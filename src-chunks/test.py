import json
import os
import sys
from typing import Any

import numpy as np
from bedrock import invoke_llm, llm_model_id
from chunky import extract_relevant_chunks
from pathy import get_clickable_chunk, get_xml_element, parse_xml_path
from transform import etree_transform_data_to_json, get_matching_schema
from vectoring import embed_text
from bedrock_batch import ask_llm_additional_questions_batch


def normalize_text(text):
    """Normalize text by converting to lowercase and removing special characters."""
    import re
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
                    }
                    embeddings.append(r)

    return embeddings


def cos_similarity(a: np.array, b: np.array) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


# Modified main function to use batch inference and maintain deduplication
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python test.py <xml_file>")
        sys.exit(1)

    file = sys.argv[1]

    # Extract chunks
    chunks = extract_relevant_chunks(file)
    with open("out/chunks.json", "w") as f:
        json.dump(chunks, f)

    # Identify text and table chunks
    text_indices = [
        i for i, c in enumerate(chunks) if c["path"].split(".")[-1].lower() == "text"
    ]
    table_indices = [
        i for i, c in enumerate(chunks) if c["path"].split(".")[-1].lower() == "table"
    ]

    # Process text chunks using batch inference
    print(f"Processing {len(text_indices)} text segments using batch inference...")
    
    # Extract text segments to process
    text_segments = [chunks[i] for i in text_indices if "text" in chunks[i] and chunks[i]["text"]]
    
    # Create a mapping of normalized text to original segments for deduplication
    text_deduplication_map = {}
    unique_text_segments = []

    for segment in text_segments:
        normalized = normalize_text(segment["text"])
        if normalized not in text_deduplication_map:
            text_deduplication_map[normalized] = []
            unique_text_segments.append(segment)
        
        # Keep track of all segments with this normalized text
        text_deduplication_map[normalized].append(segment)
    
    print(f"Reduced from {len(text_segments)} to {len(unique_text_segments)} unique text segments after de-duplication...")

    # Use batch processing
    bucket_name = "ryan-bedrock-batch-analysis"  # Change to your bucket name
    max_batch_size = 200  # Adjust based on your needs

    # Process only unique texts in batches and get token metrics
    updated_segments, token_metrics = ask_llm_additional_questions_batch(
        text_segments=unique_text_segments,
        bucket_name=bucket_name,
        max_batch_size=max_batch_size
    )

    # Create a mapping from path to processed segment
    processed_segments_by_path = {segment["path"]: segment for segment in updated_segments}

    # Create final output structure - only using unique segments
    text_segment_records = []
    
    # Use only the unique segments for the final output
    # for segment in unique_text_segments:
    #     path = segment["path"]
    #     if path in processed_segments_by_path:
    #         processed_segment = processed_segments_by_path[path]
    #         section_path = ".".join(path.split(".")[:-1])
    #         try:
    #             element = get_xml_element(file, section_path)
    #             record = etree_transform_data_to_json(element)
    #         except Exception:
    #             record = {}
            
    #         record["text"] = segment["text"]
    #         record["path"] = path
    #         record["inference_answers"] = processed_segment.get("llm_answers", {})
    #         text_segment_records.append(record)
    
    #Use only the unique segments for the final output - just text portion 
    for segment in unique_text_segments:
        path = segment["path"]
        if path in processed_segments_by_path:
            processed_segment = processed_segments_by_path[path]
            section_path = ".".join(path.split(".")[:-1])
            record = {}
            record["text"] = segment["text"]
            record["path"] = path
            record["inference_answers"] = processed_segment.get("llm_answers", {})
            text_segment_records.append(record)

    final_output = {}
    final_output["best_match_table"] = None
    final_output["text_segments"] = text_segment_records
    
    # Add token usage metrics to output
    final_output["token_usage"] = token_metrics

    with open("out/json_object.json", "w") as f:
        json.dump(final_output, f, indent=4)

    print("Exported to out/json_object.json")
    print(f"Token usage summary:")
    print(f"  - Input tokens: {token_metrics['input_tokens']}")
    print(f"  - Output tokens: {token_metrics['output_tokens']}")
    print(f"  - Total tokens: {token_metrics['total_tokens']}")