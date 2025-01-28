import re
import xml.etree.ElementTree as ET
from typing import Any


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    return text.lower().strip()


def manipulate_tag(tag: str) -> str:
    tag = re.sub(r"\{.*\}", "", tag)
    return tag


def chunkify_by_hierarchy(
    element: ET.Element,
    max_chunk_size: int,
) -> list[dict[str, Any]]:
    """
    chunk the document dynamically based on the xml hierarchy
    groups related elements under the same parent or logically related elements into chunks
    """
    chunks: list[dict[str, Any]] = []
    current_chunk: list[str] = []
    current_chunk_size = 0
    chunk_id = 0

    def process_element(
        el: ET.Element,
        parent_path: str,
    ):
        nonlocal current_chunk, current_chunk_size, chunk_id
        if el.text:
            clean_el_text = clean_text(el.text)
            clean_el_text_length = len(clean_el_text)
            # print(f"processing: {el.tag[16:]}")

            if current_chunk_size + clean_el_text_length <= max_chunk_size:
                current_chunk.append(clean_el_text)
                current_chunk_size += clean_el_text_length
            else:
                if current_chunk:
                    chunks.append(
                        {
                            "chunk_id": chunk_id,
                            "text": " ".join(current_chunk),
                            "path": parent_path,
                            "chunk_size": current_chunk_size,
                        }
                    )
                    chunk_id += 1
                    # print(
                    #     f"finalizing chunk: {len(current_chunk)} elements, {current_chunk_size} characters."
                    # )
                    current_chunk = [clean_el_text]
                    current_chunk_size = clean_el_text_length

    def traverse_xml_tree(el: ET.Element, parent_path: str):
        # manipulated_tag = manipulate_tag(el.tag)
        process_element(el, parent_path)

        for child in el:
            child_tag = manipulate_tag(child.tag)
            siblings = [c for c in el if manipulate_tag(c.tag) == child_tag]
            index = siblings.index(child)
            new_parent_path = f"{parent_path}.{child_tag}.{index}"
            traverse_xml_tree(child, new_parent_path)

    traverse_xml_tree(element, "root")
    if current_chunk:
        chunks.append(
            {
                "chunk_id": chunk_id,
                "text": " ".join(current_chunk),
                "path": "root",
                "chunk_size": current_chunk_size,
            }
        )
        # print(
        #     f"finalizing chunk: {len(current_chunk)} elements, {current_chunk_size} characters."
        # )

    return chunks


def extract_relevant_chunks(
    filename: str, max_chunk_size: int = 6000
) -> list[dict[str, Any]]:
    """
    extract chunks of the document using XML parsing and dynamic chunking
    """
    tree = ET.parse(filename)
    root = tree.getroot()

    chunks = chunkify_by_hierarchy(root, max_chunk_size)

    return chunks
