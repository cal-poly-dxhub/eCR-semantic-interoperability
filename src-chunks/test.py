import json
import os
import sys
from typing import Any

import numpy as np  # type: ignore
from chunky2 import extract_relevant_chunks
from pathy import get_clickable_chunk, parse_xml_path
from transform import get_matching_schema, transform_table_to_json
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python test.py <xml_file>")
        sys.exit(1)
    file = sys.argv[1]

    existing_embeddings = load_all_embeddings()
    chunks = extract_relevant_chunks(file)

    with open("out/chunks.json", "w") as f:
        json.dump(chunks, f)

    test_file_embeddings = [embed_text(chunk) for chunk in chunks]

    similarities: list[dict[str, Any]] = []

    for i, tfe in enumerate(test_file_embeddings):
        for j, existing_embedding in enumerate(existing_embeddings):
            # cosine similarity
            similarity = np.dot(  # type: ignore
                np.array(tfe["embedding"]),  # type: ignore
                np.array(existing_embedding["embedding"]),  # type: ignore
            ) / (
                np.linalg.norm(np.array(tfe["embedding"]))  # type: ignore
                * np.linalg.norm(np.array(existing_embedding["embedding"]))  # type: ignore
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
            similarities.append(r)

    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    truncated = similarities[:10]
    with open("out/similarities.json", "w") as f:
        json.dump(truncated, f, indent=4)

    # print("-" * 120)
    # for s in truncated:
    #     c1 = parse_xml_path(s["test_file"]["file"], s["test_file"]["path"])
    #     c2 = get_clickable_chunk(
    #         s["existing_file"]["file"], s["existing_file"]["chunk_id"]
    #     )
    #     print(f"similarity: {s['similarity']}")
    #     print(f"test chunk: {c1}")
    #     print(f"existing chunk: {c2}")
    #     print("-" * 120)

    best_match = truncated[0]
    best_match_file = best_match["existing_file"]["file"]
    best_match_chunk_id = best_match["existing_file"]["chunk_id"]
    print("-" * 120)
    print(f"best match: {best_match['similarity']}")
    print(
        f"test chunk: {parse_xml_path(best_match['test_file']['file'], best_match['test_file']['path'])}"
    )
    print(
        f"existing chunk: {get_clickable_chunk(best_match['existing_file']['file'], best_match['existing_file']['chunk_id'])}"
    )
    print("-" * 120)

    # get best match schema
    best_match_schema = get_matching_schema(best_match_file, best_match_chunk_id)
    with open("out/chunks.json", "r") as f:
        d = json.load(f)

    # get the text from the test file out/chunk.json
    text = d[best_match_chunk_id]["text"]

    # transform the text into a json object
    j = transform_table_to_json(text, best_match_schema)
    print(j)
    with open("out/json_object.json", "w") as f:
        json.dump(j, f, indent=4)
