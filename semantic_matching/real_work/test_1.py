import json
from pathlib import Path
import random
import time
from bedrock_client import BedrockClient
from typing import List

def main():
    # Initialize client
    client = BedrockClient(
        region='us-west-2',
        account_id='your-account-id',
        profile_name='public-records-profile'
    )

    # Test single LLM call
    question = "What is the capital of Cambodia?"
    response = client.single_llm_call(question)
    print(f"Single LLM Response: {json.dumps(response, indent=2)}")

if __name__ == "__main__":
    main()