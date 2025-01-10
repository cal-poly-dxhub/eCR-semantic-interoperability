import json
import os
import sys

from chunky import extract_relevant_chunks

pathext = "out/"


def cleanup():
    if os.path.exists(pathext):
        for file in os.listdir(pathext):
            os.remove(os.path.join(pathext, file))
    else:
        os.mkdir(pathext)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python parse_xml.py <xml_file>")
        sys.exit(1)
    cleanup()

    file = sys.argv[1]
    if "assets" not in file:
        file = "./assets/" + file

    chunks = extract_relevant_chunks(file)

    for i, chunk in enumerate(chunks[:3]):
        print(f"Chunk {i+1}: {chunk[:200]}...")

    with open(pathext + "chunks.json", "w") as f:
        json.dump(chunks, f)
