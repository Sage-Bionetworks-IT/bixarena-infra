from os import environ

import aws_cdk as cdk

from src.database_stack import DatabaseStack
from src.ecs_stack import EcsStack
from src.load_balancer_stack import LoadBalancerStack
from src.network_stack import NetworkStack
from src.service_props import ServiceProps
from src.service_stack import LoadBalancedServiceStack, ServiceStack

# get the environment and set environment specific variables
VALID_ENVIRONMENTS = ["dev", "stage", "prod"]
environment = environ.get("ENV")
match environment:
    case "prod":
        environment_variables = {
            "VPC_CIDR": "10.254.122.0/24",
            "FQDN": "prod.bixarena.ai",
            "CERTIFICATE_ARN": "arn:aws:acm:us-east-1:045984464920:certificate/2d81bfca-89ea-42cb-8e78-ea9c3d1f6919",
            "TAGS": {"CostCenter": "NO PROGRAM / 000000"},
        }
    case "stage":
        environment_variables = {
            "VPC_CIDR": "10.254.121.0/24",
            "FQDN": "stage.bixarena.ai",
            "CERTIFICATE_ARN": "arn:aws:acm:us-east-1:045984464920:certificate/2d81bfca-89ea-42cb-8e78-ea9c3d1f6919",
            "TAGS": {"CostCenter": "NO PROGRAM / 000000"},
        }
    case "dev":
        environment_variables = {
            "VPC_CIDR": "10.254.120.0/24",
            "FQDN": "dev.bixarena.ai",
            "CERTIFICATE_ARN": "arn:aws:acm:us-east-1:864020296088:certificate/d82cd9ec-2106-4293-9232-62af18bb6295",
            "TAGS": {"CostCenter": "NO PROGRAM / 000000"},
        }
    case _:
        valid_envs_str = ",".join(VALID_ENVIRONMENTS)
        raise SystemExit(
            f"Must set environment variable `ENV` to one of {valid_envs_str}. Currently set to {environment}."
        )

stack_name_prefix = f"bixarena-{environment}"
fully_qualified_domain_name = environment_variables["FQDN"]
environment_tags = environment_variables["TAGS"]
app_version = "edge"

# Define stacks
cdk_app = cdk.App()

# recursively apply tags to all stack resources
if environment_tags:
    for key, value in environment_tags.items():
        cdk.Tags.of(cdk_app).add(key, value)


network_stack = NetworkStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-network",
    vpc_cidr=environment_variables["VPC_CIDR"],
)

database_stack = DatabaseStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-db",
    vpc=network_stack.vpc,
    allocated_storage=50,
)


ecs_stack = EcsStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-ecs",
    vpc=network_stack.vpc,
    namespace=fully_qualified_domain_name,
)

api_props = ServiceProps(
    container_name="bixarena-api",
    container_location=f"ghcr.io/sage-bionetworks/bixarena-api:{app_version}",
    container_port=8112,
    ecs_task_memory=1024,
)
api_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-api",
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
    container_location=f"ghcr.io/sage-bionetworks/bixarena-ai-service:{app_version}",
    container_port=8114,
    container_env_vars={
        "APP_PORT": "8114",
    },
    ecs_task_memory=1024,
)
ai_service_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-ai-service",
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
    container_location=f"ghcr.io/sage-bionetworks/bixarena-api-gateway:{app_version}",
    container_port=8113,
    ecs_task_memory=1024,
)
api_gateway_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-api-gateway",
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
    construct_id=f"{stack_name_prefix}-load-balancer",
    vpc=network_stack.vpc,
)

app_props = ServiceProps(
    container_name="bixarena-app",
    container_location=f"ghcr.io/sage-bionetworks/bixarena-app:{app_version}",
    container_port=8100,
    ecs_task_memory=1024,
    container_env_vars={
        "APP_PORT": "8100",
        "ENVIRONMENT": "development",
        "API_BASE_URL": f"https://{fully_qualified_domain_name}/v1",
        "OIDC_BASE_URL": "http://127.0.0.1:8112/v1",
        "OPENAI_API_KEY": "changeme",
    },
)
app_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-app",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=app_props,
)
app_stack.add_dependency(api_stack)

apex_props = ServiceProps(
    container_name="bixarena-apex",
    container_location=f"ghcr.io/sage-bionetworks/bixarena-apex:{app_version}",
    container_port=80,
    container_env_vars={
        "API_GATEWAY_HOST": "bixarena-api-gateway",
        "API_GATEWAY_PORT": "8113",
        "APP_HOST": "bixarena-app",
        "APP_PORT": "8100",
    },
)
apex_stack = LoadBalancedServiceStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-apex",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=apex_props,
    load_balancer=load_balancer_stack.alb,
    certificate_arn=environment_variables["CERTIFICATE_ARN"],
)
apex_stack.add_dependency(app_stack)
apex_stack.add_dependency(api_gateway_stack)

cdk_app.synth()
