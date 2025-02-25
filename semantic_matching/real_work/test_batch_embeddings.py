# test_batch_embeddings.py
import json
import os
import time
import numpy as np
from typing import List, Dict
from bedrock_client import BedrockClient
from pathlib import Path
import random

def generate_test_texts() -> List[str]:
    """Generate 100 test texts with 1 correct answer and 99 random texts"""
    countries = {
        "France": "Paris",
        "Germany": "Berlin",
        "Japan": "Tokyo",
        "Australia": "Canberra",
        "Brazil": "Brasília"
    }
    
    # Create correct Q&A pair
    country = random.choice(list(countries.keys()))
    capital = countries[country]
    correct_text = f"The capital of {country} is {capital}."
    
    # Generate random texts
    random_texts = [
        f"Color mix: {random.choice(['red', 'blue', 'green'])} and {random.choice(['yellow', 'black', 'white'])}",
        f"Random string: {''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=10))}",
        f"Number sequence: {'-'.join(map(str, random.sample(range(100), 5)))}",
        f"Science fact: {random.choice(['H2O', 'CO2', 'NaCl'])} is a chemical compound.",
        f"Historical year: {random.randint(1800, 2023)}"
    ]
    
    # Generate 99 random texts
    texts = [correct_text]
    for _ in range(99):
        texts.append(random.choice(random_texts))
    
    random.shuffle(texts)
    return texts, correct_text

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def main():
    # Initialize client
    client = BedrockClient(
        region='us-west-2',
        account_id='REMOVED_ID',
        profile_name='public-records-profile'
    )
    
    # Generate test data
    texts, correct_text = generate_test_texts()
    print(f"Generated {len(texts)} texts (1 correct: '{correct_text}')")
    
    # Create batch embeddings JSONL
    batch_file = "embedding_batch_test.jsonl"
    client.generate_embeddings_batch_jsonl(texts, batch_file)
    
    # Setup S3
    bucket_name = "batch-embeddings-test-bucket"
    input_key = f"input/{Path(batch_file).name}"
    
    # Upload to S3
    client.upload_file_to_s3(batch_file, bucket_name, input_key)
    
    # Create IAM role
    role_name = f"embedding-test-role-{int(time.time())}"
    role_arn = client.create_iam_role(role_name, bucket_name)
    
    # Create and run batch job
    job_name = f"embedding-test-job-{int(time.time())}"
    job_id = client.create_embeddings_batch_job(
        job_name=job_name,
        input_location=f"s3://{bucket_name}/{input_key}",
        output_location=f"s3://{bucket_name}/output/",
        role_arn=role_arn
    )
    
    # Monitor job
    status = client.monitor_job_status(job_id)
    if status != 'Completed':
        raise Exception(f"Batch job failed with status: {status}")
    
    # Download and parse results
    results_file = client.download_batch_results(bucket_name)
    batch_embeddings = client.parse_batch_embeddings(results_file)
    print(f"Parsed {len(batch_embeddings)} embeddings from batch job")
    
    # Generate single embedding for verification
    query = correct_text.split(' is ')[0] + " is?"
    single_embedding = client.generate_embeddings([query])[0]
    
    # Find most similar embedding from batch results
    similarities = []
    for record_id, embedding in batch_embeddings.items():
        sim = cosine_similarity(single_embedding, embedding)
        similarities.append((sim, record_id))
    
    # Get top match
    similarities.sort(reverse=True)
    top_sim, top_id = similarities[0]
    
    # Verify correct text is in top 5 matches
    results_file = "downloaded_results.jsonl.out"
    top_texts = []
    with open(results_file, 'r') as f:
        for line in f:
            record = json.loads(line)
            if record['recordId'] == top_id:
                top_text = record['modelInput']['texts'][0]
                print(f"\nTop match (similarity: {top_sim:.4f}): {top_text}")
                if top_text.startswith("The capital of"):
                    print("✅ Test passed - Correct capital question found in top results")
                else:
                    print("❌ Test failed - Correct answer not in top results")
                break

if __name__ == "__main__":
    main()