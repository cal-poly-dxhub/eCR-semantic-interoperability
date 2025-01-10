from typing import Any, Union
from xml.etree import ElementTree as ET

import lxml  # type: ignore # parser for bs4


def get_direct_text(element: Any) -> str:
    return "".join([t for t in element.contents if isinstance(t, str)]).strip()


def xml_to_dict(element: Any) -> dict[str, Union[str, list[dict[str, Any]]]]:
    """
    convert an XML element to a dictionary
    """
    data: Any = {}
    if element.attrs:
        data.update(element.attrs)

    text = get_direct_text(element)
    if text:
        data["content"] = text

    children = [child for child in element.children if child.name]
    if children:
        for child in children:
            child_content = xml_to_dict(child)
            if child.name in data:
                if not isinstance(data[child.name], list):
                    data[child.name] = [data[child.name]]
                data[child.name].append(child_content)
            else:
                data[child.name] = child_content

    return data


def extract_texts(
    data: dict[str, Union[str, list[dict[str, Any]]]]
) -> list[dict[str, Union[str, list[dict[str, Any]]]]]:
    """
    get all text objects from a dictionary
    """
    texts: list[dict[str, Union[str, list[dict[str, Any]]]]] = []
    for key, value in data.items():
        if key == "text":
            texts.append(data)
        elif isinstance(value, list):
            for item in value:
                texts.extend(extract_texts(item))
        elif isinstance(value, dict):
            texts.extend(extract_texts(value))

    return texts


def extract_tables(
    data: dict[str, Union[str, list[dict[str, Any]]]]
) -> list[dict[str, Union[str, list[dict[str, Any]]]]]:
    """
    get all table objects from a dictionary
    """
    tables: list[dict[str, Union[str, list[dict[str, Any]]]]] = []
    for key, value in data.items():
        if key == "table":
            tables.append(data)
        elif isinstance(value, list):
            for item in value:
                tables.extend(extract_tables(item))
        elif isinstance(value, dict):
            tables.extend(extract_tables(value))

    return tables


def extract_text_and_tables(filename: str) -> list[Any]:
    tree = ET.parse(filename)
    root = tree.getroot()
    elements: list[Any] = []
    for element in root.iter():
        if (
            element.tag == "{urn:hl7-org:v3}text"
            or element.tag == "{urn:hl7-org:v3}table"
        ):
            element_dict = {
                "tag": element.tag,
                "text": element.text,
                "attributes": element.attrib,
            }
            elements.append(element_dict)

    return elements
