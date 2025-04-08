import ast
import json
import sys
import xml.etree.ElementTree as ET  # type: ignore
from typing import Any

import boto3  # type: ignore
from botocore.exceptions import ClientError
from shared import save_to_file

get_keys_prompt: str = """<prompt>
You are a medical data analyst tasked with analyzing a JSON dataset containing medical information. Your goal is to identify the relevant keys in the JSON data that may contain information related to a specific query.
The JSON data structure consists of nested dictionaries and lists, with keys representing various medical attributes, such as patient information, diagnoses, treatments, test results, and more.

Given:
1. A list of JSON keys present in the medical dataset:
--KEYS--

2. A specific characteristic or query of interest: <query>--QUERY--</query>
Your task is to examine the list of JSON keys and determine which keys in which there is any possibility of containing information relevant to the given query. Include any keys relating to relevant summaries.

<format>
    You will split your response into "thought" and "json_keys". There should be no content outside these XML blocks:\n\n<thought>Your internal thought process</thought><json_keys>a list of "<key>" elements containing the keys relating to the query</json_keys>
</format>
</prompt>"""

get_info_prompt: str = """<prompt>
You are a medical data analyst tasked with analyzing a list of key-value pairs from a medical JSON dataset. Your goal is to identify the key-value pairs where the value contains information related to a specific query.
The key-value pairs may include various types of data, such as text, numbers, or nested objects/arrays, representing different medical attributes, diagnoses, treatments, test results, and more.

Given:
1. A list of key-value pairs present in the medical dataset:
<key_value_pairs>
--KEY_VALUE_PAIRS--
</key_value_pairs>

2. A specific characteristic or query of interest: <query>--QUERY--</query>

Your task is to examine the list of key-value pairs and return a subset of those pairs where the value contains information relevant to the given query.

<format>
You will split your response into "thought" and "relevant_pairs". There should be no content outside these XML blocks:
<thought>Your internal thought process</thought>
<relevant_pairs>A list of "<pair>" elements containing the key-value pairs relating to the query in this format:
<pair>
<key>key1</key>
<value>value containing relevant information</value>
<reason>reason for relevance</reason>
</pair>
(If no relevant pairs are found leave the <relevant_pairs> block empty)
</relevant_pairs>
</format>
</prompt>"""


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
    print("getting response")
    client = boto3.client("bedrock-runtime", region_name="us-east-1")  # type: ignore
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    conversation: Any = [{"role": "user", "content": [{"text": prompt}]}]

    try:
        response = client.converse(  # type: ignore
            modelId=model_id,
            messages=conversation,
            inferenceConfig={"maxTokens": 2048, "temperature": 1.0, "topP": 0.9},
        )
        response_text: Any = response["output"]["message"]["content"][0]["text"]
        print("got response")
        with open("response.txt", "w") as f:
            f.write(response_text)
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
        reason_start = pair_data.find("<reason>")
        reason_end = pair_data.find("</reason>")
        value = pair_data[value_start + 7 : value_end]

        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            pass

        new_val = {  # type: ignore
            "value": value,
            "reason": pair_data[reason_start + 8 : reason_end],
        }
        relevant_pairs[key] = new_val

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
    if len(sys.argv) < 3:
        print("Usage: python script.py <file_path> query")
    else:
        file = sys.argv[1]
        query = sys.argv[2]
        file_path = f"../assets/makedata/{file}"

        xml = ""
        data = None
        try:
            with open(file_path, "r") as file:
                data = json.load(file)
                keys: list[str] = get_all_keys(data)
                xml = create_keys_xml(keys)
        except FileNotFoundError:
            print(f"Error: File '{file_path}' not found.")
        except json.JSONDecodeError:
            print(f"Error: '{file_path}' is not a valid JSON file.")

        if xml and data:
            kp = get_keys_prompt.replace("--KEYS--", xml).replace("--QUERY--", query)
            kr: str = get_bedrock_response(kp)
            keys = get_json_keys_tags(kr)
            print("relevant keys:", keys)

            values = [get_json_value(data, key) for key in keys]
            pairs = create_key_value_xml(keys, values)
            vp = get_info_prompt.replace("--KEY_VALUE_PAIRS--", pairs).replace(
                "--QUERY--", query
            )
            vr = get_bedrock_response(vp)
            print(vr)
            # exit(1)
            pairs = get_json_pairs_tags(vr)
            # print(pairs)
            save_to_file(json.dumps(pairs, indent=4), "output.json")
