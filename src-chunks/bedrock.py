import json
import os
import time
from typing import Any

import boto3

embedding_model_id = "amazon.titan-embed-text-v2:0"
llm_model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
client = boto3.client(  # type: ignore
    "bedrock-runtime",
    region_name="us-west-2",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    # config=boto3.config.Config(retries={"max_attempts": 10}),  # type: ignore
)

bedrock = boto3.client(  # type: ignore
    "bedrock",
    region_name="us-west-2",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    # config=boto3.config.Config(retries={"max_attempts": 10}),  # type: ignore
)


def test_bedrock():
    response = bedrock.list_foundation_models()  # type: ignore
    summarries = response["modelSummaries"]  # type: ignore
    for model in summarries:  # type: ignore
        print(model["modelName"], "| model id:", model["modelId"])  # type: ignore


def invoke_llm(body: Any, modelId: str = llm_model_id, retries: int = 0) -> Any:
    print("invoking llm, retries:", retries)
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
    print("invoking embedding, retries:", retries)
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


def ask_llm_additional_questions(text: str) -> dict[str, Any]:
    """
    Calls the LLM to answer the three questions about pregnancy, travel history, and occupation.
    Returns a dict in JSON format.
    """
    prompt = (
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
        "and an empty string for the text fields. Do not add any extra keys."
    )
    request_body: dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
    }
    response = invoke_llm(json.dumps(request_body), llm_model_id)
    response_text = json.loads(response["body"].read())["content"][0]["text"]
    try:
        return json.loads(response_text)
    except Exception:
        return {}


if __name__ == "__main__":
    test_bedrock()
