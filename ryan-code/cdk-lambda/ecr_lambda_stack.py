from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    CfnOutput,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_iam as iam,
)
from constructs import Construct

class EcrLambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create S3 buckets
        input_bucket = s3.Bucket(
            self, 
            "InputBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )
        
        output_bucket = s3.Bucket(
            self, 
            "OutputBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Create Lambda layer with dependencies
        lambda_layer = lambda_.LayerVersion(
            self,
            "DependenciesLayer",
            code=lambda_.Code.from_asset("lambda-layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_9],
            description="Layer containing numpy, bs4, lxml, etc."
        )

        # Create Lambda function
        lambda_function = lambda_.Function(
            self,
            "EcrLambdaFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="app.lambda_handler",
            code=lambda_.Code.from_asset("lambda-code"),
            timeout=Duration.seconds(300),
            memory_size=1024,
            environment={
                "OUTPUT_BUCKET": output_bucket.bucket_name
            },
            layers=[lambda_layer]
        )

        # Grant permissions to Lambda function
        input_bucket.grant_read(lambda_function)
        output_bucket.grant_write(lambda_function)
        
        # Grant Bedrock permissions
        lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:ListFoundationModels",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=["*"]
            )
        )

        # Set up S3 event notification to trigger Lambda when XML files are uploaded
        notification_filter = s3.NotificationKeyFilter(suffix=".xml")
        input_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3.LambdaDestination(lambda_function),
            notification_filter
        )
        
        # Output the bucket names for easy reference
        CfnOutput(self, "InputBucketName", value=input_bucket.bucket_name)
        CfnOutput(self, "OutputBucketName", value=output_bucket.bucket_name)
        CfnOutput(self, "LambdaFunctionName", value=lambda_function.function_name)