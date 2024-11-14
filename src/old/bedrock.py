import os
from typing import Dict

import boto3  # type: ignore
from dotenv import load_dotenv

load_dotenv()
client = boto3.client(  # type: ignore
    "bedrock-runtime",
    region_name="us-west-2",
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
)
model_id = "anthropic.claude-3-sonnet-20240229-v1:0"


# test
# test_message = [{"role": "user", "content": [{"text": "tell me a joke"}]}]  # type: ignore
# response = client.converse(  # type: ignore
#     modelId=model_id,
#     messages=test_message,
#     # inferenceConfig={"maxTokens": 1024, "temperature": 1.0, "topP": 0.9},
# )


def json_to_xml(data: Dict[str, str]) -> str:
    """
    Convert a dictionary to an XML string.
    """
    xml = ""
    for key, value in data.items():
        if isinstance(value, dict):
            xml += f"<{key}>{json_to_xml(value)}</{key}>"
        else:
            xml += f"<{key}>{value}</{key}>"
    return xml
