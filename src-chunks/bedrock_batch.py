import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
import boto3
from botocore.exceptions import ClientError


from bedrock import client, bedrock, llm_model_id, invoke_llm

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

start_time = time.time()

class TokenCounter:
    """Simple token counter for tracking API usage."""
    
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using word count as a rough approximation.
        Claude models use ~0.75 tokens per word on average."""
        return int(len(text.split()) / 0.75) + 1
    
    def add_input(self, text: str) -> None:
        """Count input tokens."""
        self.input_tokens += self.estimate_tokens(text)
    
    def add_output(self, text: str) -> None:
        """Count output tokens."""
        self.output_tokens += self.estimate_tokens(text)
    
    def get_metrics(self) -> Dict[str, int]:
        """Get current token usage metrics."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens
        }


class BedrockBatch:
    """Batch processing for AWS Bedrock using existing credentials."""

    
    def __init__(self, region='us-west-2', profile_name='pub-rec'):
        """Initialize using the profile credentials."""
        self.region = region
        self.profile_name = profile_name
    
        # Create a session using the specified profile
        session = boto3.Session(profile_name=profile_name, region_name=region)
        credentials = session.get_credentials().get_frozen_credentials()
        logger.info("Using AWS Credentials from profile: %s", profile_name)
    
        # Use the session to create clients
        self.bedrock_client = session.client('bedrock')
        self.bedrock_runtime_client = session.client('bedrock-runtime')
        self.s3_client = session.client('s3')
        self.iam_client = session.client('iam')
        
        # Get AWS account ID from the session
        self.account_id = self._get_account_id(session)
        
        # Use the model ID from  bedrock module
        self.llm_model_id = llm_model_id
        
        logger.info("BedrockBatch initialized successfully")
    
    def _get_account_id(self, session) -> str:
        """Get AWS account ID from STS."""
        sts_client = session.client('sts')
        return sts_client.get_caller_identity()["Account"]
    
    def create_s3_bucket_if_not_exists(self, bucket_name: str) -> bool:
        """Create S3 bucket if it doesn't exist."""
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

    def verify_s3_permissions(self, bucket_name: str) -> bool:
        """Verify S3 permissions for batch processing."""
        logger.info(f"Verifying S3 permissions for bucket: {bucket_name}")
        try:
            if not self.create_s3_bucket_if_not_exists(bucket_name):
                raise Exception(f"Failed to create or verify bucket {bucket_name}")
                
            logger.info("Testing S3 permissions...")
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
            return False

    def create_iam_role(self, role_name: str, bucket_name: str) -> str:
        """Create IAM role for Bedrock batch inference."""
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
                    "s3:*"
                ],
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}",
                    f"arn:aws:s3:::{bucket_name}/*"
                ]
            }]
        }

        try:
            # Check if role already exists
            try:
                role_response = self.iam_client.get_role(RoleName=role_name)
                role_arn = role_response['Role']['Arn']
                logger.info(f"IAM role {role_name} already exists with ARN: {role_arn}")
                
                # Update trust policy
                self.iam_client.update_assume_role_policy(
                    RoleName=role_name,
                    PolicyDocument=json.dumps(trust_policy)
                )
                logger.info(f"Updated trust policy for existing role: {role_name}")
                
                # Update permission policy
                try:
                    self.iam_client.get_role_policy(
                        RoleName=role_name,
                        PolicyName=f"{role_name}-policy"
                    )
                    
                    # Update existing policy
                    self.iam_client.put_role_policy(
                        RoleName=role_name,
                        PolicyName=f"{role_name}-policy",
                        PolicyDocument=json.dumps(permission_policy)
                    )
                    logger.info(f"Updated permission policy for role: {role_name}")
                except ClientError:
                    # Create new policy if it doesn't exist
                    self.iam_client.put_role_policy(
                        RoleName=role_name,
                        PolicyName=f"{role_name}-policy",
                        PolicyDocument=json.dumps(permission_policy)
                    )
                    logger.info(f"Created new permission policy for role: {role_name}")
                    
            except ClientError:
                # Create new role if it doesn't exist
                role_response = self.iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy)
                )
                role_arn = role_response['Role']['Arn']
                logger.info(f"Created new IAM role: {role_name} with ARN: {role_arn}")

                # Attach permission policy
                self.iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=f"{role_name}-policy",
                    PolicyDocument=json.dumps(permission_policy)
                )
                logger.info("Attached permission policy to new role")

            # Wait for role propagation
            logger.info("Waiting for IAM role to propagate...")
            time.sleep(50)
            return role_arn
        except ClientError as e:
            logger.error(f"Error creating/updating IAM role: {e}")
            raise

    def upload_file_to_s3(self, local_file_path: str, bucket_name: str, s3_key: str) -> None:
        """Upload file to S3 bucket."""
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

    def create_batch_inference_job(self, job_name: str, input_location: str, 
                                  output_location: str, role_arn: str) -> str:
        """Create a batch inference job."""
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

    def monitor_job_status(self, job_id: str) -> str:
        """Monitor the status of a batch job until completion."""
        logger.info(f"Monitoring job status for job ID: {job_id}")
        while True:
            try:
                job_arn = f"arn:aws:bedrock:{self.region}:{self.account_id}:model-invocation-job/{job_id}"
                response = self.bedrock_client.get_model_invocation_job(jobIdentifier=job_arn)
                status = response['status']
                logger.info(f"Job status: {status}")

                if status.upper() == 'FAILED':
                    # Get and log the failure reason
                    failure_reason = response.get('message', 'No failure reason provided')
                    logger.error(f"Job failed with reason: {failure_reason}")
                    return status
                elif status.upper() in ['COMPLETED', 'STOPPED']:
                    return status

                time.sleep(30)  # Check every 30 seconds
            except ClientError as e:
                logger.error(f"Error monitoring job status: {e}")
                raise

    def download_batch_results(self, bucket_name: str, s3_prefix: str = "output/") -> Optional[str]:
        """Download batch inference results from S3."""
        logger.info(f"Downloading batch results from bucket: {bucket_name} with prefix: {s3_prefix}")
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=s3_prefix
            )
            
            jsonl_out_file = None
            
            # Find the most recent .jsonl.out file
            latest_time = 0
            for obj in response.get('Contents', []):
                key = obj['Key']
                if key.endswith('.jsonl.out'):
                    if obj['LastModified'].timestamp() > latest_time:
                        latest_time = obj['LastModified'].timestamp()
                        jsonl_out_file = key
            
            if not jsonl_out_file:
                logger.error(f"No .jsonl.out file found in bucket {bucket_name} with prefix {s3_prefix}")
                return None
            
            # Download the file
            output_file = "downloaded_results.jsonl.out"
            self.s3_client.download_file(
                bucket_name,
                jsonl_out_file,
                output_file
            )
            
            logger.info(f"Successfully downloaded file to: {output_file}")
            return output_file
        except ClientError as e:
            logger.error(f"Error downloading batch results: {e}")
            return None

    def prepare_batch_prompt(self, text: str) -> str:
        """Prepare the prompt for a single chunk."""
        return (
            "You are analyzing the following text from a patient's record:\n\n"
            f"{text}\n\n"
            "Answer these questions in JSON format with exactly the following keys and structure:\n\n"
            "{\n"
            '  "patient_pregnant": "true" or "false",\n'
            '  "patient_pregnant_cot": "string explanation of your chain of thought of how arrived at your conclusion",\n'
            '  "recent_travel_history": {\n'
            '    "true_false": "true" or "false",\n'
            '    "where": "string",\n'
            '    "when": "string",\n'
            '    "cot": "string explanation of your chain of thought of how arrived at your conclusion"\n'
            "  },\n"
            '  "occupation": {\n'
            '    "true_false": "true" or "false",\n'
            '    "job": "string",\n'
            '    "cot": "string explanation of your chain of thought of how arrived at your conclusion"\n'
            "  }\n"
            "}\n\n"
            'For each field, if the text does not indicate any specific information, return "false" for the boolean value '
            "and an empty string for the text fields. Do not add any extra keys. I MUST be able to call json.loads() "
            "and json.dump() on your response (i.e. must be valid JSON). Do not include any additional preamble, just simply output the JSON mappings"
        )

    def generate_batch_jsonl(self, prompts: List[str], filename: str = "batch_prompts.jsonl") -> Dict[str, int]:
        """Generate JSONL file for batch inference and map record IDs to indices."""
        logger.info(f"Generating batch JSONL file: {filename}")
        record_map = {}  # Maps record ID to original index
        
        with open(filename, 'w') as f:
            # Add real prompts
            for i, prompt in enumerate(prompts):
                record_id = f"prompt_{i}_{int(time.time())}"
                record_map[record_id] = i
                
                record = {
                    "recordId": record_id,
                    "modelInput": {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 4000,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": prompt
                                    }
                                ]
                            }
                        ]
                    }
                }
                
                f.write(json.dumps(record) + '\n')
            
            # Add dummy records to meet minimum requirement of 100
            if len(prompts) < 100:
                dummy_prompt = self.prepare_batch_prompt("Empty placeholder record")
                for j in range(len(prompts), 100):
                    dummy_id = f"dummy_{j}_{int(time.time())}"
                    # Don't add dummy records to the map - we'll ignore their results
                    
                    dummy_record = {
                        "recordId": dummy_id,
                        "modelInput": {
                            "anthropic_version": "bedrock-2023-05-31",
                            "max_tokens": 4000,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": dummy_prompt
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                
                    f.write(json.dumps(dummy_record) + '\n')
                
                logger.info(f"Generated {len(prompts)} real prompts plus {100-len(prompts)} dummy prompts in {filename}")
            else:
                logger.info(f"Generated {len(prompts)} prompts in {filename}")
        
        return record_map

    def parse_batch_results(self, result_file: str, record_map: Dict[str, int]) -> Dict[int, Dict[str, Any]]:
        """Parse batch results and map them back to original indices."""
        logger.info(f"Parsing batch results from {result_file}")
        results = {}
        
        with open(result_file, 'r') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    record_id = record["recordId"]
                    
                    # Only process records in our map (ignore dummy records)
                    original_index = record_map.get(record_id)
                    if original_index is not None:
                        model_output = record.get("modelOutput", {})
                        content = model_output.get("content", [])
                        
                        if content and isinstance(content, list) and len(content) > 0:
                            response_text = content[0].get("text", "{}")
                            
                            try:
                                response_json = json.loads(response_text)
                                results[original_index] = response_json
                            except json.JSONDecodeError:
                                logger.warning(f"Could not parse JSON from response for record {record_id}\n Record: {response_json}")
                                results[original_index] = {}
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Error parsing result line: {e}")
        
        return results

    def process_texts_individually(self, texts: List[str], token_counter: TokenCounter) -> Dict[int, Dict[str, Any]]:
        """Process texts using direct API calls instead of batch processing."""
        logger.info(f"Processing {len(texts)} texts using direct API calls")
        results = {}
        
        for i, text in enumerate(texts):
            try:
                # Prepare prompt
                prompt = self.prepare_batch_prompt(text)
                token_counter.add_input(prompt)
                
                # Prepare request body
                request_body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt
                                }
                            ]
                        }
                    ]
                })
                
                # Call the LLM directly using existing function
                logger.info(f"Processing text {i+1}/{len(texts)} using direct API call")
                response = invoke_llm(request_body)
                
                # Parse response
                response_body = json.loads(response['body'].read().decode('utf-8'))
                if 'content' in response_body and len(response_body['content']) > 0:
                    response_text = response_body['content'][0]['text']
                    token_counter.add_output(response_text)
                    
                    # Parse JSON from response text
                    try:
                        response_json = json.loads(response_text)
                        results[i] = response_json
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse JSON from response for text {i}")
                        results[i] = {}
                else:
                    logger.warning(f"Empty or invalid response for text {i}")
                    results[i] = {}
                    
            except Exception as e:
                logger.error(f"Error processing text {i}: {str(e)}")
                results[i] = {}
        
        return results

    def batch_process_texts(self, texts: List[str], bucket_name: str, 
                          max_batch_size: int = 50) -> tuple[Dict[int, Dict[str, Any]], TokenCounter]:
        """
        Process multiple text segments using batch inference or direct API calls if under minimum batch size.
        
        Args:
            texts: List of text segments to process
            bucket_name: S3 bucket for batch processing
            max_batch_size: Maximum batch size
            
        Returns:
            Dictionary mapping original indices to results and a token counter
        """
        token_counter = TokenCounter()
        all_results = {}
        
        # If fewer than 100 total texts, use direct API calls instead of batch
        if len(texts) < 100:
            logger.info(f"Only {len(texts)} texts to process, using direct API calls instead of batch processing")
            all_results = self.process_texts_individually(texts, token_counter)
        else:
            # Create IAM role for batch processing
            role_name = f"bedrock-batch-role-{int(time.time())}"
            try:
                role_arn = self.create_iam_role(role_name, bucket_name)
            except Exception as e:
                logger.error(f"Error creating IAM role: {e}")
                raise
            
            # Process in batches
            for batch_start in range(0, len(texts), max_batch_size):
                batch_end = min(batch_start + max_batch_size, len(texts))
                current_batch = texts[batch_start:batch_end]
                
                logger.info(f"Processing batch {batch_start//max_batch_size + 1}: segments {batch_start} to {batch_end-1}")
                
                # Prepare prompts
                prompts = []
                for text in current_batch:
                    prompt = self.prepare_batch_prompt(text)
                    token_counter.add_input(prompt)
                    prompts.append(prompt)
                
                # Generate batch JSONL
                batch_file = f"batch_prompts_{batch_start}.jsonl"
                record_map = self.generate_batch_jsonl(prompts, batch_file)
                
                # Upload to S3
                input_key = f"input/{Path(batch_file).name}"
                self.upload_file_to_s3(batch_file, bucket_name, input_key)
                
                # Create and run batch job
                job_name = f"text-analysis-batch-{int(time.time())}"
                input_location = f"s3://{bucket_name}/{input_key}"
                output_location = f"s3://{bucket_name}/output/"
                
                job_id = self.create_batch_inference_job(
                    job_name, 
                    input_location, 
                    output_location, 
                    role_arn
                )
                
                final_status = self.monitor_job_status(job_id)
                
                # Process batch results
                if final_status == 'COMPLETED':
                    result_file = self.download_batch_results(bucket_name)
                    
                    if result_file:
                        batch_results = self.parse_batch_results(result_file, record_map)
                        
                        # Add to token counter and merge results
                        for idx, result in batch_results.items():
                            # Add original index offset
                            original_idx = batch_start + idx
                            all_results[original_idx] = result
                            
                            # Estimate output tokens
                            result_text = json.dumps(result)
                            token_counter.add_output(result_text)
                else:
                    logger.error(f"Batch job failed with status: {final_status}")
                    # Fall back to individual processing for this batch
                    logger.info(f"Falling back to direct API calls for batch {batch_start} to {batch_end-1}")
                    batch_results = self.process_texts_individually(current_batch, token_counter)
                    
                    # Merge results
                    for idx, result in batch_results.items():
                        original_idx = batch_start + idx
                        all_results[original_idx] = result
        
        # Print token usage metrics
        metrics = token_counter.get_metrics()
        logger.info(f"Token usage metrics:")
        logger.info(f"  - Input tokens: {metrics['input_tokens']}")
        logger.info(f"  - Output tokens: {metrics['output_tokens']}")
        logger.info(f"  - Total tokens: {metrics['total_tokens']}")
        
        return all_results, token_counter


