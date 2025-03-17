import re
import xml.etree.ElementTree as ET
from typing import Any

from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    # text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    return text.lower().strip()


def manipulate_tag(tag: str) -> str:
    tag = re.sub(r"\{.*\}", "", tag)
    return tag


def table_to_list(element: ET.Element) -> list[list[str]]:
    """
    takes a table xml element and returns a list of dictionaries
    ex. [['header1', 'header2'], ['value1a', 'value2a'], ['value1b', 'value2b']]
    """
    soup = BeautifulSoup(ET.tostring(element), "xml")
    table = soup.table
    th = table.find_all("th")  # type: ignore
    td = table.find_all("td")  # type: ignore
    headers = [clean_text(h.text) for h in th]
    rows: list[list[str]] = []
    for i in range(0, len(td)):
        row = [clean_text(cell.text) for cell in td[i : i + len(headers)]]
        rows.append(row)

    all_rows = [headers] + rows
    return all_rows


def chunkify_table_list(table: list[list[str]], max_chunk_size: int) -> list[str]:
    """
    converts a table to a list of strings for vectorizing
    truncates table into one chunk of less than max_chunk_size
    """
    chunk: list[str] = []
    chunk_size = 0
    for row in table:
        row_str = "\t".join(row)
        row_size = len(row_str)
        if chunk_size + row_size <= max_chunk_size:
            chunk.append(row_str + "\n")
            chunk_size += row_size + 1
        else:
            break

    return chunk


def chunkify_by_hierarchy(
    element: ET.Element,
    max_chunk_size: int,
) -> list[dict[str, Any]]:
    """
    chunk the document dynamically based on the xml hierarchy
    groups related elements under the same parent or logically related elements into chunks
    """
    chunks: list[dict[str, Any]] = []
    current_chunk: list[str] = []  # this is the text of the chunk
    current_chunk_size = 0
    chunk_id = 0

    def process_element(
        el: ET.Element,
        parent_path: str,
    ):
        nonlocal current_chunk, current_chunk_size, chunk_id
        if el.tag.endswith("table"):
            t = table_to_list(el)
            chunk = chunkify_table_list(t, max_chunk_size)
            if chunk:
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "text": " ".join(chunk),
                        "path": parent_path,
                        "chunk_size": len(" ".join(chunk)),
                    }
                )
                chunk_id += 1

        # elif el.text: # disregard text elements for now
        #     clean_el_text = clean_text(el.text)
        #     clean_el_text_length = len(clean_el_text)
        #     # print(clean_el_text)
        #     # print(f"processing: {el.tag[16:]}")

        #     if current_chunk_size + clean_el_text_length <= max_chunk_size:
        #         current_chunk.append(clean_el_text)
        #         current_chunk_size += clean_el_text_length
        #     else:
        #         if current_chunk:
        #             chunks.append(
        #                 {
        #                     "chunk_id": chunk_id,
        #                     "text": " ".join(current_chunk),
        #                     "path": parent_path,
        #                     "chunk_size": current_chunk_size,
        #                 }
        #             )
        #             chunk_id += 1
        #             # print(
        #             #     f"finalizing chunk: {len(current_chunk)} elements, {current_chunk_size} characters."
        #             # )
        #             current_chunk = [clean_el_text]
        #             current_chunk_size = clean_el_text_length

    def traverse_xml_tree(el: ET.Element, parent_path: str):
        # manipulated_tag = manipulate_tag(el.tag)
        process_element(el, parent_path)

        for child in el:
            child_tag = manipulate_tag(child.tag)
            siblings = [c for c in el if manipulate_tag(c.tag) == child_tag]
            index = siblings.index(child)
            if len(siblings) > 1:
                child_tag = f"{index}"
            new_parent_path = f"{parent_path}.{child_tag}"
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


def chunkify_by_hierarchy_text_tables(
    element: ET.Element,
    max_chunk_size: int,
    include_tables: bool = True,
    include_text: bool = True,
) -> list[dict[str, Any]]:
    """
    Dynamically chunks the document based on the XML hierarchy.
    It can extract:
      - <table> elements (if include_tables is True)
      - <text> elements that do not contain any <table> descendants (if include_text is True)
    """
    chunks: list[dict[str, Any]] = []
    chunk_id = 0

    def process_element(el: ET.Element, parent_path: str):
        nonlocal chunk_id
        if include_tables and el.tag.endswith("table"):
            t = table_to_list(el)
            chunk = chunkify_table_list(t, max_chunk_size)
            if chunk:
                combined_text = " ".join(chunk)
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "text": combined_text,
                        "path": parent_path,
                        "chunk_size": len(combined_text),
                    }
                )
                chunk_id += 1

        if include_text and el.tag.endswith("text") and el.find(".//table") is None:
            if el.text and el.text.strip():
                clean_el_text = clean_text(el.text)
                clean_el_text_length = len(clean_el_text)
                if clean_el_text_length > 0:
                    if clean_el_text_length <= max_chunk_size:
                        chunks.append(
                            {
                                "chunk_id": chunk_id,
                                "text": clean_el_text,
                                "path": parent_path,
                                "chunk_size": clean_el_text_length,
                            }
                        )
                        chunk_id += 1
                    else:
                        # If the text exceeds max_chunk_size, split it into smaller chunks.
                        start = 0
                        while start < clean_el_text_length:
                            end = start + max_chunk_size
                            chunk_text = clean_el_text[start:end]
                            chunks.append(
                                {
                                    "chunk_id": chunk_id,
                                    "text": chunk_text,
                                    "path": parent_path,
                                    "chunk_size": len(chunk_text),
                                }
                            )
                            chunk_id += 1
                            start = end

    def traverse_xml_tree(el: ET.Element, parent_path: str):
        process_element(el, parent_path)
        for child in el:
            child_tag = manipulate_tag(child.tag)
            siblings = [c for c in el if manipulate_tag(c.tag) == child_tag]
            index = siblings.index(child)
            if len(siblings) > 1:
                child_tag = f"{index}"
            new_parent_path = f"{parent_path}.{child_tag}"
            traverse_xml_tree(child, new_parent_path)

    traverse_xml_tree(element, "root")
    return chunks


def extract_relevant_chunks(
    filename: str, max_chunk_size: int = 6000
) -> list[dict[str, Any]]:
    """
    extract chunks of the document using XML parsing and dynamic chunking
    """
    tree = ET.parse(filename)
    root = tree.getroot()
    chunks = chunkify_by_hierarchy_text_tables(root,max_chunk_size, False, True)
    # chunks = chunkify_by_hierarchy(root, max_chunk_size)

    return chunks
