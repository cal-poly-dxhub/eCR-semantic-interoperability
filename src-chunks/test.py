import json
import os
import sys
import numpy as np  # type: ignore
from typing import Any

from chunky import extract_relevant_chunks
from pathy import get_clickable_chunk, get_xml_element, parse_xml_path  # type: ignore
from transform import etree_transform_data_to_json  # type: ignore
from transform import get_matching_schema
from vectoring import embed_text
from bedrock import invoke_llm, llm_model_id  # For invoking LLM

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
            "category": e.get("category", "")
          }
          embeddings.append(r)
  return embeddings

def ask_llm_additional_questions(text: str) -> dict[str, Any]:
  """
  Calls the LLM to answer the three questions about pregnancy, travel history, and occupation.
  Returns a dict in JSON format.
  """
  prompt = (
    "You are analyzing the following text from a patient's record:\n\n"
    f"{text}\n\n"
    "Answer these questions in JSON format with keys:\n\n"
    "{\n"
    '  "patient_pregnant": "yes" or "no",\n'
    '  "recent_travel_history": {\n'
    '    "yes_no": "yes" or "no",\n'
    '    "where": "string",\n'
    '    "when": "string"\n'
    "  },\n"
    '  "occupation": "string"\n'
    "}\n\n"
    "If the text does not indicate a specific field, return \"no\" or an empty string accordingly. "
    "Do not add extra keys."
  )
  request_body = {
    "anthropic_version": "bedrock-2023-05-31",
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": 500,
  }
  response = invoke_llm(json.dumps(request_body), llm_model_id)
  response_text = json.loads(response["body"].read())["content"][0]["text"]
  try:
    return json.loads(response_text)
  except Exception as e:
    return {}

if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("usage: python test.py <xml_file>")
    sys.exit(1)
  
  file = sys.argv[1]

  # Extract text chunks from the XML file.
  chunks = extract_relevant_chunks(file)
  with open("out/chunks.json", "w") as f:
    json.dump(chunks, f)
  
  # Embed each text chunk.
  test_file_embeddings = [embed_text(chunk) for chunk in chunks]
  
  # (Optional) Compute similarities between test embeddings and existing ones.
  existing_embeddings = load_all_embeddings()
  similarities: list[dict[str, Any]] = []
  for i, tfe in enumerate(test_file_embeddings):
    for j, existing_embedding in enumerate(existing_embeddings):
      similarity = np.dot(
        np.array(tfe["embedding"]),
        np.array(existing_embedding["embedding"])
      ) / (
        np.linalg.norm(np.array(tfe["embedding"]))
        * np.linalg.norm(np.array(existing_embedding["embedding"]))
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
          "path": chunks[i]["path"],
        },
        "similarity": similarity,
      }
      similarities.append(r)
  similarities.sort(key=lambda x: x["similarity"], reverse=True)
  truncated = similarities[:10]
  with open("out/similarities.json", "w") as f:
    json.dump(truncated, f, indent=4)
  
  # Get LLM answers for every text chunk.
  for chunk in chunks:
    if "text" in chunk and chunk["text"]:
      answers = ask_llm_additional_questions(chunk["text"])
      chunk["llm_answers"] = answers
  
  # For each text chunk, retrieve its parent section from the XML,
  # transform it to JSON (which preserves the medical information),
  # and then override "text", and add "path" and "answers".
  final_output = []
  for chunk in chunks:
    if "text" in chunk and chunk["text"]:
      # Remove the last component (assumed to be "text") to get the section's path.
      section_path = ".".join(chunk["path"].split(".")[:-1])
      try:
        element = get_xml_element(file, section_path)
        record = etree_transform_data_to_json(element)
      except Exception as e:
        record = {}
      # Override/augment with the text chunk's own details.
      record["text"] = chunk["text"]
      record["path"] = chunk["path"]
      record["inference_answers"] = chunk.get("llm_answers", {})
      final_output.append(record)
  
  # Write the final output as a JSON array (one record per text segment).
  with open("out/json_object.json", "w") as f:
    json.dump(final_output, f, indent=4)
  
  print(f"exported to out/json_object.json")
