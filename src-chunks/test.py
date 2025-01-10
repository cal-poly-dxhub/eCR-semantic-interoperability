import json
import os
import sys
from typing import Any

import numpy as np  # type: ignore
from chunky import extract_relevant_chunks
from vectoring import get_biobert_embeddings


def load_all_embeddings() -> list[Any]:
    embeddings: list[Any] = []
    os.chdir("embeddings/")
    for file_path in os.listdir("."):
        print("loading", file_path)
        with open(file_path, "r") as f:
            # f is json file with array of objects, one key in object is "embedding" and value there is ebmeddings.tolist()
            e = json.load(f)
            embeddings.extend(e)

    os.chdir("..")
    return embeddings


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python parse_xml.py <xml_file>")
        sys.exit(1)

    file = sys.argv[1]
    if "assets" not in file:
        file = "assets/" + file

    existing_embeddings = load_all_embeddings()
    chunks = extract_relevant_chunks(file)
    test_embeddings = [get_biobert_embeddings(chunk) for chunk in chunks]

    # compare existing_embeddings[...]["embedding"] with test_embeddings[...]["embedding"]

    # cosine similarity
    for i, test_embedding in enumerate(test_embeddings):
        for j, existing_embedding in enumerate(existing_embeddings):
            similarity = np.dot(  # type: ignore
                np.array(test_embedding["embedding"]),  # type: ignore
                np.array(existing_embedding["embedding"]),  # type: ignore
            ) / (
                np.linalg.norm(np.array(test_embedding["embedding"]))  # type: ignore
                * np.linalg.norm(np.array(existing_embedding["embedding"]))  # type: ignore
            )
            print(f"cosine similarity between {i} and {j}: {similarity}")

    # euclidean distance
    # for i, test_embedding in enumerate(test_embeddings):
    #     for j, existing_embedding in enumerate(existing_embeddings):
    #         distance = np.linalg.norm(  # type: ignore
    #             np.array(test_embedding["embedding"])  # type: ignore
    #             - np.array(existing_embedding["embedding"])  # type: ignore
    #         )
    #         print(f"euclidian distance between {i} and {j}: {distance}")

    # manhattan distance
    # for i, test_embedding in enumerate(test_embeddings):
    #     for j, existing_embedding in enumerate(existing_embeddings):
    #         distance = np.linalg.norm(  # type: ignore
    #             np.array(test_embedding["embedding"])  # type: ignore
    #             - np.array(existing_embedding["embedding"]),  # type: ignore
    #             ord=1,
    #         )
    #         print(f"manhattan distance between {i} and {j}: {distance}")
