from typing import Any

from bedrock import get_fhir_from_flat_json


def transform_object(fhir_object: dict[str, Any], flat_json: dict[str, str]) -> None:
    """
    puts the flat json into the fhir object
    """
    id = flat_json["id"]
    value = flat_json["value"]
    fhir_path = get_fhir_from_flat_json(flat_json)
    # fhir_path = "Patient.name.given"
    if fhir_path:
        keys = fhir_path.split(".")
        current = fhir_object
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = {"id": id, "value": value}


def build_fhir_object(flat_json: list[dict[str, str]]) -> dict[str, Any]:
    """
    build the fhir object from the flat json
    """
    fhir_object: dict[str, Any] = {}
    for index, item in enumerate(flat_json):
        if index < 20:
            continue
        if index > 30:
            break
        print(f"Processing {index} of {len(flat_json)}")
        transform_object(fhir_object, item)

    return fhir_object
