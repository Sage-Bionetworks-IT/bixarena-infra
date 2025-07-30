from os import environ

import aws_cdk as cdk

from src.ecs_stack import EcsStack
from src.load_balancer_stack import LoadBalancerStack
from src.network_stack import NetworkStack
from src.service_props import ServiceProps
from src.service_stack import LoadBalancedServiceStack

# get the environment and set environment specific variables
VALID_ENVIRONMENTS = ["dev", "stage", "prod"]
environment = environ.get("ENV")
match environment:
    case "prod":
        environment_variables = {
            "VPC_CIDR": "10.254.174.0/24",
            "FQDN": "prod.mydomain.io",
            "CERTIFICATE_ARN": "arn:aws:acm:us-east-1:XXXXXXXXX:certificate/69b3ba97-b382-4648-8f94-a250b77b4994",
            "TAGS": {"CostCenter": "NO PROGRAM / 000000"},
        }
    case "stage":
        environment_variables = {
            "VPC_CIDR": "10.254.173.0/24",
            "FQDN": "stage.mydomain.io",
            "CERTIFICATE_ARN": "arn:aws:acm:us-east-1:XXXXXXXXXX:certificate/69b3ba97-b382-4648-8f94-a250b77b4994",
            "TAGS": {"CostCenter": "NO PROGRAM / 000000"},
        }
    case "dev":
        environment_variables = {
            "VPC_CIDR": "10.254.172.0/24",
            "FQDN": "dev.mydomain.io",
            "CERTIFICATE_ARN": "arn:aws:acm:us-east-1:607346494281:certificate/e8093404-7db1-4042-90d0-01eb5bde1ffc",
            "TAGS": {"CostCenter": "NO PROGRAM / 000000"},
        }
    case _:
        valid_envs_str = ",".join(VALID_ENVIRONMENTS)
        raise SystemExit(
            f"Must set environment variable `ENV` to one of {valid_envs_str}. Currently set to {environment}."
        )

stack_name_prefix = f"app-{environment}"
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

ecs_stack = EcsStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-ecs",
    vpc=network_stack.vpc,
    namespace=fully_qualified_domain_name,
)

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
    ecs_task_cpu=256,
    ecs_task_memory=512,
    container_name="my-app",
    container_location=f"ghcr.io/sage-bionetworks/my-app:{app_version}",
    container_port=80,
    container_env_vars={
        "APP_VERSION": f"{app_version}",
    },
)
app_stack = LoadBalancedServiceStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-app",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=app_props,
    load_balancer=load_balancer_stack.alb,
    certificate_arn=environment_variables["CERTIFICATE_ARN"],
    health_check_path="/health",
)
app_stack.add_dependency(app_stack)

cdk_app.synth()
