import ast
import json
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError

from shared import save_to_file

from fhir.resources.patient import Patient
from fhir.resources.humanname import HumanName
from fhir.resources.fhirtypes import Date

import xml.etree.ElementTree as ET

get_info_prompt: str = """<prompt>
You are a medical data analyst tasked with analyzing a list of key-value pairs from a medical JSON dataset. Your goal is to identify the key-value pairs where the value contains information related to a specific query.
The key-value pairs may include various types of data, such as text, numbers, or nested objects/arrays, representing different medical attributes, diagnoses, treatments, test results, and more.

Given:
1. A list of key-value pairs present in the medical dataset:
--KEY_VALUE_PAIRS--

2. A specific characteristic or query of interest: <query>--QUERY--</query>

Your task is to examine the list of key-value pairs and return a subset of those pairs where the value contains information relevant to the given query.

<format>
You will split your response into "thought" and "relevant_pairs". There should be no content outside these XML blocks:
<thought>Your internal thought process</thought>
<relevant_pairs>A list of "<pair>" elements containing the key-value pairs relating to the query in this format:
<pair>
<key>key1</key>
<value>value containing relevant information</value>
</pair>
(If no relevant pairs are found leave the <relevant_pairs> block empty)
</relevant_pairs>
</format>
</prompt>"""

def xml_to_patient_json(filepath : str):
    with open(filepath , 'r') as f:
        cda = f.read()

    root = ET.fromstring(cda)
    namespace = {'cda': 'urn:hl7-org:v3'}
    # patient_path = 'ClinicalDocument.recordTarget.patientRole'

    patient_gender_entity = root.find(".//cda:recordTarget/cda:patientRole/cda:patient/cda:administrativeGenderCode", namespaces=namespace)
    patient_name = root.find(".//cda:recordTarget/cda:patientRole/cda:patient/cda:name/cda:given", namespaces=namespace).text
    patient_birth_entity = root.find(".//cda:recordTarget/cda:patientRole/cda:patient/cda:birthTime", namespaces=namespace)

    gender_code = patient_gender_entity.attrib["code"]
    birthdate = patient_birth_entity.attrib['value']

    date = Date(int(birthdate[0:4]),int(birthdate[4:6]), int(birthdate[6:]) )

    return(Patient( birthDate=date, gender=gender_code, name=[HumanName(given=[patient_name])]))


def get_all_keys(data: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(data, dict):  # type: ignore
        keys.extend(data.keys())  # type: ignore
        for value in data.values():  # type: ignore
            keys.extend(get_all_keys(value))  # type: ignore
    return keys


def create_keys_xml(keys: list[str]) -> str:
    xml: str = "<json_keys>\n"
    for key in keys:
        xml += f" <key>{key}</key>\n"
    xml += "</json_keys>"
    return xml


def create_key_value_xml(keys: list[str], values: list[Any]) -> str:
    xml: str = "<key_value_pairs>\n"
    for key, value in zip(keys, values):
        xml += f" <pair>\n  <key>{key}</key>\n  <value>{value}</value>\n </pair>\n"
    xml += "</key_value_pairs>"
    return xml


def get_bedrock_response(prompt: str) -> str:
    client = boto3.client("bedrock-runtime", region_name="us-west-2")  # type: ignore
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    conversation = [{"role": "user", "content": [{"text": prompt}]}]

    try:
        response = client.converse(  # type: ignore
            modelId=model_id,
            messages=conversation,
            inferenceConfig={"maxTokens": 1024, "temperature": 1.0, "topP": 0.9},
        )
        response_text: Any = response["output"]["message"]["content"][0]["text"]
        return response_text

    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
        exit(1)


def get_json_keys_tags(res: str) -> list[str]:
    start = res.find("<json_keys>")
    end = res.find("</json_keys>")
    if start == -1 or end == -1:
        return []
    keys_xml = res[start : end + len("</json_keys>")].split("\n")[1:-1]
    keys = [key.strip()[5:-6] for key in keys_xml]
    return keys


def get_json_pairs_tags(res: str) -> dict[str, Any]:
    relevant_pairs: dict[str, Any] = {}
    pair_start = res.find("<pair>")
    while pair_start != -1:
        pair_end = res.find("</pair>", pair_start)
        if pair_end == -1:
            break

        pair_data = res[pair_start + 6 : pair_end]
        key_start = pair_data.find("<key>")
        key_end = pair_data.find("</key>")
        key = pair_data[key_start + 5 : key_end]

        value_start = pair_data.find("<value>")
        value_end = pair_data.find("</value>")
        value = pair_data[value_start + 7 : value_end]

        if "pregnant" in value.lower():
            try:
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass
            relevant_pairs[key] = value

        pair_start = res.find("<pair>", pair_end)

    return relevant_pairs


def get_json_value(data: Any, key: str) -> Any:
    if isinstance(data, dict):  # type: ignore
        if key in data:  # type: ignore
            return data[key]  # type: ignore
        for value in data.values():  # type: ignore
            result = get_json_value(value, key)
            if result is not None:
                return result
    elif isinstance(data, list):  # type: ignore
        for item in data:  # type: ignore
            result = get_json_value(item, key)
            if result is not None:
                return result
    return None


if __name__ == "__main__":
    if len(sys.argv) < 1:
        print("Usage: python script.py <file_path> query")
    else:
        # file_path = sys.argv[1]
        file_path = './input_xml.xml'
        # query = sys.argv[2]
        query = "what is the patients name"
        # file_path = f"../assets/human_readable_messy/{file}"


        keys = []
        data = None
        try:
            with open(file_path, "r") as file:
                patient = xml_to_patient_json(file_path)
                data = patient.json()
                data = json.loads(data)
                keys: list[str] = get_all_keys(data)
        except FileNotFoundError:
            print(f"Error: File '{file_path}' not found.")
        except json.JSONDecodeError:
            print(f"Error: '{file_path}' is not a valid JSON file.")

        if keys and data:
            values = [get_json_value(data, key) for key in keys]
            pairs = create_key_value_xml(keys, values)
            vp = get_info_prompt.replace("--KEY_VALUE_PAIRS--", pairs).replace(
                "--QUERY--", query
            )
            vr = get_bedrock_response(vp)
            pairs = get_json_pairs_tags(vr)
            save_to_file(json.dumps(pairs, indent=2), "output2.json")
