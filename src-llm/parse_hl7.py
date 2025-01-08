import json
import sys
from typing import Any, Union

import lxml  # type: ignore # parser for bs4
from bs4 import BeautifulSoup


def get_direct_text(element: Any) -> str:
    return "".join([t for t in element.contents if isinstance(t, str)]).strip()


def xml_to_dict(element: Any) -> dict[str, Union[str, list[dict[str, Any]]]]:
    """
    Convert an XML element to a dictionary.
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python parse_xml.py <xml_file>")
        sys.exit(1)

    file = sys.argv[1]
    with open(file, "r") as f:
        soup = BeautifulSoup(f.read(), "xml")
        d = xml_to_dict(soup.ClinicalDocument)
    with open("out.json", "w") as outfile:
        json.dump(d, outfile)
