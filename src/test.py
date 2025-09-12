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

from datetime import datetime

tempext = "temp/"
outext = "out/"

input_tokens = 0
output_tokens = 0


def get_content_preview(element, max_length=50):
    """Extract a meaningful text preview from an XML element."""
    try:
        # First try to find text elements
        text_elements = element.xpath(".//text")
        if text_elements:
            for text_el in text_elements:
                # Get text content
                if text_el.text and text_el.text.strip():
                    return text_el.text.strip()[:max_length]

        # If no text elements with content, try tables
        table_elements = element.xpath(".//table")
        if table_elements:
            for table in table_elements:
                # Try to get content from table cells
                cells = table.xpath(".//td")
                if cells:
                    cell_texts = []
                    for cell in cells[:3]:  # Get first few cells
                        if cell.text and cell.text.strip():
                            cell_texts.append(cell.text.strip())
                    if cell_texts:
                        return " | ".join(cell_texts)[:max_length]

        # If still no content, look for any text in any element
        all_text = element.xpath(".//text()")
        filtered_text = [t.strip() for t in all_text if t.strip()]
        if filtered_text:
            return " ".join(filtered_text[:3])[:max_length]

        # If we still don't have content, return a fallback
        return "No text content found"

    except Exception as e:
        return f"Preview error: {str(e)[:30]}"


def cleanup():
    for p in [tempext, outext]:
        if os.path.exists(p):
            for file in os.listdir(p):
                os.remove(os.path.join(p, file))
        else:
            os.mkdir(p)


def normalize_text(text: str) -> str:
    """Normalize text by converting to lowercase and removing special characters."""
    # Convert to lowercase
    text = text.lower()
    # Remove special characters
    text = re.sub(r"[^\w\s]", "", text)
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()
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


def first_occurrence_of_text(
    normalized_text: str, chunk_map: dict, current_index: int
) -> bool:
    """Return True if this is the first occurrence of this text in the document."""
    for i in range(current_index):
        if chunk_map[i] == normalized_text:
            return False
    return True


