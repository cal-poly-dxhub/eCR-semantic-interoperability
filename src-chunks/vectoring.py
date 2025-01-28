import json
import os
import re
import time
from typing import Any

import boto3
import torch
from transformers import BertModel, BertTokenizer  # type: ignore

embedding_model_id = "amazon.titan-embed-text-v2:0"
llm_model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
client = boto3.client(  # type: ignore
    "bedrock-runtime",
    region_name="us-west-2",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

bedrock = boto3.client(  # type: ignore
    "bedrock",
    region_name="us-west-2",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)


def test_bedrock():
    response = bedrock.list_foundation_models()  # type: ignore
    summarries = response["modelSummaries"]  # type: ignore
    for model in summarries:  # type: ignore
        print(model["modelName"], "| model id:", model["modelId"])  # type: ignore


def embed_text(data: dict[str, Any]) -> dict[str, Any]:
    # bedrock
    return get_bedrock_embeddings(data)

    # local
    # return get_biobert_embeddings(data)


def get_all_categories() -> list[str]:
    with open("assets/ecr_schema.json", "r") as f:
        schema = json.load(f)
    categories = schema["properties"]
    return list(categories.keys())


def get_category(text: str) -> str:
    categories = get_all_categories()
    prompt = "You are going to be given a block of text and a list of categories. You need to select the category that best describes the text. The categories are: "
    for i, c in enumerate(categories):
        prompt += f"{i+1}. {c}, "
    prompt = prompt[:-2] + ".\n\n"
    prompt += "Text block:\n"
    prompt += text
    prompt += "\n\nWhich category best describes the text? Please respond with the name of the category in XML format, e.g. <category>category_name</category>."

    request_body = {  # type: ignore
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
    }

    response = client.invoke_model(modelId=llm_model_id, body=json.dumps(request_body))  # type: ignore
    response_body = json.loads(response["body"].read())  # type: ignore
    print("got response, waiting 10 seconds")
    time.sleep(10)
    response_text = response_body["content"][0]["text"]
    match = re.search(r"<category>(.*?)</category>", response_text)
    if match:
        return match.group(1)
    return ""


def get_bedrock_embeddings(data: dict[str, Any]) -> dict[str, Any]:
    native_request = {"inputText": data["text"]}
    request = json.dumps(native_request)

    response = client.invoke_model(modelId=embedding_model_id, body=request)  # type: ignore
    model_response = json.loads(response["body"].read())  # type: ignore

    embedding = model_response["embedding"]
    # input_token_count = model_response["inputTextTokenCount"]
    category = get_category(data["text"])

    r: dict[str, Any] = {
        "chunk_id": data["chunk_id"],
        "path": data["path"],
        "chunk_size": data["chunk_size"],
        "category": category,
        "embedding": embedding,
    }

    return r


# LOCAL


def get_biobert_embeddings(data: dict[str, Any]) -> dict[str, Any]:
    tokenizer = BertTokenizer.from_pretrained("dmis-lab/biobert-v1.1")  # type: ignore
    model = BertModel.from_pretrained("dmis-lab/biobert-v1.1")  # type: ignore
    # Tokenize the text
    text: str = data["text"]
    inputs = tokenizer(  # type: ignore
        text, return_tensors="pt", truncation=True, padding=True, max_length=512
    )

    # Get the embeddings from BioBERT
    with torch.no_grad():  # type: ignore
        outputs = model(**inputs)  # type: ignore

    # The embeddings are in outputs[0], which is the hidden states of the model
    # You can use the last hidden state or pooler_output
    embeddings = outputs.last_hidden_state.mean(  # type: ignore
        dim=1
    ).squeeze()  # Using mean of token embeddings

    embeddings = embeddings.tolist()  # type: ignore
    r = {  # type: ignore
        "chunk_id": data["chunk_id"],
        "path": data["path"],
        "chunk_size": data["chunk_size"],
        # TODO: add category
        "category": "",
        "embedding": embeddings,
    }

    return r  # type: ignore


if __name__ == "__main__":
    test_bedrock()
