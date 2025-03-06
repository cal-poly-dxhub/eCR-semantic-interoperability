import json
import re
import sys
from typing import Any
from xml.etree import ElementTree as ET

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


def attrib_nesting_helper(element: etree.Element) -> dict[str, Any]:  # type: ignore
    """
    helper function to transform a etree.Element's attributes to a json object, including attributes
    """
    json_data = {}
    for attr_name, attr_value in element.attrib.items():  # type: ignore
        json_data[attr_name] = attr_value  # type: ignore
    return json_data  # type: ignore


def etree_table_helper(element: etree.Element, headers: list[str] = []) -> dict[str, Any]:  # type: ignore
    """
    helper function to transform a etree.Element's table to a json array, including attributes
    """
    table_list = []
    for child in element:  # type: ignore
        if child.tag.endswith("colgroup"):  # type: ignore
            continue
        if child.tag.endswith("thead"):  # type: ignore
            for tr in child:  # type: ignore
                for _, cell in enumerate(tr):  # type: ignore
                    headers.append(cell.text)  # type: ignore
        if child.tag.endswith("tbody"):  # type: ignore
            for tr in child:  # type: ignore
                table_dict = {}
                for index, td in enumerate(tr):  # type: ignore
                    table_dict[headers[index]] = etree_transform_data_to_json(td)  # type: ignore
                table_list.append(table_dict)  # type: ignore

    return table_list  # type: ignore


def etree_text_helper(element: etree.Element) -> dict[str, Any]:  # type: ignore
    """
    helper function to transform a etree.Element's text to a json object, including attributes
    """
    json_data = {}
    for child in element:  # type: ignore
        if child.tag.endswith("table"):  # type: ignore
            json_data[child.tag[16:]] = etree_table_helper(child)  # type: ignore

        if len(child) > 0:  # type: ignore
            json_data[child.tag[16:]] = etree_transform_data_to_json(child)  # type: ignore

        else:
            if child.text is not None:  # type: ignore
                json_data[child.tag[16:]] = {  # type: ignore
                    ".text": child.text,  # type: ignore
                    **attrib_nesting_helper(child),  # type: ignore
                }  # type: ignore
            else:
                json_data[child.tag[16:]] = attrib_nesting_helper(child)  # type: ignore

    return json_data  # type: ignore


def etree_transform_data_to_json(element: etree.Element) -> dict[str, Any]:  # type: ignore
    """
    transform a etree.Element to a json object, including attributes
    """
    json_data = {}
    for child in element:  # type: ignore
        if child.tag.endswith("text"):  # type: ignore
            json_data[child.tag[16:]] = etree_text_helper(child)  # type: ignore

        # if child.tag.endswith("table"):  # type: ignore
        #     json_data[child.tag[16:]] = etree_table_helper(child)  # type: ignore

        elif len(child) > 0:  # type: ignore
            json_data[child.tag[16:]] = etree_transform_data_to_json(child)  # type: ignore

        else:
            if child.text is not None:  # type: ignore
                json_data[child.tag[16:]] = {  # type: ignore
                    "content": child.text,  # type: ignore
                    **attrib_nesting_helper(child),  # type: ignore
                }  # type: ignore
            else:
                json_data[child.tag[16:]] = attrib_nesting_helper(child)  # type: ignore

    return json_data  # type: ignore


def remove_xml_comments(tree: ET.ElementTree) -> ET.ElementTree:  # type: ignore
    """
    removes comments from an xml tree
    """
    # for elem in tree.iter():  # type: ignore
    #     print(str(elem.tag) + "\t\t" + str(type(elem)))
    #     if elem.tag.startswith("<!--"):  # type: ignore
    #         elem.clear()  # type: ignore

    return tree


def tree_to_string(tree: etree._Element) -> str:  # type: ignore
    """
    converts an xml tree to a string
    """
    s = etree.tostring(tree, pretty_print=True).decode("utf-8")  # type: ignore
    return re.sub("ns0:", "", s)  # type: ignore


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python transform.py <filepath>")
        exit(1)

    filepath = sys.argv[1]
    with open(filepath, "r") as f:
        parser = etree.XMLParser(remove_blank_text=True)  # type: ignore # To preserve line numbers
        tree = etree.parse(filepath, parser)  # type: ignore
    j = etree_transform_data_to_json(tree.getroot())  # type: ignore

    with open("out/transform.json", "w") as f:
        json.dump(j, f, indent=2)
