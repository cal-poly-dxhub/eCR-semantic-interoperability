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
        print("usage: python parse_xml.py <xml_file>")
        sys.exit(1)
    cleanup()

    file = sys.argv[1]
    if "assets" not in file:
        file = "assets/" + file

    chunks = extract_relevant_chunks(file)

    # print the first 3 chunks
    # for i, chunk in enumerate(chunks[:3]):
    #     print(f"Chunk {i+1}: {chunk[:200]}...")

    with open(pathext + "chunks.json", "w") as f:
        json.dump(chunks, f)

    # bedrock accessdenied errors
    # embeddings = [embed_text(chunk) for chunk in chunks]
    # embeddings = [embed_text(chunks[0])]
    # with open(pathext + "embeddings.json", "w") as f:
    #     json.dump(embeddings, f)

    # local bioBERT embeddings
    embeddings = [get_biobert_embeddings(chunk) for chunk in chunks]  # type: ignore
    if not os.path.exists(embeddings_path):
        os.mkdir(embeddings_path)

    with open(
        embeddings_path + file.replace("/", "-").replace(".xml", ".json"), "w"
    ) as f:
        json.dump(embeddings, f)
