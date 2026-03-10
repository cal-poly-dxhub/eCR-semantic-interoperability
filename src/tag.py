import json
import os
import sys
import re
from datetime import datetime

from lxml import etree

from bedrock import llm_inference
from chunky import extract_relevant_chunks
from preprocess import resolve_references, strip_namespaces, write_preprocessed_file
from transform import tree_to_string

tempext = "temp/"
outext = "out/"

input_tokens = 0
output_tokens = 0


def cleanup():
    for p in [tempext, outext]:
        if os.path.exists(p):
            for file in os.listdir(p):
                os.remove(os.path.join(p, file))
        else:
            os.mkdir(p)


def normalize_text(text: str) -> str:
    """Normalize text by converting to lowercase and removing special characters."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


if __name__ == "__main__":
    start_time = datetime.now()
    if len(sys.argv) < 2:
        print("usage: python tag.py <xml_file>")
        sys.exit(1)
    cleanup()
    file = sys.argv[1]

    # Preprocess: resolve references
    print("Preprocessing: resolving references...")
    resolved_tree = resolve_references(file)
    strip_namespaces(resolved_tree)

    # Save preprocessed file (no XML declaration, no namespace prefixes)
    preprocessed_path = os.path.join("out", os.path.basename(file).replace(".xml", "_preprocessed.xml"))
    write_preprocessed_file(resolved_tree, preprocessed_path, file)
    print(f"Saved preprocessed file: {preprocessed_path}")

    # Extract chunks from resolved tree
    chunks = extract_relevant_chunks(resolved_tree)
    with open("temp/chunks.json", "w") as f:
        json.dump(chunks, f)

    seen = set()
    unique_chunks = []
    for chunk in chunks:
        if normalize_text(chunk.get("text", "")) not in seen:
            seen.add(normalize_text(chunk.get("text", "")))
            unique_chunks.append(chunk)
    print(
        f"{len(chunks)} total chunks, after deduplication, {len(unique_chunks)} total chunks"
    )

    # Run LLM inference on each chunk (tagging only, no categorization)
    inferences: list[str] = []
    for i, chunk in enumerate(unique_chunks):
        print(f"chunk {i + 1} / {len(unique_chunks)}:")
        chunk_text = chunk.get("text", "")
        chunk_xml = chunk.get("xml", "")

        contains_table = False
        if "<table" in chunk_xml.lower():
            contains_table = True

        if not contains_table:
            try:
                doc = etree.fromstring(chunk_xml.encode("utf-8"))
                tables = doc.xpath(".//*[local-name()='table']")
                if tables:
                    contains_table = True
            except Exception:
                pass

        if not contains_table:
            llm_response = llm_inference(chunk_text)
            inference = llm_response[0]
            input_tokens += llm_response[1]
            output_tokens += llm_response[2]
        else:
            inference = (
                '<pregnancy pregnant="false"><reasoning>Table data - no inference performed</reasoning></pregnancy>'
                '<travel status="false"><reasoning>Table data - no inference performed</reasoning></travel>'
                '<occupation employed="false"><reasoning>Table data - no inference performed</reasoning></occupation>'
            )

        # Escape chunk text for XML embedding
        safe_text = (
            chunk_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

        xml = (
            f'<chunk id="{i}" path="{chunk["path"]}">\n'
            f"  <source>\n    {safe_text}\n  </source>\n"
            f"  <inference>\n    {inference}\n  </inference>\n"
            f"</chunk>\n"
        )
        inferences.append(xml)
        print(f"  contains_table={contains_table}, path={chunk['path']}")

    with open("out/xml_tagging_inference.xml", "w") as f:
        f.write("<root>\n")
        for i in inferences:
            f.write(i)
        f.write("</root>\n")

    end_time = datetime.now()
    elapsed = end_time - start_time

    # https://aws.amazon.com/bedrock/pricing/ as of 04/01/2025
    total_inference_cost = (input_tokens * 0.003 / 1000) + (
        output_tokens * 0.015 / 1000
    )

    print("------------------------------------------------------------")
    print("Final output created in: out/xml_tagging_inference.xml")
    print(f"Preprocessed file: {preprocessed_path}")
    print(f"LLM inference input tokens: {input_tokens}")
    print(f"LLM inference output tokens: {output_tokens}")
    print(f"Approximate LLM inference cost: ${total_inference_cost:.4f}")
    print(f"Script took approximately {elapsed.total_seconds() / 60:.2f} minutes.")
    print("------------------------------------------------------------")
