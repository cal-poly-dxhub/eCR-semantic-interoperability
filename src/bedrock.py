import json
import os
import time
from typing import Any
from dotenv import load_dotenv

load_dotenv()


import boto3

embedding_model_id = "amazon.titan-embed-text-v2:0"
llm_model_id = os.getenv("NOVA_PRO_INFERENCE_PROFILE_ARN")
lite_model_id = os.getenv("NOVA_LITE_INFERENCE_PROFILE_ARN")

print(f"Using LLM model ID: {llm_model_id}")
print(f"Using Lite model ID: {lite_model_id}")
client = boto3.client(  # type: ignore
    "bedrock-runtime",
    region_name="us-west-2",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
    # config=boto3.config.Config(retries={"max_attempts": 10}),  # type: ignore
)
bedrock = boto3.client(  # type: ignore
    "bedrock",
    region_name="us-west-2",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
    # config=boto3.config.Config(retries={"max_attempts": 10}),  # type: ignore
)


def test_bedrock():
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token = (os.getenv("AWS_SESSION_TOKEN"),)
    print("aws_access_key_id:", aws_access_key_id)
    print("aws_secret_access_key:", aws_secret_access_key)
    print("aws_session_token:", aws_session_token)
    response = bedrock.list_foundation_models()  # type: ignore
    summarries = response["modelSummaries"]  # type: ignore
    for model in summarries:  # type: ignore
        print(model["modelName"], "| model id:", model["modelId"])  # type: ignore


def invoke_llm(body: Any, modelId: str, retries: int = 0) -> Any:
    # print("invoking llm, retries:", retries)
    print(f"Invoking model: {modelId}")
    try:
        return client.invoke_model(modelId=modelId, body=body)  # type: ignore
    except Exception as e:
        if "(ThrottlingException)" in str(e) and retries < 3:
            time.sleep((retries + 1) * 8)
            return invoke_llm(
                body,
                modelId,
                retries + 1,
            )
        
        print(e)
        exit(1)


def invoke_embedding(body: Any, retries: int = 0) -> Any:
    # print("invoking embedding, retries:", retries)
    try:
        return client.invoke_model(modelId=embedding_model_id, body=body)  # type: ignore
    except Exception as e:
        if "(ThrottlingException)" in str(e) and retries < 3:
            time.sleep((retries + 1) * 8)
            return invoke_embedding(
                body,
                retries + 1,
            )
        print(e)
        exit(1)

def llm_inference(text: str) -> str:
    """
    llm inference on 3 questions:
    1. is the patient pregnant?
    2. recent travel history?
    3. patient's occupation?
    """
    prompt = (
        "You are analyzing the following text from a patient's record:\n\n"
        f"{text}\n\n"
        "Answer these questions in XML format with the following keys and structure:\n\n"
        '<pregnancy pregnant="true" or "false" or "null">\n'
        "<reasoning>explaination of your chain of thought for this record</reasoning>\n"
        "</pregnancy>\n"
        '<travel status="true" or "false" or "null">\n'
        "<recent_travel>\n"
        "<reasoning>explaination of your chain of thought for this record</reasoning>\n"
        "<location>string (in City,ST format)</location>\n"
        "<date>string (in MM/DD/YYYY format)</date>\n"
        "</recent_travel>\n"
        "... more recent travels if any\n"
        "</travel>\n"
        '<occupation employed="true" or "false" or "null">\n'
        "<reasoning>explaination of your chain of thought for this record</reasoning>\n"
        "<job>string</job>\n"
        "</occupation>\n"
        'For each field, if the text does not indicate any specific information, return "null" for the boolean value '
        "and an empty string for the text fields. Do not add any extra keys."
    )
    request_body: dict[str, Any] = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        # "max_tokens": 500,
    }

    response = invoke_llm(json.dumps(request_body), llm_model_id)
    response_body = json.loads(response["body"].read())
    # Handle Nova model response format
    if "output" in response_body:
        response_text = response_body["output"]["message"]["content"][0]["text"]
    else:
        response_text = response_body["content"][0]["text"]
    
    response_vals = (
        response_text,
        json.loads(
            response["ResponseMetadata"]["HTTPHeaders"][
                "x-amzn-bedrock-input-token-count"
            ]
        ),
        json.loads(
            response["ResponseMetadata"]["HTTPHeaders"][
                "x-amzn-bedrock-output-token-count"
            ]
        ),
    )
    try:
        return response_vals
    except Exception:
        return None  # type: ignore


if __name__ == "__main__":
    test_bedrock()
