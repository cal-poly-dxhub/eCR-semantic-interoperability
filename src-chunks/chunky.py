import re
import xml.etree.ElementTree as ET


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    return text.lower().strip()


def chunkify_by_hierarchy(element: ET.Element, max_chunk_size: int = 1000) -> list[str]:
    """
    chunk the document dynamically based on the xml hierarchy
    groups related elements under the same parent or logically related elements into chunks
    """
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_chunk_size = 0

    def process_element(el: ET.Element):
        nonlocal current_chunk, current_chunk_size

        if el.text:
            clean_el_text = clean_text(el.text)
            clean_el_text_length = len(clean_el_text)
            print(f"Processing element: {el.tag} | Text: {clean_el_text[:30]}...")

            if current_chunk_size + clean_el_text_length <= max_chunk_size:
                current_chunk.append(clean_el_text)
                current_chunk_size += clean_el_text_length
            else:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    print(
                        f"Finalizing chunk with {len(current_chunk)} elements. Size: {current_chunk_size} characters."
                    )
                    current_chunk = [clean_el_text]
                    current_chunk_size = clean_el_text_length

    def traverse_xml_tree(el: ET.Element):
        process_element(el)

        for child in el:
            traverse_xml_tree(child)

    traverse_xml_tree(element)
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        print(
            f"Finalizing last chunk with {len(current_chunk)} elements. Size: {current_chunk_size} characters."
        )

    return chunks


def extract_relevant_chunks(filename: str, max_chunk_size: int = 1000) -> list[str]:
    """
    extract chunks of the document using XML parsing and dynamic chunking
    """
    tree = ET.parse(filename)
    root = tree.getroot()

    chunks = chunkify_by_hierarchy(root, max_chunk_size)

    return chunks
