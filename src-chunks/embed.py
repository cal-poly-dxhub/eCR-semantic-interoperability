import json
import os
import sys

from chunky import extract_relevant_chunks
from vectoring import embed_text, get_biobert_embeddings  # type: ignore

pathext = "out/"
embeddings_path = "embeddings/"


def cleanup():
    if os.path.exists(pathext):
        for file in os.listdir(pathext):
            os.remove(os.path.join(pathext, file))
    else:
        os.mkdir(pathext)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python embed.py <xml_file>")
        sys.exit(1)
    cleanup()
    file = sys.argv[1]

    chunks = extract_relevant_chunks(file)

    with open(pathext + "chunks.json", "w") as f:
        json.dump(chunks, f)

    # choose between bedrock and local in vectoring.py
    embeddings = [embed_text(chunk) for chunk in chunks]
    # embeddings = [embed_text(chunks[0])] # for running one embedding

    output_path = embeddings_path + file[7:].replace(".xml", ".json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(embeddings, f, indent=4)