def ask_llm_additional_questions_batch(text_segments: List[Dict[str, Any]], 
                                       bucket_name: str = "ryan-bedrock-batch-analysis",
                                       max_batch_size: int = 50) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Batch version of ask_llm_additional_questions that processes multiple text segments at once.
    
    Args:
        text_segments: List of chunk dictionaries with 'text' keys
        bucket_name: S3 bucket for batch processing
        max_batch_size: Maximum batch size
        
    Returns:
        Updated chunks with LLM answers and token usage metrics
    """
    # Create batch processor
    batch_processor = BedrockBatch()
    
    # Extract text from each segment
    texts = [segment.get("text", "") for segment in text_segments if segment.get("text")]
    
    # Process texts in batches
    results, token_counter = batch_processor.batch_process_texts(
        texts=texts,
        bucket_name=bucket_name,
        max_batch_size=max_batch_size
    )
    
    # Update original text segments with results
    for i, segment in enumerate(text_segments):
        if i in results:
            segment["llm_answers"] = results[i]
        else:
            segment["llm_answers"] = {}

    end_time = time.time()
    time_delta = end_time - start_time
    logger.info(f"Elapsed time: {time_delta:.6f} seconds ({time_delta/60:.4f} minutes)")
    return text_segments, token_counter.get_metrics()