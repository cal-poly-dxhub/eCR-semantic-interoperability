import json
import os
import sys
from typing import Any

import numpy as np  # type: ignore
from .bedrock import invoke_llm, llm_model_id  # For invoking LLM
from .chunky import extract_relevant_chunks
from .pathy import get_clickable_chunk, get_xml_element, parse_xml_path  # type: ignore
from .transform import etree_transform_data_to_json  # type: ignore
from .transform import get_matching_schema
from .vectoring import embed_text

def load_all_embeddings() -> list[Any]:
    embeddings: list[dict[str, Any]] = []
    base_dir = "embeddings"

    for root, _, files in os.walk(base_dir):
        for file_path in files:
            if not file_path.endswith(".json"):
                continue

            full_path = os.path.join(root, file_path)
            rel_path = os.path.relpath(full_path, base_dir)
            with open(full_path, "r") as f:
                d = json.load(f)
                for e in d:
                    r: dict[str, Any] = {
                        "file": rel_path,
                        "embedding": e["embedding"],
                        "chunk_id": e["chunk_id"],
                        "path": e["path"],
                        "chunk_size": e["chunk_size"],
                    }
                    embeddings.append(r)

    return embeddings


def ask_llm_additional_questions(text: str) -> dict[str, Any]:
    """
    Calls the LLM to answer the three questions about pregnancy, travel history, and occupation.
    Returns a dict in JSON format.
    """
    prompt = (
        "You are analyzing the following text from a patient's record:\n\n"
        f"{text}\n\n"
        "Answer these questions in JSON format with exactly the following keys and structure:\n\n"
        "{\n"
        '  "patient_pregnant": "true" or "false",\n'
        '  "patient_pregnant_cot": "string explanation of your chain of thought of how arrived at your conclusion",\n'
        '  "recent_travel_history": {\n'
        '    "true_false": "true" or "false",\n'
        '    "where": "string",\n'
        '    "when": "string",\n'
        '    "cot": "string explanation of your chain of thought of how arrived at your conclusion"\n'
        "  },\n"
        '  "occupation": {\n'
        '    "true_false": "true" or "false",\n'
        '    "job": "string",\n'
        '    "cot": "string explanation of your chain of thought of how arrived at your conclusion"\n'
        "  }\n"
        "}\n\n"
        'For each field, if the text does not indicate any specific information, return "false" for the boolean value '
        "and an empty string for the text fields. Do not add any extra keys."
    )
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
    }
    response = invoke_llm(json.dumps(request_body), llm_model_id)
    response_text = json.loads(response["body"].read())["content"][0]["text"]
    try:
        return json.loads(response_text)
    except Exception:
        return {}


def cos_similarity(a: np.array, b: np.array) -> float:  # type: ignore
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))  # type: ignore


# ryan
def process_test_file(file_path: str):
    print("process test file")
    # Extract chunks from the XML file
    os.makedirs("/tmp/out", exist_ok=True)
    chunks = extract_relevant_chunks(file_path)
    with open("/tmp/out/chunks.json", "w") as f:
        try:
            json.dump(chunks, f)
        except Exception as e:
            print(e)
            print(type(e))
            print("process_test_file:", file_path)

    # Process embeddings for each chunk
    test_file_embeddings = [embed_text(chunk) for chunk in chunks]

    # Load existing embeddings and compute similarities
    existing_embeddings = load_all_embeddings()
    similarities: list[dict[str, Any]] = []
    for i, tfe in enumerate(test_file_embeddings):
        for j, existing_embedding in enumerate(existing_embeddings):
            similarity = np.dot(
                np.array(tfe["embedding"]), np.array(existing_embedding["embedding"])
            ) / (
                np.linalg.norm(np.array(tfe["embedding"]))
                * np.linalg.norm(np.array(existing_embedding["embedding"]))
            )
            similarities.append({
                "existing_file": {
                    "file": f"embeddings/{existing_embedding['file']}",
                    "chunk_id": existing_embedding["chunk_id"],
                    "path": existing_embedding["path"],
                },
                "test_file": {
                    "file": file_path,
                    "chunk_id": i,
                    "path": chunks[i]["path"],
                },
                "similarity": similarity,
            })
    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    truncated = similarities[:10]
    with open("/tmp/out/similarities.json", "w") as f:
        json.dump(truncated, f, indent=4)

    # Identify indices for text and table chunks
    text_indices = [
        i for i, c in enumerate(chunks)
        if c["path"].split(".")[-1].lower() == "text"
    ]
    table_indices = [
        i for i, c in enumerate(chunks)
        if c["path"].split(".")[-1].lower() == "table"
    ]

    best_table_record = None
    if table_indices:
        # Filter similarities to only those that reference a table chunk
        table_sims = [
            s for s in similarities if s["test_file"]["chunk_id"] in table_indices
        ]
        table_sims.sort(key=lambda x: x["similarity"], reverse=True)
        if table_sims:
            best_match = table_sims[0]
            best_id = best_match["test_file"]["chunk_id"]
            section_path = ".".join(chunks[best_id]["path"].split(".")[:-1])
            try:
                element = get_xml_element(file_path, section_path)
                best_table_record = etree_transform_data_to_json(element)
            except Exception:
                best_table_record = {}
            best_table_record["text"] = chunks[best_id]["text"]
            best_table_record["path"] = chunks[best_id]["path"]

    text_segment_records = []
    for i in text_indices:
        chunk = chunks[i]
        if "text" in chunk and chunk["text"]:
            answers = ask_llm_additional_questions(chunk["text"])
            chunk["llm_answers"] = answers

            section_path = ".".join(chunk["path"].split(".")[:-1])
            try:
                element = get_xml_element(file_path, section_path)
                record = etree_transform_data_to_json(element)
            except Exception:
                record = {}
            record["text"] = chunk["text"]
            record["path"] = chunk["path"]
            record["inference_answers"] = chunk.get("llm_answers", {})
            text_segment_records.append(record)

    final_output = {}
    final_output["best_match_table"] = best_table_record if best_table_record else None
    final_output["text_segments"] = text_segment_records

    with open("/tmp/out/json_object.json", "w") as f:
        json.dump(final_output, f, indent=4)
    return final_output["text_segments"]
    print("exported to /tmp/out/json_object.json")
