import os
from typing import Any

import boto3  # type: ignore
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()
client = boto3.client(  # type: ignore
    "bedrock-runtime",
    region_name="us-west-2",
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
)
claude_instant_v1 = "anthropic.claude-instant-v1"
claude_3_sonnet = "anthropic.claude-3-sonnet-20240229-v1:0"


def get_bedrock_response(prompt: str) -> str:
    conversation: Any = [{"role": "user", "content": [{"text": prompt}]}]
    try:
        response = client.converse(  # type: ignore
            modelId=claude_3_sonnet,
            messages=conversation,
            inferenceConfig={"maxTokens": 2048, "temperature": 0.0, "topP": 0.9},
        )
        response_text: Any = response["output"]["message"]["content"][0]["text"]
        with open("response.txt", "w") as f:
            f.write(response_text)
        return response_text

    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke '{claude_3_sonnet}'. Reason: {e}")
        exit(1)


# test
# test_message = [{"role": "user", "content": [{"text": "tell me a joke"}]}]  # type: ignore
# response = client.converse(  # type: ignore
#     modelId=model_id,
#     messages=test_message,
#     # inferenceConfig={"maxTokens": 1024, "temperature": 1.0, "topP": 0.9},
# )


def get_fhir_from_flat_json(flat_json: dict[str, str]) -> Any:
    """
    convert flat json to fhir json
    """
    # id = flat_json["id"]
    input_data = {"path": flat_json["path"], "value": flat_json["value"]}

    prompt = f"""Convert the following HL7 XML path-value pair into a valid FHIR JSON path.
                Input data:
                {input_data}
                Your output format is this:
                <thought>Your short internal thought process</thought>
                <path>The FHIR JSON path where this data belongs. Example: "Patient.name.given". If the data does not fit into a FHIR resource, leave this blank.</path>
                <reason>Your reasoning why this data belongs at your provided path.</reason>"""

    conversation: Any = [{"role": "user", "content": [{"text": prompt}]}]
    try:
        response = client.converse(  # type: ignore
            modelId=claude_3_sonnet,
            messages=conversation,
            inferenceConfig={"maxTokens": 1024, "temperature": 0.0, "topP": 0.9},
        )
        response_text: Any = response["output"]["message"]["content"][0]["text"]
        if (
            "<path>" not in response_text
            or "</path>" not in response_text
            or "<path></path>" in response_text
        ):
            return None
        return response_text.split("<path>")[1].split("</path>")[0]

    except ClientError as e:
        print(f"ERROR: Can't invoke '{claude_instant_v1}'. Reason: {e}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def json_to_xml(data: dict[str, str]) -> str:
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
