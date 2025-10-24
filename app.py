import aws_cdk as cdk

from src.database_stack import DatabaseStack
from src.ecs_stack import EcsStack
from src.load_balancer_stack import LoadBalancerStack
from src.network_stack import NetworkStack
from src.service_props import ServiceProps
from src.service_stack import LoadBalancedServiceStack, ServiceStack
from src.utils import load_context_config

cdk_app = cdk.App()
env_name = cdk_app.node.try_get_context("env") or "dev"
config = load_context_config(env_name=env_name)
STACK_NAME_PREFIX = f"bixarena-{env_name}"
FQDN = config["FQDN"]
TAGS = config["TAGS"]
CERTIFICATE_ARN = config["CERTIFICATE_ARN"]
APP_VERSION = "edge"

# recursively apply tags to all stack resources
if TAGS:
    for key, value in TAGS.items():
        cdk.Tags.of(cdk_app).add(key, value)


network_stack = NetworkStack(
    scope=cdk_app,
    construct_id=f"{STACK_NAME_PREFIX}-network",
    vpc_cidr=config["VPC_CIDR"],
)

database_stack = DatabaseStack(
    scope=cdk_app,
    construct_id=f"{STACK_NAME_PREFIX}-db",
    vpc=network_stack.vpc,
    allocated_storage=50,
)

ecs_stack = EcsStack(
    scope=cdk_app,
    construct_id=f"{STACK_NAME_PREFIX}-ecs",
    vpc=network_stack.vpc,
    namespace=FQDN,
)

api_props = ServiceProps(
    container_name="bixarena-api",
    container_location=f"ghcr.io/sage-bionetworks/bixarena-api:{APP_VERSION}",
    container_port=8112,
    ecs_task_memory=1024,
)
api_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{STACK_NAME_PREFIX}-api",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=api_props,
)
api_stack.add_dependency(database_stack)
api_stack.service.connections.allow_to_default_port(
    database_stack.database,
    "Allow API container to connect to database",
)
ai_service_props = ServiceProps(
    container_name="bixarena-ai-service",
    container_location=f"ghcr.io/sage-bionetworks/bixarena-ai-service:{APP_VERSION}",
    container_port=8114,
    container_env_vars={
        "APP_PORT": "8114",
    },
    ecs_task_memory=1024,
)
ai_service_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{STACK_NAME_PREFIX}-ai-service",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=ai_service_props,
)
ai_service_stack.add_dependency(database_stack)
ai_service_stack.service.connections.allow_to_default_port(
    database_stack.database,
    "Allow AI Service container to connect to database",
)

api_gateway_props = ServiceProps(
    container_name="bixarena-api-gateway",
    container_location=f"ghcr.io/sage-bionetworks/bixarena-api-gateway:{APP_VERSION}",
    container_port=8113,
    ecs_task_memory=1024,
)
api_gateway_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{STACK_NAME_PREFIX}-api-gateway",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=api_gateway_props,
)
api_gateway_stack.add_dependency(api_stack)
api_gateway_stack.add_dependency(ai_service_stack)


# From AWS docs https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-connect-concepts-deploy.html
# The public discovery and reachability should be created last by AWS CloudFormation, including the frontend
# client service. The services need to be created in this order to prevent an time period when the frontend
# client service is running and available the public, but a backend isn't.
load_balancer_stack = LoadBalancerStack(
    scope=cdk_app,
    construct_id=f"{STACK_NAME_PREFIX}-load-balancer",
    vpc=network_stack.vpc,
)
load_balancer_stack.add_dependency(ecs_stack)

app_props = ServiceProps(
    container_name="bixarena-app",
    container_location=f"ghcr.io/sage-bionetworks/bixarena-app:{APP_VERSION}",
    container_port=8100,
    ecs_task_memory=1024,
    container_env_vars={
        "APP_PORT": "8100",
        "ENVIRONMENT": "development",
        "API_BASE_URL": f"https://{FQDN}/v1",
        "OIDC_BASE_URL": "http://127.0.0.1:8112/v1",
        "OPENAI_API_KEY": "changeme",
    },
)
app_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{STACK_NAME_PREFIX}-app",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=app_props,
)
app_stack.add_dependency(api_stack)

apex_props = ServiceProps(
    container_name="bixarena-apex",
    container_location=f"ghcr.io/sage-bionetworks/bixarena-apex:{APP_VERSION}",
    container_port=8111,
    container_env_vars={
        "API_GATEWAY_HOST": "bixarena-api-gateway",
        "API_GATEWAY_PORT": "8113",
        "APP_HOST": "bixarena-app",
        "APP_PORT": "8100",
    },
)
apex_stack = LoadBalancedServiceStack(
    scope=cdk_app,
    construct_id=f"{STACK_NAME_PREFIX}-apex",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=apex_props,
    load_balancer=load_balancer_stack.alb,
    certificate_arn=CERTIFICATE_ARN,
)
apex_stack.add_dependency(app_stack)
apex_stack.add_dependency(api_gateway_stack)

cdk_app.synth()
