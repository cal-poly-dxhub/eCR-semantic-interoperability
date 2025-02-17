import json
import random
from datetime import datetime
import string

def generate_record_id():
    """Generate an 11-character alphanumeric record ID. Guaranteed to be unique."""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')  # Include microseconds
    # Take last 6 digits of timestamp including microseconds
    time_part = timestamp[-6:]
    # Generate 1 random character to ensure uniqueness
    random_char = random.choice(string.ascii_uppercase + string.digits)
    return f"MATH{time_part}{random_char}"

def generate_math_problems(num_problems=200):
    """Generate specified number of math addition problems."""
    problems = []
    
    for _ in range(num_problems):
        # Generate random numbers between 1 and 15600
        x = random.randint(1, 15600)
        y = random.randint(1, 15600)
        
        # Create the question text
        question = f"What is {x} + {y}?"
        
        # Create the record structure
        record = {
            "recordId": generate_record_id(),
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
        problems.append(record)
    
    return problems

def write_jsonl(problems, filename="math_problems.jsonl"):
    """Write problems to a JSONL file."""
    with open(filename, 'w') as f:
        for problem in problems:
            json_str = json.dumps(problem)
            f.write(json_str + '\n')

def main():
    # Generate 200 math problems
    problems = generate_math_problems(200)
    
    # Write to JSONL file
    output_file = "math_problems.jsonl"
    write_jsonl(problems, output_file)
    print(f"Generated {len(problems)} math problems in {output_file}")
    
    # Print a sample problem to verify format
    print("\nSample problem format:")
    print(json.dumps(problems[0], indent=2))

if __name__ == "__main__":
    main()
