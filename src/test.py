import json
import os
import sys
import xml.etree.ElementTree as ET
from typing import Any
import re

import lxml
import numpy as np
from lxml import etree

from bedrock import llm_inference
from chunky import extract_relevant_chunks_file
from pathy import embedding_to_source_xml, get_xml_element
from transform import tree_to_string
from vectoring import get_bedrock_embeddings

tempext = "temp/"
outext = "out/"

# TODO: Make prompt easier to edit for customer
# TODO: Human input pipeline for categories

def cleanup():
    for p in [tempext, outext]:
        if os.path.exists(p):
            for file in os.listdir(p):
                os.remove(os.path.join(p, file))
        else:
            os.mkdir(p)

def normalize_text(text : str) -> str:
    """Normalize text by converting to lowercase and removing special characters."""
    # Convert to lowercase
    text = text.lower()
    # Remove special characters
    text = re.sub(r'[^\w\s]', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

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
                        "category": e["category"],
                    }
                    embeddings.append(r)

    return embeddings

def cos_similarity(a: np.array, b: np.array) -> float:  # type: ignore
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))  # type: ignore

def first_occurrence_of_text(normalized_text: str, chunk_map: dict, current_index: int) -> bool:
    """Return True if this is the first occurrence of this text in the document."""
    for i in range(current_index):
        if chunk_map[i] == normalized_text:
            return False
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python test.py <xml_file>")
        sys.exit(1)
    cleanup()
    file = sys.argv[1]

    chunks = extract_relevant_chunks_file(file)
    with open("temp/chunks.json", "w") as f:
        json.dump(chunks, f)

    seen = set()
    unique_chunks = []
    for chunk in chunks:
        if normalize_text(chunk.get("text","")) not in seen:
            seen.add(normalize_text(chunk.get("text","")))
            unique_chunks.append(chunk)
    print(f"{len(chunks)} total chunks, after deduping, {len(unique_chunks)} total chunks")

    # choose between hl7 and ecr (makedata golden template) schemas in vectoring.py
    test_file_embeddings = [get_bedrock_embeddings(c) for c in unique_chunks]
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
                    "path": unique_chunks[i]["path"],
                },
                "similarity": similarity,
                "category": existing_embedding["category"],
            }
            similarities[i].append(r)
        # store all similarities for now so can access them if needed or if first one isnt best match etc
        similarities[i].sort(key=lambda x: x["similarity"], reverse=True)

    with open("temp/similarities.json", "w") as f:
        json.dump(similarities, f, indent=2)

    document_with_similarities: list[Any] = []
    for i in range(len(similarities)):
        document_with_similarities.append(similarities[i][0])  # type: ignore

    with open("temp/whole_doc_similarities.json", "w") as f:
        # intermediately saving document with similarities
        json.dump(document_with_similarities, f, indent=2)

    inferences: list[str] = []
    for i, s in enumerate(document_with_similarities):
        print(f"chunk {i + 1} / {len(document_with_similarities)}:")
        embed_section_path = s["existing_file"]["path"].split(".section.")[0]
        test_section_path = s["test_file"]["path"].split(".section.")[0]
        embed_xml = embedding_to_source_xml(s["existing_file"]["file"])
        print("------------------------------------------------------------")
        print(
            f"matched {s['existing_file']['file']}\nto {embed_xml}\ncategory {s['category']}"
        )
        print("------------------------------------------------------------\n")
        embed_el: Any = get_xml_element(embed_xml, embed_section_path)
        test_el: Any = get_xml_element(s["test_file"]["file"], test_section_path)
        text = tree_to_string(test_el)
        test_el_string = etree.tostring(test_el, encoding='unicode')
        # for debugging: save text to file
        # with open(f"out/text{i}.txt", "w") as f:
        #     f.write(text)

        contains_table = False
        
        # 3 different methods to check if the chunk is a table
        if "<table" in test_el_string:
            contains_table = True
        
        if not contains_table:
            for elem in test_el.iter():
                tag = elem.tag
                # Remove namespace if present
                if '}' in tag:
                    tag = tag.split('}', 1)[1]
                if tag.lower() == 'table':
                    contains_table = True
                    break
        
        if not contains_table:
            try:
                tables = test_el.xpath(".//*[local-name()='table']")
                if tables:
                    contains_table = True
            except (AttributeError, TypeError):
                pass

        if not contains_table:
            inference = llm_inference(text)
        else:
            inference = "<pregnancy pregnant=\"false\"><reasoning>Table data - no inference performed</reasoning></pregnancy><travel status=\"false\"><reasoning>Table data - no inference performed</reasoning></travel><occupation employed=\"false\"><reasoning>Table data - no inference performed</reasoning></occupation>"
        
        xml = (
            f"<{s['category'].replace(' ', '_')} similarity=\"{s['similarity']}\"><testSource filePath=\"{s['test_file']['file']}\" elementPath=\"{test_section_path}\">"
            + text
            + f'</testSource><embeddedSource filePath="{embed_xml}" elementPath="{embed_section_path}">'
            + tree_to_string(embed_el)
            + "</embeddedSource><inference>"
            + inference
            + f"</inference></{s['category'].replace(' ', '_')}>"
        )
        inferences.append(xml)

    with open("out/xml_source_inference.xml", "w") as f:
        f.write("<root>")
        for i in inferences:
            f.write(i)
        f.write("</root>")
        
    print("Final output created in: out/xml_source_inference.xml")