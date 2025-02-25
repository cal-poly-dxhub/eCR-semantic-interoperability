import json
import os
import sys
from typing import Any

import numpy as np  # type: ignore
from bedrock import ask_llm_additional_questions  # type: ignore
from bedrock import invoke_llm, llm_model_id  # type: ignore
from chunky import extract_relevant_chunks
from pathy import get_clickable_chunk, get_xml_element, parse_xml_path  # type: ignore
from transform import etree_transform_data_to_json  # type: ignore
from transform import get_matching_schema
from vectoring import get_bedrock_embeddings


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


def cos_similarity(a: np.array, b: np.array) -> float:  # type: ignore
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))  # type: ignore


# ryan
# if __name__ == "__main__":
#     if len(sys.argv) < 2:
#         print("usage: python test.py <xml_file>")
#         sys.exit(1)

#     file = sys.argv[1]

#     chunks = extract_relevant_chunks(file)
#     with open("out/chunks.json", "w") as f:
#         json.dump(chunks, f)

#     test_file_embeddings = [embed_text(chunk) for chunk in chunks]

#     existing_embeddings = load_all_embeddings()
#     similarities: list[dict[str, Any]] = []
#     for i, tfe in enumerate(test_file_embeddings):
#         for j, existing_embedding in enumerate(existing_embeddings):
#             similarity = np.dot(
#                 np.array(tfe["embedding"]), np.array(existing_embedding["embedding"])
#             ) / (
#                 np.linalg.norm(np.array(tfe["embedding"]))
#                 * np.linalg.norm(np.array(existing_embedding["embedding"]))
#             )
#             similarities.append(
#                 {
#                     "existing_file": {
#                         "file": f"embeddings/{existing_embedding['file']}",
#                         "chunk_id": existing_embedding["chunk_id"],
#                         "path": existing_embedding["path"],
#                     },
#                     "test_file": {
#                         "file": file,
#                         "chunk_id": i,
#                         "path": chunks[i]["path"],
#                     },
#                     "similarity": similarity,
#                 }
#             )
#     similarities.sort(key=lambda x: x["similarity"], reverse=True)
#     truncated = similarities[:10]
#     with open("out/similarities.json", "w") as f:
#         json.dump(truncated, f, indent=2)

#     text_indices = [
#         i for i, c in enumerate(chunks) if c["path"].split(".")[-1].lower() == "text"
#     ]
#     table_indices = [
#         i for i, c in enumerate(chunks) if c["path"].split(".")[-1].lower() == "table"
#     ]

#     best_table_record = None
#     if table_indices:
#         # Filter similarities to only those that reference a table chunk
#         table_sims = [
#             s for s in similarities if s["test_file"]["chunk_id"] in table_indices
#         ]
#         table_sims.sort(key=lambda x: x["similarity"], reverse=True)
#         if table_sims:
#             best_match = table_sims[0]
#             best_id = best_match["test_file"]["chunk_id"]
#             section_path = ".".join(chunks[best_id]["path"].split(".")[:-1])
#             try:
#                 element = get_xml_element(file, section_path)
#                 best_table_record = etree_transform_data_to_json(element)
#             except Exception:
#                 best_table_record = {}
#             best_table_record["text"] = chunks[best_id]["text"]
#             best_table_record["path"] = chunks[best_id]["path"]

#     text_segment_records = []
#     for i in text_indices:
#         chunk = chunks[i]
#         if "text" in chunk and chunk["text"]:

#             answers = ask_llm_additional_questions(chunk["text"])
#             chunk["llm_answers"] = answers

#             section_path = ".".join(chunk["path"].split(".")[:-1])
#             try:
#                 element = get_xml_element(file, section_path)
#                 record = etree_transform_data_to_json(element)
#             except Exception:
#                 record = {}
#             record["text"] = chunk["text"]
#             record["path"] = chunk["path"]
#             record["inference_answers"] = chunk.get("llm_answers", {})
#             text_segment_records.append(record)

#     final_output = {}
#     if best_table_record:
#         final_output["best_match_table"] = best_table_record
#     else:
#         final_output["best_match_table"] = None

#     final_output["text_segments"] = text_segment_records

#     with open("out/json_object.json", "w") as f:
#         json.dump(final_output, f, indent=2)

#     print("exported to out/json_object.json")

