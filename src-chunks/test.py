import json
import os
import sys
from typing import Any

import numpy as np  # type: ignore
from bedrock import invoke_llm, llm_model_id  # For invoking LLM
from chunky import extract_relevant_chunks
from pathy import get_clickable_chunk, get_xml_element, parse_xml_path  # type: ignore
from transform import etree_transform_data_to_json  # type: ignore
from transform import get_matching_schema
from vectoring import embed_text


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


# ryan
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python test.py <xml_file>")
        sys.exit(1)

    file = sys.argv[1]

    chunks = extract_relevant_chunks(file)
    with open("out/chunks.json", "w") as f:
        json.dump(chunks, f)

    test_file_embeddings = [embed_text(chunk) for chunk in chunks]

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
            similarities.append(
                {
                    "existing_file": {
                        "file": f"embeddings/{existing_embedding['file']}",
                        "chunk_id": existing_embedding["chunk_id"],
                        "path": existing_embedding["path"],
                    },
                    "test_file": {
                        "file": file,
                        "chunk_id": i,
                        "path": chunks[i]["path"],
                    },
                    "similarity": similarity,
                }
            )
    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    truncated = similarities[:10]
    with open("out/similarities.json", "w") as f:
        json.dump(truncated, f, indent=4)

    text_indices = [
        i for i, c in enumerate(chunks) if c["path"].split(".")[-1].lower() == "text"
    ]
    table_indices = [
        i for i, c in enumerate(chunks) if c["path"].split(".")[-1].lower() == "table"
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
                element = get_xml_element(file, section_path)
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
                element = get_xml_element(file, section_path)
                record = etree_transform_data_to_json(element)
            except Exception:
                record = {}
            record["text"] = chunk["text"]
            record["path"] = chunk["path"]
            record["inference_answers"] = chunk.get("llm_answers", {})
            text_segment_records.append(record)

    final_output = {}
    if best_table_record:
        final_output["best_match_table"] = best_table_record
    else:
        final_output["best_match_table"] = None

    final_output["text_segments"] = text_segment_records

    with open("out/json_object.json", "w") as f:
        json.dump(final_output, f, indent=4)

    print("exported to out/json_object.json")

# # gus
# if __name__ == "__main__":
#     if len(sys.argv) < 2:
#         print("usage: python test.py <xml_file>")
#         sys.exit(1)
#     file = sys.argv[1]

#     existing_embeddings = load_all_embeddings()
#     chunks = extract_relevant_chunks(file)

#     with open("out/chunks.json", "w") as f:
#         json.dump(chunks, f)

#     # choose between hl7 and ecr (makedata golden template) schemas in vectoring.py
#     test_file_embeddings = [embed_text(chunk) for chunk in chunks]
#     similarities: list[dict[str, Any]] = []

#     for i, tfe in enumerate(test_file_embeddings):
#         for j, existing_embedding in enumerate(existing_embeddings):
#             # cosine similarity
#             similarity = np.dot(  # type: ignore
#                 np.array(tfe["embedding"]),  # type: ignore
#                 np.array(existing_embedding["embedding"]),  # type: ignore
#             ) / (
#                 np.linalg.norm(np.array(tfe["embedding"]))  # type: ignore
#                 * np.linalg.norm(np.array(existing_embedding["embedding"]))  # type: ignore
#             )
#             r: dict[str, Any] = {
#                 "existing_file": {
#                     "file": f"embeddings/{existing_embedding['file']}",
#                     "chunk_id": existing_embedding["chunk_id"],
#                     "path": existing_embedding["path"],
#                 },
#                 "test_file": {
#                     "file": file,
#                     "chunk_id": i,
#                     "path": chunks[i]["path"],
#                 },
#                 "similarity": similarity,
#             }
#             similarities.append(r)

#     similarities.sort(key=lambda x: x["similarity"], reverse=True)
#     truncated = similarities[:10]
#     with open("out/similarities.json", "w") as f:
#         json.dump(truncated, f, indent=4)

#     # print("-" * 120)
#     # for s in truncated:
#     #     c1 = parse_xml_path(s["test_file"]["file"], s["test_file"]["path"])
#     #     c2 = get_clickable_chunk(
#     #         s["existing_file"]["file"], s["existing_file"]["chunk_id"]
#     #     )
#     #     print(f"similarity: {s['similarity']}")
#     #     print(f"test chunk: {c1}")
#     #     print(f"existing chunk: {c2}")
#     #     print("-" * 120)

#     best_match = truncated[0]
#     best_match_file = best_match["existing_file"]["file"]
#     best_match_chunk_id = best_match["existing_file"]["chunk_id"]
#     print("-" * 120)
#     print(f"best match: {best_match['similarity']}")
#     print(
#         f"test chunk: \"{parse_xml_path(best_match['test_file']['file'], best_match['test_file']['path'])}\""
#     )
#     print(
#         f"existing chunk: \"{get_clickable_chunk(best_match['existing_file']['file'], best_match['existing_file']['chunk_id'])}\""
#     )
#     print("-" * 120)

#     # get best match schema
#     best_match_schema = get_matching_schema(best_match_file, best_match_chunk_id)
#     with open("out/chunks.json", "r") as f:
#         d = json.load(f)

#     # get the text from the test file out/chunk.json
#     text = d[best_match_chunk_id]["text"]

#     # transform the text into a json object
#     # j = llm_transform_data_to_json(text, best_match_schema)

#     # transform the file and path into a json object
#     print(f"schema: {best_match_schema}")
#     test_file_path = best_match["test_file"]["path"]
#     closest_section_path = test_file_path.split(".section.")[0] + ".section"
#     element = get_xml_element(file, closest_section_path)  # type: ignore
#     j = etree_transform_data_to_json(element)  # type: ignore
#     # add category to json
#     with open(f"out/json_object.json", "w") as f:
#         json.dump(j, f, indent=4)
#     print(f"exported to out/json_object.json")
