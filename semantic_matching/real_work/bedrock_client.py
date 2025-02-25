import boto3
import json
import time
import argparse
import random
from botocore.exceptions import ClientError
import logging
from pathlib import Path
from typing import List, Dict, Any
import json_lines
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BedrockClient:
    def __init__(self, region='us-west-2', account_id='REMOVED_ID', profile_name="public-records-profile"):
        logger.info(f"Initializing BedrockClient with region: {region}, account_id: {account_id}, profile_name: {profile_name}")
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region)
        else:
            session = boto3.Session(region_name=region)
            
        self.region = region
        self.account_id = account_id
        self.s3_client = session.client('s3')
        self.iam_client = session.client('iam')
        self.single_bedrock_client = session.client('bedrock-runtime')
        self.bedrock_client = session.client('bedrock')
        self.llm_model_id = 'anthropic.claude-3-5-sonnet-20241022-v2:0'
        self.embeddings_model_id = 'cohere.embed-multilingual-v3'
        logger.info("BedrockClient initialized successfully")

    def create_s3_bucket_if_not_exists(self, bucket_name):
        logger.info(f"Checking if S3 bucket {bucket_name} exists")
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} already exists")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                try:
                    logger.info(f"Bucket {bucket_name} does not exist. Creating new bucket")
                    if self.region != 'us-east-1':
                        self.s3_client.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={
                                'LocationConstraint': self.region
                            }
                        )
                    else:
                        self.s3_client.create_bucket(Bucket=bucket_name)
                    
                    logger.info(f"Created new bucket: {bucket_name}")
                    
                    waiter = self.s3_client.get_waiter('bucket_exists')
                    waiter.wait(Bucket=bucket_name)
                    logger.info(f"Bucket {bucket_name} is now available")
                    
                    return True
                except ClientError as create_error:
                    logger.error(f"Error creating bucket: {create_error}")
                    return False
            else:
                logger.error(f"Error checking bucket: {e}")
                return False

    def verify_s3_permissions(self, bucket_name):
        logger.info(f"Verifying S3 permissions for bucket: {bucket_name}")
        try:
            if not self.create_s3_bucket_if_not_exists(bucket_name):
                raise Exception(f"Failed to create or verify bucket {bucket_name}")
                
            logger.info("Waiting for S3 permissions to propagate...")
            time.sleep(60)
            logger.info("Verifying S3 permissions...")
            
            self.s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
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
                - s3:CreateBucket
                - s3:PutObject
                - s3:GetObject
                - s3:ListBucket
                - s3:DeleteObject
                """)
            return False

    def create_iam_role(self, role_name, bucket_name):
        logger.info(f"Creating IAM role: {role_name}")
        trust_policy = {
            "Version": "2012-10-17",
            "Statement":[{
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
            "Statement":[{
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
            role_response = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            role_arn = role_response['Role']['Arn']
            logger.info(f"Created IAM role: {role_name}")

            self.iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-policy",
                PolicyDocument=json.dumps(permission_policy)
            )
            logger.info("Attached permission policy to role")

            time.sleep(30)
            return role_arn
        except ClientError as e:
            logger.error(f"Error creating IAM role: {e}")
            raise

    def upload_file_to_s3(self, local_file_path, bucket_name, s3_key):
        logger.info(f"Uploading file {local_file_path} to S3 bucket {bucket_name} with key {s3_key}")
        try:
            if not Path(local_file_path).exists():
                raise FileNotFoundError(f"Input file not found: {local_file_path}")
                
            if not self.verify_s3_permissions(bucket_name):
                raise PermissionError("Failed to verify S3 permissions")

            self.s3_client.upload_file(local_file_path, bucket_name, s3_key)
            logger.info(f"Uploaded {local_file_path} to s3://{bucket_name}/{s3_key}")
        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise

    def create_batch_inference_job(self, job_name, input_location, output_location, role_arn):
        logger.info(f"Creating batch inference job: {job_name}")
        try:
            response = self.bedrock_client.create_model_invocation_job(
                modelId=self.llm_model_id,
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
            job_id = job_arn.split('/')[-1]
            logger.info(f"Created batch inference job: {job_id}")
            return job_id
        except ClientError as e:
            logger.error(f"Error creating batch inference job: {e}")
            raise

    def monitor_job_status(self, job_id):
        logger.info(f"Monitoring job status for job ID: {job_id}")
        while True:
            try:
                job_arn = f"arn:aws:bedrock:{self.region}:{self.account_id}:model-invocation-job/{job_id}"
                response = self.bedrock_client.get_model_invocation_job(jobIdentifier=job_arn)
                status = response['status']
                logger.info(f"Job status: {status}")

                if status.upper() in ['COMPLETED', 'FAILED', 'STOPPED']:
                    return status

                time.sleep(60)
            except ClientError as e:
                logger.error(f"Error monitoring job status: {e}")
                raise

    def single_llm_call(self, question: str):
        logger.info(f"Making single LLM call with question: {question}")
        try:
            response = self.single_bedrock_client.invoke_model(
                modelId=self.llm_model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1024,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": question
                                }
                            ]
                        }
                    ]
                })
            )
            return json.loads(response['body'].read())
        except ClientError as e:
            logger.error(f"Error making single LLM call: {e}")
            raise

    def generate_batch_jsonl(self, questions: List[str], filename: str = "batch_questions.jsonl"):
        logger.info(f"Generating batch JSONL file: {filename}")
        records = []
        for question in questions:
            record_id = f"Q_{int(time.time())}_{random.randint(1000, 9999)}"
            record = {
                "recordId": record_id,
                "modelInput": {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1024,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": question
                                }
                            ]
                        }
                    ]
                }
            }
            records.append(record)
        
        with open(filename, 'w') as f:
            for record in records:
                json_str = json.dumps(record)
                f.write(json_str + '\n')
        
        logger.info(f"Generated {len(records)} questions in {filename}")
        return records

    def download_batch_results(self, bucket_name: str, s3_prefix: str = "output/"):
        logger.info(f"Downloading batch results from bucket: {bucket_name} with prefix: {s3_prefix}")
        try:
            print(f"\nAttempting to download results from bucket: {bucket_name}")
            print(f"Using prefix: {s3_prefix}")
            
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=s3_prefix
            )
            
            print(f"\nResponse contents: {response}")
            
            jsonl_out_file = None
            for obj in response.get('Contents', []):
                key = obj['Key']
                print(f"Found object: {key}")
                if key.endswith('.jsonl.out'):
                    jsonl_out_file = key
                    print(f"\nFound JSONL output file: {key}")
                    break
            
            if not jsonl_out_file:
                print(f"\nError: No .jsonl.out file found in bucket {bucket_name} with prefix {s3_prefix}")
                logger.error(f"No .jsonl.out file found in bucket {bucket_name} with prefix {s3_prefix}")
                return None
            
            self.s3_client.download_file(
                bucket_name,
                jsonl_out_file,
                "downloaded_results.jsonl.out"
            )
            
            print(f"\nSuccessfully downloaded file to: downloaded_results.jsonl.out")
            return "downloaded_results.jsonl.out"
        except ClientError as e:
            print(f"\nError during download process: {str(e)}")
            logger.error(f"Error downloading batch results: {e}")
            raise

    def _get_folder_time(self, folder_prefix):
        timestamp_str = folder_prefix.split('/')[-2]
        try:
            from datetime import datetime
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.error(f"Error parsing folder timestamp: {e}")
            return datetime.min

    def generate_embeddings(self, texts: List[str], filename: str = "embeddings.jsonl"):
        logger.info(f"Generating embeddings for {len(texts)} texts in file: {filename}")
        try:
            embeddings = []
            for text in tqdm(texts, desc="Generating embeddings", unit="text"):
                response = self.single_bedrock_client.invoke_model(
                    modelId=self.embeddings_model_id,
                    body=json.dumps({
                        "texts": [text],
                        "input_type": "search_document"
                    })
                )
                result = json.loads(response['body'].read())
                embeddings.append(result['embeddings'][0])

                with open(filename, 'a') as f:
                    json.dump({
                        "text": text,
                        "embedding": result['embeddings'][0]
                    }, f)
                    f.write('\n')

            logger.info(f"Generated embeddings for {len(texts)} texts in {filename}")
            return embeddings
        except ClientError as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def semantic_search(self, query: str, embeddings_file: str):
        logger.info(f"Performing semantic search for query: {query}")
        try:
            response = self.single_bedrock_client.invoke_model(
                modelId=self.embeddings_model_id,
                body=json.dumps({
                    "texts": [query],
                    "input_type": "search_query"
                })
            )
            query_embedding = json.loads(response['body'].read())['embeddings'][0]
            
            existing_embeddings = []
            existing_texts = []
            with open(embeddings_file, 'r') as f:
                for line in f:
                    data = json.loads(line)
                    existing_embeddings.append(data['embedding'])
                    existing_texts.append(data['text'])
            
            from numpy import dot
            from numpy.linalg import norm
            
            def cosine_similarity(a, b):
                return dot(a, b) / (norm(a) * norm(b))
            
            similarities = [
                cosine_similarity(query_embedding, doc_embedding) 
                for doc_embedding in existing_embeddings
            ]
            
            results = list(zip(existing_texts, similarities))
            results.sort(key=lambda x: x[1], reverse=True)
            
            return results[:10]
        except ClientError as e:
            logger.error(f"Error performing semantic search: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Run AWS Bedrock batch inference')
    parser.add_argument('input_file', type=str, help='Path to input JSONL file')
    parser.add_argument('--bucket', type=str, required=True, help='S3 bucket name')
    parser.add_argument('--region', type=str, default='us-west-2', help='AWS region')
    parser.add_argument('--account-id', type=str, required=True, help='AWS account ID')
    parser.add_argument('--profile', type=str, help='AWS SSO profile name')
    args = parser.parse_args()

    logger.info(f"Starting Bedrock batch inference with arguments: {args}")

    handler = BedrockClient(
        region=args.region, 
        account_id=args.account_id,
        profile_name=args.profile
    )

    try:
        role_name = f"bedrock-batch-role-{int(time.time())}"
        logger.info(f"Creating IAM role: {role_name}")
        role_arn = handler.create_iam_role(role_name, args.bucket)

        input_key = f"input/{Path(args.input_file).name}"
        logger.info(f"Uploading input file to S3 with key: {input_key}")
        handler.upload_file_to_s3(args.input_file, args.bucket, input_key)

        job_name = f"bedrock-batch-{int(time.time())}"
        input_location = f"s3://{args.bucket}/{input_key}"
        output_location = f"s3://{args.bucket}/output/"
        
        logger.info(f"Creating batch inference job: {job_name}")
        job_id = handler.create_batch_inference_job(
            job_name,
            input_location,
            output_location,
            role_arn
        )

        logger.info(f"Monitoring job status for job ID: {job_id}")
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