# # gus
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python test.py <xml_file>")
        sys.exit(1)
    file = sys.argv[1]

    chunks = extract_relevant_chunks(file)
    with open("out/chunks.json", "w") as f:
        json.dump(chunks, f)

    # choose between hl7 and ecr (makedata golden template) schemas in vectoring.py
    test_file_embeddings = [get_bedrock_embeddings(chunk) for chunk in chunks]
    existing_embeddings = load_all_embeddings()
    similarities: list[list[dict[str, Any]]] = []

    for i, tfe in enumerate(test_file_embeddings):
        similarities.append([])
        for j, existing_embedding in enumerate(existing_embeddings):
            similarity = cos_similarity(
                np.array(tfe["embedding"]), np.array(existing_embedding["embedding"])
            )
            r: dict[str, Any] = {
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
            similarities[i].append(r)
        # store all similarities for now so can access them if needed or if first one isnt best match etc
        similarities[i].sort(key=lambda x: x["similarity"], reverse=True)

    # now similarities = [[{existing_file, test_file, similarity}, {...}, ...], [{...}, {...}, ...], ...]

    # for each array in similarities, get the first element of the first element
    document_with_similarities: list[Any] = []
    for i in range(len(similarities)):
        document_with_similarities.append(similarities[i][0])  # type: ignore

    with open("out/whole_doc_similarities.json", "w") as f:
        json.dump(document_with_similarities, f, indent=2)

    # save file of chunks and their similar chunks
    side_by_side: list[Any] = []
    for i, c in enumerate(document_with_similarities):
        existing_file = (
            c["existing_file"]["file"]
            .replace("embeddings/", "assets/")
            .replace(".json", ".xml")
        )
        test_xml_section = c["test_file"]["path"].split(".section.")[0] + ".section"
        test_xml: Any = get_xml_element(c["test_file"]["file"], test_xml_section)
        existing_xml_section = (
            c["existing_file"]["path"].split(".section.")[0] + ".section"
        )
        existing_xml: Any = get_xml_element(
            existing_file,
            existing_xml_section,
        )

        test_link = parse_xml_path(c["test_file"]["file"], c["test_file"]["path"])
        existing_link = get_clickable_chunk(
            c["existing_file"]["file"], c["existing_file"]["chunk_id"]
        )

        side_by_side.append(
            {
                "test_chunk": {
                    "file": c["test_file"]["file"],
                    "path": c["test_file"]["path"],
                    "link": test_link,
                    "source_info": etree_transform_data_to_json(test_xml),
                },
                "existing_chunk": {
                    "file": existing_file,
                    "path": c["existing_file"]["path"],
                    "link": existing_link,
                    "source_info": etree_transform_data_to_json(existing_xml),
                },
                "similarity": c["similarity"],
            }
        )

    with open("out/side_by_side.json", "w") as f:
        json.dump(side_by_side, f, indent=2)

    exit(0)

    # ------------------

    best_match = truncated[0]
    best_match_file = best_match["existing_file"]["file"]
    best_match_chunk_id = best_match["existing_file"]["chunk_id"]
    print("-" * 120)
    print(f"best match: {best_match['similarity']}")
    print(
        f"test chunk: \"{parse_xml_path(best_match['test_file']['file'], best_match['test_file']['path'])}\""
    )
    print(
        f"existing chunk: \"{get_clickable_chunk(best_match['existing_file']['file'], best_match['existing_file']['chunk_id'])}\""
    )
    print("-" * 120)

    # get best match schema
    best_match_schema = get_matching_schema(best_match_file, best_match_chunk_id)
    with open("out/chunks.json", "r") as f:
        d = json.load(f)

    # get the text from the test file out/chunk.json
    text = d[best_match_chunk_id]["text"]

    # transform the text into a json object
    # j = llm_transform_data_to_json(text, best_match_schema)

    # transform the file and path into a json object
    test_file_path = best_match["test_file"]["path"]
    closest_section_path = test_file_path.split(".section.")[0] + ".section"
    element = get_xml_element(file, closest_section_path)  # type: ignore
    j = etree_transform_data_to_json(element)  # type: ignore
    # add category to json
    with open(f"out/json_object.json", "w") as f:
        json.dump(j, f, indent=2)
    print(f"exported to out/json_object.json")
