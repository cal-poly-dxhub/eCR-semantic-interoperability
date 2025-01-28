import json
import os
import time
from typing import Any

import boto3

llm_model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
client = boto3.client(  # type: ignore
    "bedrock-runtime",
    region_name="us-west-2",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)


def transform_text_to_xml(text: str) -> str:
    """
    takes a text string and returns xml table
    """
    lines = text.split("\n")
    table = "<table>"
    for line in lines:
        table += "<tr>"
        cells = line.split("\t")
        for cell in cells:
            table += f"<td>{cell}</td>"
        table += "</tr>"
    table += "</table>"
    return table


def get_matching_schema(filepath: str, chunk_id: int) -> dict[str, Any]:
    """
    returns the schema for the category that the chunk belongs to
    """
    with open(filepath, "r") as f:
        d = json.load(f)
    category_name = d[chunk_id]["category"]
    with open("assets/ecr_schema.json", "r") as f:
        schema = json.load(f)
    return schema["properties"][category_name]


def transform_table_to_json(text: str, schema: dict[str, Any]) -> dict[str, Any]:
    """
    takes a table xml string and returns a json object
    """
    prompt = "You are going to be given a table in XML format. You need to transform this table into a JSON object. The JSON object should follow the following schema: "
    prompt += json.dumps(schema, indent=2)
    prompt += "\n\n"
    prompt += "Table:\n"
    table = transform_text_to_xml(text)
    prompt += table
    prompt += "\n\nTransform this table into a JSON object that follows the schema above. Return the JSON table inside th XML tags <table>...</table>."

    request_body = {  # type: ignore
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
    }

    time.sleep(10)
    response = client.invoke_model(modelId=llm_model_id, body=json.dumps(request_body))  # type: ignore
    response_body = json.loads(response["body"].read())  # type: ignore
    response_text = response_body["content"][0]["text"]

    response_table = response_text.split("<table>")[1].split("</table>")[0]
    try:
        j = json.loads(response_table)
    except json.JSONDecodeError:
        with open("out/error.txt", "w") as f:
            f.write(response_text)
        raise Exception("Error decoding JSON")
    return j
