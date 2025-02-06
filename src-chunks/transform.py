import json
from typing import Any

from bedrock import invoke_llm
from lxml import etree  # type: ignore
from vectoring import SCHEMA_TYPE


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
    with open(f"assets/{SCHEMA_TYPE}_schema.json", "r") as f:
        schema = json.load(f)
    return schema["properties"][category_name]


def llm_transform_data_to_json(data: str, schema: dict[str, Any]) -> dict[str, Any]:
    """
    takes a table xml string and returns a json object
    """
    prompt = "You are going to be given data. You need to transform this data into a JSON object. The JSON object should follow the following schema: "
    prompt += json.dumps(schema, indent=2)
    prompt += "\n\n"
    prompt += "Table:\n"
    table = transform_text_to_xml(data)
    prompt += table
    prompt += "\n\nTransform the data into a JSON object that follows the schema above. Return the JSON table inside th XML tags <table>...</table>."

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

    response_table = response_text.split("<table>")[1].split("</table>")[0]
    try:
        j = json.loads(response_table)
    except json.JSONDecodeError:
        with open("out/error.txt", "w") as f:
            f.write(response_text)
        raise Exception("Error decoding JSON")
    return j


def etree_transform_data_to_json(element: etree.Element) -> dict[str, Any]:  # type: ignore
    """
    transform a etree.Element to a json object, including attributes
    """
    json_data = {}
    for child in element:  # type: ignore
        if len(child) > 0:  # type: ignore
            json_data[child.tag[16:]] = etree_transform_data_to_json(child)  # type: ignore
        else:
            json_data[child.tag[16:]] = child.text  # type: ignore

        for attr_name, attr_value in child.attrib.items():  # type: ignore
            json_data[child.tag[16:] + "_" + attr_name] = attr_value  # type: ignore

    return json_data  # type: ignore
