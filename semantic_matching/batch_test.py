import boto3
import json
import time
from typing import List, Dict

def init_bedrock_client(profile_name: str = "ecr-profile", region_name: str = "us-west-2"):
    """
    Initialize AWS Bedrock client using the specified AWS profile.

    Args:
        profile_name: AWS profile name (default: "ecr-profile")
        region_name: AWS region name (default: "us-west-2")

    Returns:
        A boto3 client for AWS Bedrock.
    """
    session = boto3.Session(profile_name=profile_name)
    return session.client('bedrock', region_name=region_name)

def verify_account_and_policies():
    """
    Verify the account and policies being used.
    Prints the AWS account ID and active policies.
    """
    sts_client = boto3.client('sts')
    account_id = sts_client.get_caller_identity().get('Account')
    print(f"AWS Account ID: {account_id}")

    iam_client = boto3.client('iam')
    attached_policies = iam_client.list_attached_role_policies(RoleName='batchinferencerole')
    print("Attached Policies:")
    for policy in attached_policies.get('AttachedPolicies', []):
        print(f"- {policy['PolicyName']} ({policy['PolicyArn']})")

def create_batch_inference_job():
    """
    Create a batch inference job on Amazon Bedrock.
    """
    bedrock = init_bedrock_client()

    role_arn = "arn:aws:iam::535002857730:role/batchinferencerole"
    input_s3_uri = "s3://bedrockbatchtest/test.jsonl"
    output_s3_uri = "s3://bedrockbatchtest/batchoutput/"
    model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"

    input_data_config = {
        "s3InputDataConfig": {
            "s3Uri": input_s3_uri
        }
    }

    output_data_config = {
        "s3OutputDataConfig": {
            "s3Uri": output_s3_uri
        }
    }

    try:
        response = bedrock.create_model_invocation_job(
            clientRequestToken="unique-request-token",
            roleArn=role_arn,
            modelId=model_id,
            jobName="bedrock-batch-inference-test",
            inputDataConfig=input_data_config,
            outputDataConfig=output_data_config
        )
        job_arn = response.get('jobArn')
        print(f"Started batch inference job with ARN: {job_arn}")
        return job_arn
    except Exception as e:
        print(f"Error creating batch inference job: {e}")
        raise

def monitor_job_status(job_arn):
    """
    Monitor the status of the batch inference job.

    Args:
        job_arn: The ARN of the batch inference job.
    """
    bedrock = init_bedrock_client()

    while True:
        try:
            job_status_response = bedrock.get_model_invocation_job(jobIdentifier=job_arn)
            status = job_status_response['status']
            if status in ['InProgress', 'Initializing', 'Submitted', 'Validating']:
                print(f"Job {job_arn} is {status}. Waiting for completion...")
                time.sleep(30)  # Wait for 30 seconds before checking again
            elif status == 'Completed':
                print(f"Job {job_arn} completed successfully.")
                break
            elif status == 'Failed':
                print(f"Job {job_arn} failed.")
                raise RuntimeError("Batch inference job failed.")
            else:
                print(f"Job {job_arn} has unexpected status: {status}")
                time.sleep(30)
        except Exception as e:
            print(f"Error monitoring job status: {e}")
            raise

# Verify account and policies
verify_account_and_policies()

# Create and monitor batch inference job
job_arn = create_batch_inference_job()
monitor_job_status(job_arn)

# After completion, results will be in the output S3 bucket.
print("Batch inference completed. Check the output in the specified S3 bucket.")
