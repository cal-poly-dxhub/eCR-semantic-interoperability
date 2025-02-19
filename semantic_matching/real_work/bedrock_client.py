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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BedrockClient:
    def __init__(self, region='us-west-2', account_id='REMOVED_ID', profile_name="public-records-profile"):
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
        
    # def verify_s3_permissions(self, bucket_name):
    #     try:
    #         print("Waiting for S3 permissions to propagate...")
    #         time.sleep(60)
    #         print("Verifying S3 permissions...")
    #         self.s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
    #         self.s3_client.put_object(
    #             Bucket=bucket_name,
    #             Key='test-permissions.txt',
    #             Body='Testing write permissions'
    #         )
    #         self.s3_client.delete_object(
    #             Bucket=bucket_name,
    #             Key='test-permissions.txt'
    #         )
    #         logger.info("Successfully verified S3 permissions")
    #         return True
    #     except ClientError as e:
    #         logger.error(f"S3 permission verification failed: {e}")
    #         if 'AccessDenied' in str(e):
    #             logger.error("""
    #             Please ensure your AWS credentials have the following S3 permissions:
    #             - s3:PutObject
    #             - s3:GetObject
    #             - s3:ListBucket
    #             - s3:DeleteObject
    #             """)
    #         return False
    def create_s3_bucket_if_not_exists(self, bucket_name):
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} already exists")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                try:
                    # For regions other than us-east-1, we need to specify LocationConstraint
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
                    
                    # Wait for bucket to be created and available
                    waiter = self.s3_client.get_waiter('bucket_exists')
                    waiter.wait(Bucket=bucket_name)
                    
                    return True
                except ClientError as create_error:
                    logger.error(f"Error creating bucket: {create_error}")
                    return False
            else:
                logger.error(f"Error checking bucket: {e}")
                return False

    def verify_s3_permissions(self, bucket_name):
        try:
            # First ensure bucket exists
            if not self.create_s3_bucket_if_not_exists(bucket_name):
                raise Exception(f"Failed to create or verify bucket {bucket_name}")
                
            print("Waiting for S3 permissions to propagate...")
            time.sleep(60)
            print("Verifying S3 permissions...")
            
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

    def single_llm_call(self, question: str):
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
        try:
            results = []
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=s3_prefix
            )
            
            for obj in response.get('Contents', []):
                key = obj['Key']
                if key.endswith('.jsonl'):
                    content = self.s3_client.get_object(
                        Bucket=bucket_name,
                        Key=key
                    )
                    results.extend(json_lines.Reader(content['Body'].read().decode()))
            
            logger.info(f"Downloaded {len(results)} results from S3")
            return results
        except ClientError as e:
            logger.error(f"Error downloading batch results: {e}")
            raise

    # def generate_embeddings(self, texts: List[str], filename: str = "embeddings.jsonl"):
    #     try:
    #         from sentence_transformers import SentenceTransformer
    #         model = SentenceTransformer(self.embeddings_model_id)
    #         embeddings = model.encode(texts, show_progress_bar=True)

    #         with open(filename, 'w') as f:
    #             for text, emb in zip(texts, embeddings):
    #                 json.dump({
    #                     "text": text,
    #                     "embedding": emb.tolist()
    #                 }, f)
    #                 f.write('\n')
            
    #         logger.info(f"Generated embeddings for {len(texts)} texts in {filename}")
    #         return embeddings
    #     except Exception as e:
    #         logger.error(f"Error generating embeddings: {e}")
    #         raise

    # def semantic_search(self, query: str, embeddings_file: str):
    #     try:
    #         from sentence_transformers import SentenceTransformer, util
    #         model = SentenceTransformer(self.embeddings_model_id)
            
    #         # Load existing embeddings
    #         existing_embeddings = []
    #         existing_texts = []
    #         with open(embeddings_file, 'r') as f:
    #             for line in f:
    #                 data = json.loads(line)
    #                 existing_embeddings.append(data['embedding'])
    #                 existing_texts.append(data['text'])
            
    #         # Encode query
    #         query_embedding = model.encode(query)
            
    #         # Compute cosine similarities
    #         cos_scores = util.cos_sim(query_embedding, existing_embeddings)
            
    #         # Get top 10 matches
    #         top_results = zip(
    #             existing_texts,
    #             existing_embeddings,
    #             cos_scores[0]
    #         )
            
    #         # Sort by score in descending order
    #         top_results = sorted(top_results, key=lambda x: x[2], reverse=True)
            
    #         return [(text, score) for text, emb, score in top_results[:10]]
    #     except Exception as e:
    #         logger.error(f"Error performing semantic search: {e}")
    #         raise
    def generate_embeddings(self, texts: List[str], filename: str = "embeddings.jsonl"):
        try:
            embeddings = []
            for text in texts:
                response = self.single_bedrock_client.invoke_model(
                    modelId=self.embeddings_model_id,
                    body=json.dumps({
                        "texts": [text],
                        "input_type": "search_document"
                    })
                )
                result = json.loads(response['body'].read())
                embeddings.append(result['embeddings'][0])

                # Write results to file as we go to handle large datasets
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
        try:
            # Get query embedding
            response = self.single_bedrock_client.invoke_model(
                modelId=self.embeddings_model_id,
                body=json.dumps({
                    "texts": [query],
                    "input_type": "search_query"
                })
            )
            query_embedding = json.loads(response['body'].read())['embeddings'][0]
            
            # Load existing embeddings
            existing_embeddings = []
            existing_texts = []
            with open(embeddings_file, 'r') as f:
                for line in f:
                    data = json.loads(line)
                    existing_embeddings.append(data['embedding'])
                    existing_texts.append(data['text'])
            
            # Compute cosine similarities
            from numpy import dot
            from numpy.linalg import norm
            
            def cosine_similarity(a, b):
                return dot(a, b) / (norm(a) * norm(b))
            
            # Calculate similarities
            similarities = [
                cosine_similarity(query_embedding, doc_embedding) 
                for doc_embedding in existing_embeddings
            ]
            
            # Create list of (text, similarity) tuples and sort
            results = list(zip(existing_texts, similarities))
            results.sort(key=lambda x: x[1], reverse=True)
            
            # Return top 10 results
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

    handler = BedrockClient(
        region=args.region, 
        account_id=args.account_id,
        profile_name=args.profile
    )

    try:
        role_name = f"bedrock-batch-role-{int(time.time())}"
        role_arn = handler.create_iam_role(role_name, args.bucket)

        input_key = f"input/{Path(args.input_file).name}"
        handler.upload_file_to_s3(args.input_file, args.bucket, input_key)

        job_name = f"bedrock-batch-{int(time.time())}"
        input_location = f"s3://{args.bucket}/{input_key}"
        output_location = f"s3://{args.bucket}/output/"
        
        job_id = handler.create_batch_inference_job(
            job_name,
            input_location,
            output_location,
            role_arn
        )

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
