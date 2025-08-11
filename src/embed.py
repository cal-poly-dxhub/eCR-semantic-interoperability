import json
import os
import sys

from chunky import extract_relevant_chunks_file
from vectoring import get_bedrock_embeddings_with_category
from test import normalize_text

tempext = "temp/"


def cleanup():
    if os.path.exists(tempext):
        for file in os.listdir(tempext):
            os.remove(os.path.join(tempext, file))
    else:
        os.mkdir(tempext)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python embed.py <xml_file>")
        sys.exit(1)
    cleanup()
    file = sys.argv[1]

    chunks = extract_relevant_chunks_file(file)
    seen = set()
    unique_chunks = []
    for chunk in chunks:
        if normalize_text(chunk.get("text", "")) not in seen:
            seen.add(normalize_text(chunk.get("text", "")))
            unique_chunks.append(chunk)
    print(
        f"{len(chunks)} total chunks, after deduplication, {len(unique_chunks)} total chunks"
    )
    chunks = unique_chunks

    with open(tempext + "chunks.json", "w") as f:
        json.dump(chunks, f)

    # choose between hl7 and ecr (makedata golden template) schemas in vectoring.py
    embeddings = [get_bedrock_embeddings_with_category(chunk) for chunk in chunks]
    output_path = "embeddings/" + file.replace(".xml", ".json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(embeddings, f, indent=4)
