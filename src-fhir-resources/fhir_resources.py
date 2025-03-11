import json
from typing import Any

import fhir.resources.patient

attrs = [
    "name",
    "type_",
    "required",
    "default",
    "alias",
    #
]


def get_attributes(element: Any, name: str) -> dict[str, Any]:
    """
    element: fhir.resource\n
    name: str\n
    ex: get_attributes(fhir.resources.patient.Patient, "Patient")\n
    returns a dict of the attributes of the resource
    """
    j: dict[str, Any] = {}
    for r in element.__dict__.values():
        if isinstance(r, dict) and r.get("resource_type"):
            resource_name = r.get("resource_type").default
            if resource_name == name:
                for item in r.items():
                    model: Any = item[1]
                    attribute_dict = {}
                    for attr in attrs:
                        current_attribute = getattr(model, attr)
                        if attr == "type_":
                            attribute_dict[attr] = current_attribute.__name__.split(
                                "."
                            )[-1]
                        else:
                            attribute_dict[attr] = current_attribute
                    j[getattr(model, "name")] = attribute_dict
    # for item in j.items():
    # print(item)
    return j


resource_class = "patient"
resource_subclass = "Patient"

module = __import__(f"fhir.resources.{resource_class}.{resource_subclass}")

js = get_attributes(module, "Patient")
with open("patient.json", "w") as f:
    json.dump(js, f, indent=4)
