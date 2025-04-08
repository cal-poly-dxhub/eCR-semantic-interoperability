import sys
import os

from lxml import etree  # type: ignore


def get_xml_element(filepath: str, path: str) -> etree.Element:  # type: ignore
    """
    parses an xml file and returns the element at the given path
    """
    parser = etree.XMLParser(remove_blank_text=True)  # type: ignore # To preserve line numbers
    tree = etree.parse(filepath, parser)  # type: ignore
    element = tree.getroot()  # type: ignore
    path_parts = path.split(".")
    for part in path_parts:
        tags = [child.tag[16:] for child in element]  # type: ignore
        # print(tags)  # type: ignore
        if part in tags:
            element = element[tags.index(part)]  # type: ignore
        elif part.isdigit():
            element = element[int(part)]  # type: ignore

    return element


def parse_xml_path(filepath: str, path: str) -> str:
    """ "
    parses an xml file and returns a string of file, line number, character
    """
    element = get_xml_element(filepath, path)  # type: ignore
    return f"{filepath}, {element.sourceline}"  # type: ignore


def get_clickable_chunk(filepath: str, chunk_id: int) -> str:
    """
    parses a json chunk file and returns a string of file, line number for its associated xml
    """
    with open(filepath, "r") as f:
        chunks = f.read()
    chunks = eval(chunks)
    chunk = chunks[chunk_id]
    path = chunk["path"]
    
    # Get absolute path to the assets directory
    current_dir = os.path.dirname(os.path.abspath(__file__))  # Gets /var/task/src
    project_root = os.path.dirname(current_dir)  # Gets /var/task
    
    # Extract the base filename from the input path
    base_filename = os.path.basename(filepath).replace(".json", ".xml")
    
    # Create the correct absolute path to the XML file
    new_file_path = os.path.join(project_root, "assets", base_filename)
    
    return parse_xml_path(new_file_path, path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python pathy.py <xml_file> <path>")
        sys.exit(1)

    filepath = sys.argv[1]
    path = sys.argv[2]
    print(parse_xml_path(filepath, path))
