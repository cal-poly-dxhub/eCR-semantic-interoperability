import sys
from typing import Any

from lxml import etree  # type: ignore


def get_xml_element(filepath: str, path: str) -> Any:  # etree.Element
    """
    parses an xml file and returns the element at the given path
    """
    parser = etree.XMLParser(remove_blank_text=True)  # type: ignore # To preserve line numbers
    tree = etree.parse(filepath, parser)  # type: ignore
    element = tree.getroot()  # type: ignore
    path_parts = path.split(".")
    for part in path_parts:
        # skip processing comments
        tags = [child.tag[16:] if isinstance(child.tag, str) else "" for child in element]  # type: ignore
        if part in tags:
            element = element[tags.index(part)]  # type: ignore

        elif part.isdigit():
            element = element[int(part)]  # type: ignore

    return element  # type: ignore


def parse_xml_path(filepath: str, path: str) -> str:
    """
    parses an xml file and returns a string of file, line number, character
    """
    element = get_xml_element(filepath, path)  # type: ignore
    return f"{filepath}:{element.sourceline}"  # type: ignore


def embedding_to_source_xml(filepath: str) -> str:
    """
    for given json embedding, return xml source docu path
    """
    return "assets/" + filepath[11:].replace(".json", ".xml")


def get_clickable_chunk(filepath: str, chunk_id: int) -> str:
    """
    parses a json chunk file and returns a string of file, line number for its associated xml
    """
    with open(filepath, "r") as f:
        chunks = f.read()
    chunks = eval(chunks)
    chunk = chunks[chunk_id]
    path = chunk["path"]
    new_file_path = embedding_to_source_xml(filepath)
    return parse_xml_path(new_file_path, path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python pathy.py <xml_file> <path>")
        sys.exit(1)

    filepath = sys.argv[1]
    path = sys.argv[2]
    print(parse_xml_path(filepath, path))
