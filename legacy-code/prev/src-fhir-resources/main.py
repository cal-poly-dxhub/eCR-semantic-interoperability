import json
import sys
from typing import Any, Dict, List, Union

import fhir.resources
import fhir.resources.binary
import fhir.resources.patient
import lxml  # type: ignore # parser for bs4
from bs4 import BeautifulSoup

"""
steps:
1. xml --> json
2. patientrold --> fhir.resources.Patient
"""

filepath = "../assets/florida/e3ad92ed-df7e-4318-9d88-74ab2d07ec8b_20240718063134.xml"
jsonrep = {}


def get_direct_text(element: Any) -> str:
    return "".join([t for t in element.contents if isinstance(t, str)]).strip()


def xml_to_dict(element: Any) -> Dict[str, Union[str, List[Dict[str, Any]]]]:
    """
    Convert an XML element to a dictionary.
    If there is plaintext in the element, it is stored in the key "plaintext".
    """
    data: Any = {}
    if element.attrs:
        data.update(element.attrs)

    text = get_direct_text(element)
    if text:
        data["plaintext"] = text

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
    # with open(filepath, "r") as f:
    #     soup = BeautifulSoup(f.read(), "xml")
    #     jsonrep = xml_to_dict(soup.ClinicalDocument)

    # list all fhir resources
    for r in fhir.resources.patient.Patient.__dict__.values():
        if isinstance(r, dict) and r.get("resource_type"):
            modelfield = r.get("resource_type").default
            if modelfield == "Patient":
                for k in r.keys():
                    print(k)
