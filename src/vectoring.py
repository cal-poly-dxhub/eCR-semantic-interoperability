import json
import re
from typing import Any

from bedrock import invoke_embedding, invoke_llm

# choose schema type between "hl7" and "ecr" (makedata golden template)
SCHEMA_TYPE = "hl7"


def get_categories_from_file(type: str) -> list[str]:
    with open(f"assets/{type}_schema.json", "r") as f:
        schema = json.load(f)
    categories = schema["properties"]
    return list(categories.keys())


def get_category(text: str) -> str:
    categories = get_categories_from_file(SCHEMA_TYPE)
    prompt = "You are going to be given a block of text and a list of categories. You need to select the category that best describes the text. The Category MUST NOT be blank, you must just a category. The categories are: "
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

    response = invoke_llm(
        json.dumps(request_body), "anthropic.claude-3-haiku-20240307-v1:0"
    )
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

    r: dict[str, Any] = {
        "chunk_id": data["chunk_id"],
        "path": data["path"],
        "chunk_size": data["chunk_size"],
        "embedding": embedding,
    }

    return r


def get_bedrock_embeddings_with_category(data: dict[str, Any]) -> dict[str, Any]:
    #print(f"getting embeddings for chunk: {data['chunk_id']}")
    e = get_bedrock_embeddings(data)
    category = get_category(data["text"])
    e["xml"] = data['xml']
    e["category"] = category
    #print(f"category: {category}")
    return e
