import json
import random
import string

# Function to generate a random 11-character alphanumeric string
def generate_record_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=11))

# Example model input for Anthropic Claude 3 Haiku model
def generate_model_input():
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Summarize the following call transcript: Hi John, this is Jane. I'm calling to follow up on the proposal we discussed last week. Can you provide an update on the status? Thanks." 
                    }
                ]
            }
        ]
    }

# Generate 150 queries with the same model input
num_queries = 150
queries = []

for _ in range(num_queries):
    queries.append({
        "recordId": generate_record_id(),
        "modelInput": generate_model_input()
    })

# Write to a .jsonl file
output_file = "test_queries.jsonl"

with open(output_file, "w") as file:
    for query in queries:
        file.write(json.dumps(query) + "\n")

print(f"Generated {num_queries} queries in {output_file}")