if __name__ == "__main__":
    start_time = datetime.now()
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
        if normalize_text(chunk.get("text", "")) not in seen:
            seen.add(normalize_text(chunk.get("text", "")))
            unique_chunks.append(chunk)
    print(
        f"{len(chunks)} total chunks, after deduplication, {len(unique_chunks)} total chunks"
    )

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

    """Below is the additive code"""
    document_with_similarities: list[Any] = []
    for i in range(len(similarities)):
        # Find the top individual match (original approach)
        top_match = similarities[i][0]

        # Group similarities for this chunk by category and calculate additive scores
        category_scores = {}
        for sim in similarities[i]:
            category = sim["category"]
            if category not in category_scores:
                category_scores[category] = {"score": 0, "matches": []}
            category_scores[category]["score"] += sim["similarity"]

            # Get a preview of the chunk text (for showing in the output)
            preview_text = ""
            try:
                # Try to get the source XML file to extract a preview
                source_xml = embedding_to_source_xml(sim["existing_file"]["file"])
                source_path = sim["existing_file"]["path"].split(".section.")[0]
                source_el = get_xml_element(source_xml, source_path)
                full_text = tree_to_string(source_el)
                # Truncate to ~50 tokens (roughly 250 characters)
                preview_text = full_text[:250] + ("..." if len(full_text) > 250 else "")
            except:
                preview_text = "Preview not available"

            # Store match info with preview
            category_scores[category]["matches"].append(
                {
                    "file": sim["existing_file"]["file"],
                    "path": sim["existing_file"]["path"],
                    "similarity": sim["similarity"],
                    "preview": preview_text,
                }
            )

        # Find the category with the highest additive score
        highest_category = max(category_scores.items(), key=lambda x: x[1]["score"])
        top_category = highest_category[0]
        top_score = highest_category[1]["score"]

        # Create an entry with both the top individual match and category scores
        new_entry = {
            "existing_file": top_match["existing_file"],
            "test_file": top_match["test_file"],
            "similarity": top_match["similarity"],
            "category": top_match["category"],
            "additive_top_category": top_category,
            "additive_top_score": top_score,
            "highest_category_matches": category_scores[top_category]["matches"],
        }

        document_with_similarities.append(new_entry)

    with open("temp/whole_doc_similarities.json", "w") as f:
        # Save document with similarities
        json.dump(document_with_similarities, f, indent=2)

    """below is the additive code"""
    inferences: list[str] = []
    for i, s in enumerate(document_with_similarities):
        print(f"chunk {i + 1} / {len(document_with_similarities)}:")
        embed_section_path = s["existing_file"]["path"].split(".section.")[0]
        test_section_path = s["test_file"]["path"].split(".section.")[0]
        embed_xml = embedding_to_source_xml(s["existing_file"]["file"])

        print("------------------------------------------------------------")
        print(f"Top match: {s['existing_file']['file']}")
        print(f"to {embed_xml}")
        print(f"category: {s['category']} (similarity: {s['similarity']:.4f})")
        print(
            f"\nHighest additive category: {s['additive_top_category']} (score: {s['additive_top_score']:.4f})"
        )
        print("  Top matches:")

        # Show top matches for the highest category
        for match in sorted(
            s["highest_category_matches"], key=lambda x: x["similarity"], reverse=True
        )[:3]:
            print(f"    - {match['file']} (similarity: {match['similarity']:.4f})")
            print(f"      Path: {match['path']}")
            # Print preview on a new line with some indentation
            # print(f"      Preview: \"{match['preview'].replace('\n', ' ').strip()[:50]}\"")

        print("------------------------------------------------------------\n")

        # Get the elements for the XML output
        embed_el: Any = get_xml_element(embed_xml, embed_section_path)
        test_el: Any = get_xml_element(s["test_file"]["file"], test_section_path)
        text = tree_to_string(test_el)
        test_el_string = etree.tostring(test_el, encoding="unicode")

        contains_table = False
        # 3 different methods to check if the chunk is a table
        if "<table" in test_el_string:
            contains_table = True

        if not contains_table:
            for elem in test_el.iter():
                tag = elem.tag

                # skip comments
                if type(tag).__name__ == "cython_function_or_method":
                    continue

                # Remove namespace if present
                if "}" in tag:
                    tag = tag.split("}", 1)[1]
                if tag.lower() == "table":
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
            llm_response = llm_inference(text)
            inference = llm_response[0]
            input_tokens += llm_response[1]
            output_tokens += llm_response[2]
        else:
            inference = '<pregnancy pregnant="false"><reasoning>Table data - no inference performed</reasoning></pregnancy><travel status="false"><reasoning>Table data - no inference performed</reasoning></travel><occupation employed="false"><reasoning>Table data - no inference performed</reasoning></occupation>'

        # Create the XML with only the highest additive category
        additive_scores_xml = f'<category name="{s["additive_top_category"]}" score="{s["additive_top_score"]}">'
        for match in sorted(
            s["highest_category_matches"], key=lambda x: x["similarity"], reverse=True
        )[:3]:
            try:
                # Get a better preview of the content
                source_xml = embedding_to_source_xml(match["file"])
                source_path = match["path"].split(".section.")[0]
                source_el = get_xml_element(source_xml, source_path)
                preview = get_content_preview(source_el, 100)  # Get a 100-char preview
            except Exception as e:
                preview = f"Preview not available: {str(e)[:30]}"

            # Escape the preview text for XML
            preview = (
                preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            preview = preview.replace("\n", " ").strip()

            additive_scores_xml += f'<match file="{match["file"]}" path="{match["path"]}" similarity="{match["similarity"]}">\n  <preview>{preview}</preview>\n</match>\n'
        additive_scores_xml += "</category>\n"

        xml = (
            f"<{s['category'].replace(' ', '_')} similarity=\"{s['similarity']}\" additive_top_category=\"{s['additive_top_category']}\" additive_top_score=\"{s['additive_top_score']}\">\n"
            f"  <testSource filePath=\"{s['test_file']['file']}\" elementPath=\"{test_section_path}\">\n"
            + text
            + f"\n  </testSource>\n"
            f'  <embeddedSource filePath="{embed_xml}" elementPath="{embed_section_path}">\n'
            + tree_to_string(embed_el)
            + "\n  </embeddedSource>\n"
            f"  <additiveScores>\n" + additive_scores_xml + "  </additiveScores>\n"
            f"  <inference>\n" + inference + f"\n  </inference>\n"
            f"</{s['category'].replace(' ', '_')}>\n"
        )
        inferences.append(xml)

    with open("out/xml_source_inference.xml", "w") as f:
        f.write("<root>")
        for i in inferences:
            f.write(i)
        f.write("</root>")

    end_time = datetime.now()
    elapsed = end_time - start_time

    # https://aws.amazon.com/bedrock/pricing/ as of 04/01/2025
    total_inference_cost = (input_tokens * 0.0008 / 1000) + (
        output_tokens * 0.0032 / 1000
    )

    print("------------------------------------------------------------")
    print("Final output created in: out/xml_source_inference.xml")
    print(f"LLM inference input tokens: {input_tokens}")
    print(f"LLM inference output tokens: {output_tokens}")
    print(f"Approximate LLM inference cost: ${total_inference_cost:.4f}")
    print(f"Script took approximately {elapsed.total_seconds() / 60:.2f} minutes.")
    print("------------------------------------------------------------")
