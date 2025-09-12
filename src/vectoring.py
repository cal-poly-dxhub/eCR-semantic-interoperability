import json
import re
from typing import Any

from bedrock import invoke_embedding, invoke_llm, lite_model_id

# choose schema type here
SCHEMA_TYPE = "hl7"


def get_categories_from_file(type: str) -> list[str]:
    with open(f"src/assets/{type}_schema.json", "r") as f:
        schema = json.load(f)
    categories = schema["properties"]
    return list(categories.keys())


def get_category(text: str) -> str:
    categories = get_categories_from_file(SCHEMA_TYPE)
    prompt = """ You will be given a block of text and a list of categories. Your task is to choose the single most appropriate category that best describes the text.

        Important rules:
        You must choose one category from the provided list.
        You cannot leave the category blank.
        You cannot answer "None", "N/A", or make up your own category.
        Even if the text does not perfectly match any category, select the one that is closest in meaning or context.
        The available categories are:"""

    for i, c in enumerate(categories):
        prompt += f"{i+1}. {c}, "
    prompt = prompt[:-2] + ".\n\n"
    prompt += "Text block:\n"
    prompt += text
    prompt += "\n\nWhich category best describes the text? Please respond with the name of the category in XML format, e.g. <category>category_name</category>."

    request_body = {  # type: ignore
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        # "max_tokens": 1000,
    }

    response = invoke_llm(
        json.dumps(request_body), lite_model_id
    )
    response_body = json.loads(response["body"].read())  # type: ignore
    # Handle Nova model response format
    if "output" in response_body:
        response_text = response_body["output"]["message"]["content"][0]["text"]
    else:
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
    e = get_bedrock_embeddings(data)
    category = get_category(data["text"])
    e["xml"] = data["xml"]
    e["category"] = category
    return e
