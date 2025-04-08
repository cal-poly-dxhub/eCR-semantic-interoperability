import json
import os
import logging
import boto3
from src.embed import process_embed
from src.test import process_test_file

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

# Environment variable for destination bucket name
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET")

def lambda_handler(event, context):
    """
    Lambda function handler that processes files uploaded to S3.
    Downloads the file, processes it, and uploads the result to the output bucket.
    """
    try:
        # Parse S3 event to get the bucket and key
        record = event["Records"][0]
        source_bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        
        logger.info(f"Processing file {key} from bucket {source_bucket}")
        
        # Download the file from S3 to Lambda's /tmp directory
        local_file_path = f"/tmp/{os.path.basename(key)}"
        s3.download_file(source_bucket, key, local_file_path)
        
        # Run the embedding workflow (if needed)
        embedded_file_path = process_embed(local_file_path)
        logger.info(f"Embedded file saved to {embedded_file_path}")
        # Then run the test workflow on the (possibly) updated file
        result_json = process_test_file(local_file_path)
        logger.info(f"Test results saved to {result_json}")
        
        # Check if output bucket is configured
        if not OUTPUT_BUCKET:
            raise ValueError("OUTPUT_BUCKET environment variable not set. Cannot continue.")
            
        # Write the resulting JSON back to the output S3 bucket
        print("key before replace: ", key)
        output_key = key.replace(".xml", ".json")
        print(f"Output key: {output_key}")
        s3.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=output_key,
            Body=json.dumps(result_json, indent=2),
            ContentType="application/json"
        )
        
        logger.info(f"Successfully uploaded result to {OUTPUT_BUCKET}/{output_key}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Processing complete", 
                "source": f"{source_bucket}/{key}",
                "output": f"{OUTPUT_BUCKET}/{output_key}"
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }