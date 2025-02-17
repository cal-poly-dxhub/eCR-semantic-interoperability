import boto3
import json
import time
import argparse
from botocore.exceptions import ClientError
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BedrockBatchInference:
    def __init__(self, region='us-west-2', account_id='REMOVED_ID', profile_name=None):
        # Initialize session with the specified profile
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region)
        else:
            session = boto3.Session(region_name=region)
            
        self.region = region
        self.account_id = account_id
        self.s3_client = session.client('s3')
        self.iam_client = session.client('iam')
        self.bedrock_client = session.client('bedrock')
        self.model_id = 'anthropic.claude-3-5-sonnet-20240620-v1:0'

    def verify_s3_permissions(self, bucket_name):
        """Verify S3 permissions before proceeding."""
        try:
            # Try to list objects to verify read permissions
            self.s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
            # Try to put a test object to verify write permissions
            self.s3_client.put_object(
                Bucket=bucket_name,
                Key='test-permissions.txt',
                Body='Testing write permissions'
            )
            self.s3_client.delete_object(
                Bucket=bucket_name,
                Key='test-permissions.txt'
            )
            logger.info("Successfully verified S3 permissions")
            return True
        except ClientError as e:
            logger.error(f"S3 permission verification failed: {e}")
            if 'AccessDenied' in str(e):
                logger.error("""
                Please ensure your AWS credentials have the following S3 permissions:
                - s3:PutObject
                - s3:GetObject
                - s3:ListBucket
                - s3:DeleteObject
                
                If using AWS SSO, make sure you've logged in with: 
                aws sso login --profile your-profile-name
                """)
            return False

    def create_iam_role(self, role_name, bucket_name):
        """Create IAM role with trust and permission policies."""
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": self.account_id
                    },
                    "ArnEquals": {
                        "aws:SourceArn": f"arn:aws:bedrock:{self.region}:{self.account_id}:model-invocation-job/*"
                    }
                }
            }]
        }

        permission_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket"
                ],
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}",
                    f"arn:aws:s3:::{bucket_name}/*"
                ],
                "Condition": {
                    "StringEquals": {
                        "aws:ResourceAccount": self.account_id
                    }
                }
            }]
        }

        try:
            # Create the IAM role
            role_response = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            role_arn = role_response['Role']['Arn']
            logger.info(f"Created IAM role: {role_name}")

            # Attach the permission policy
            self.iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-policy",
                PolicyDocument=json.dumps(permission_policy)
            )
            logger.info("Attached permission policy to role")

            # Wait for role to propagate
            logger.info("Waiting for IAM role to propagate...")
            time.sleep(30)

            return role_arn

        except ClientError as e:
            logger.error(f"Error creating IAM role: {e}")
            raise

    def upload_file_to_s3(self, local_file_path, bucket_name, s3_key):
        """Upload a file to S3 bucket."""
        try:
            # First verify the file exists locally
            if not Path(local_file_path).exists():
                raise FileNotFoundError(f"Input file not found: {local_file_path}")
                
            # Verify S3 permissions before attempting upload
            if not self.verify_s3_permissions(bucket_name):
                raise PermissionError("Failed to verify S3 permissions")

            # Upload file directly
            self.s3_client.upload_file(local_file_path, bucket_name, s3_key)
            logger.info(f"Uploaded {local_file_path} to s3://{bucket_name}/{s3_key}")
        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise

    def create_batch_inference_job(self, job_name, input_location, output_location, role_arn):
        """Create a Bedrock batch inference job."""
        try:
            response = self.bedrock_client.create_model_invocation_job(
                modelId=self.model_id,
                jobName=job_name,
                inputDataConfig={
                    "s3InputDataConfig": {
                        "s3Uri": input_location
                    }
                },
                outputDataConfig={
                    "s3OutputDataConfig": {
                        "s3Uri": output_location
                    }
                },
                roleArn=role_arn
            )
            job_arn = response.get('jobArn')
            # Extract job ID from ARN (last part after the slash)
            job_id = job_arn.split('/')[-1]
            logger.info(f"Created batch inference job: {job_id}")
            return job_id
        except ClientError as e:
            logger.error(f"Error creating batch inference job: {e}")
            raise

    def monitor_job_status(self, job_id):
        """Monitor the status of a batch inference job."""
        while True:
            try:
                job_arn = f"arn:aws:bedrock:{self.region}:{self.account_id}:model-invocation-job/{job_id}"
                response = self.bedrock_client.get_model_invocation_job(jobIdentifier=job_arn)
                status = response['status']
                logger.info(f"Job status: {status}")

                if status in ['COMPLETED', 'FAILED', 'STOPPED']:
                    return status

                time.sleep(60)
            except ClientError as e:
                logger.error(f"Error monitoring job status: {e}")
                raise

def main():
    parser = argparse.ArgumentParser(description='Run AWS Bedrock batch inference')
    parser.add_argument('input_file', type=str, help='Path to input JSONL file')
    parser.add_argument('--bucket', type=str, required=True, help='S3 bucket name')
    parser.add_argument('--region', type=str, default='us-west-2', help='AWS region')
    parser.add_argument('--account-id', type=str, required=True, help='AWS account ID')
    parser.add_argument('--profile', type=str, help='AWS SSO profile name')
    args = parser.parse_args()

    # Initialize the batch inference handler
    handler = BedrockBatchInference(
        region=args.region, 
        account_id=args.account_id,
        profile_name=args.profile
    )

    try:
        # Create IAM role
        role_name = f"bedrock-batch-role-{int(time.time())}"
        role_arn = handler.create_iam_role(role_name, args.bucket)

        # Upload input file to S3
        input_key = f"input/{Path(args.input_file).name}"
        handler.upload_file_to_s3(args.input_file, args.bucket, input_key)

        # Create and start batch inference job
        job_name = f"bedrock-batch-{int(time.time())}"
        input_location = f"s3://{args.bucket}/{input_key}"
        output_location = f"s3://{args.bucket}/output/"
        
        job_id = handler.create_batch_inference_job(
            job_name,
            input_location,
            output_location,
            role_arn
        )

        # Monitor job status
        final_status = handler.monitor_job_status(job_id)
        
        if final_status == 'COMPLETED':
            logger.info(f"Batch inference completed successfully!")
            logger.info(f"Results available at: {output_location}")
        else:
            logger.error(f"Job failed with status: {final_status}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

if __name__ == "__main__":
    main()