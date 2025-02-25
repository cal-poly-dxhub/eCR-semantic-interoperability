import json
from pathlib import Path
import random
import time
from bedrock_client import BedrockClient
from typing import List

def generate_color_questions() -> List[str]:
    colors = [
        "Red", "Blue", "Green", "Yellow", "Purple", "Orange", "Black", "White",
        "Pink", "Brown", "Gray", "Turquoise", "Silver", "Gold", "Copper",
        "Lime", "Navy", "Coral", "Fuchsia", "Olive", "Plum", "Salmon"
    ]
    
    questions = []
    for _ in range(100):
        color1 = random.choice(colors)
        color2 = random.choice(colors)
        questions.append(f"What color would you get if you mixed {color1} and {color2}?")
    
    return questions

def main():
    # Initialize client
    client = BedrockClient(
        region='us-west-2',
        account_id='REMOVED_ID',
        profile_name='public-records-profile'
    )

    # Test single LLM call
    question = "What is the capital of Cambodia?"
    response = client.single_llm_call(question)
    print(f"Single LLM Response: {json.dumps(response, indent=2)}")

    # Generate test questions
    questions = generate_color_questions()
    print(f"Generated {len(questions)} unique questions")

    # Create embeddings for these questions
    embeddings_file = "color_questions_embeddings.jsonl"
    client.generate_embeddings(questions, embeddings_file)
    
    # Test semantic search
    search_question = "What color is created by mixing Red and Blue?"
    results = client.semantic_search(search_question, embeddings_file)
    print("\nSemantic Search Results:")
    for text, score in results:
        print(f"Text: {text}, Similarity: {score:.4f}")

    # Set up batch inference
    bucket_name = "batchinferencebuckettestbucketfeb15"
    batch_file = "color_questions.jsonl"

    # Generate batch JSONL
    client.generate_batch_jsonl(questions, batch_file)
    
    # Upload file to S3 and run batch job
    input_key = f"input/{Path(batch_file).name}"
    client.upload_file_to_s3(batch_file, bucket_name, input_key)
    
    role_name = f"bedrock-batch-role-{int(time.time())}"
    role_arn = client.create_iam_role(role_name, bucket_name)
    
    job_name = f"color-questions-batch-{int(time.time())}"
    input_location = f"s3://{bucket_name}/{input_key}"
    output_location = f"s3://{bucket_name}/output/"
    
    job_id = client.create_batch_inference_job(job_name, input_location, output_location, role_arn)
    final_status = client.monitor_job_status(job_id)
    
    print(f"{final_status=}")
    if 'Complete' in final_status:
        print("\nBatch job completed successfully!")
        results = client.download_batch_results(bucket_name)
        print(f"Downloaded {len(results)} results from S3")
        print("\nSample Result:")
        if results:  # Add safety check
            sample_result = results[0]
            # Parse the result based on your needs
            print(json.dumps({
                "modelInput": sample_result.get("modelInput"),
                "modelOutput": sample_result.get("modelOutput")
            }, indent=2))
        else:
            print("No results found")


if __name__ == "__main__":
    main()
