import json
import os
import sys

from chunky import extract_relevant_chunks
from vectoring import embed_text

pathext = "out/"


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

    # choose between hl7 and ecr (makedata golden template) schemas in vectoring.py
    embeddings = [embed_text(chunk) for chunk in chunks]
    output_path = "embeddings/" + file[7:].replace(".xml", ".json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(embeddings, f, indent=4)
