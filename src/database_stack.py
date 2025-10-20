import aws_cdk as cdk

from aws_cdk import aws_ec2 as ec2

from constructs import Construct
from aws_cdk import aws_rds as rds


class DatabaseStack(cdk.Stack):
    """
    Database for applications
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        allocated_storage: int = 30,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -------------------
        # create PostgreSQL database
        # -------------------

        self.database = rds.DatabaseInstance(
            self,
            "PostgresDatabase",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15_4
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.SMALL
            ),
            vpc=vpc,
            credentials=rds.Credentials.from_generated_secret("postgres"),
            multi_az=False,
            allocated_storage=allocated_storage,
            storage_encrypted=True,
            backup_retention=cdk.Duration.days(7),
            deletion_protection=False,
        )
