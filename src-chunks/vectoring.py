import json
import re
from typing import Any


from bedrock import invoke_embedding, invoke_llm


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

    response = invoke_llm(request_body, "amazon.nova-lite-v1:0")
    response_body = json.loads(response["body"].read())  # type: ignore
    response_text = response_body["content"][0]["text"]
    match = re.search(r"<category>(.*?)</category>", response_text)
    if match:
        return match.group(1)
    return ""


def get_bedrock_embeddings(data: dict[str, Any]) -> dict[str, Any]:
    native_request = {"inputText": data["text"]}
    request = json.dumps(native_request)

    response = invoke_embedding(request)
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