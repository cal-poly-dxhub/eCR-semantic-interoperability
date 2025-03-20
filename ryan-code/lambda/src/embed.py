import json
import os
import sys
from typing import Any

from .chunky import extract_relevant_chunks
from .vectoring import embed_text

pathext = "/tmp/out/"

def cleanup() -> None:
  """
  Cleans up the output directory by removing existing files.
  If the directory doesn't exist, it creates one.
  """
  if os.path.exists(pathext):
    for file in os.listdir(pathext):
      os.remove(os.path.join(pathext, file))
  else:
    os.mkdir(pathext)

def process_embed(file_path: str) -> str:
  """
  Processes the XML file by extracting chunks and computing embeddings.
  Writes the chunks and embeddings to output files.
  
  Parameters:
    file_path (str): Path to the XML file.
  
  Returns:
    str: The output path for the embeddings JSON file.
  """
  # Clean up output directory
  cleanup()
  print("process_emebd file:",file_path)
  # Extract chunks from the XML file
  chunks = extract_relevant_chunks(file_path)
  chunks_output_path = os.path.join(pathext, "chunks.json")
  with open(chunks_output_path, "w") as f:
    try:
      json.dump(chunks, f)
    except Exception as e:
      print(e)
      print(type(e))
      print("open in process_embed, line 39")

  # Compute embeddings for each chunk
  embeddings = [embed_text(chunk) for chunk in chunks]
  # Determine output path based on the input file's basename
  output_filename = os.path.basename(file_path).replace(".xml", ".json")
  output_path = os.path.join("/tmp/embeddings", output_filename)
  os.makedirs(os.path.dirname(output_path), exist_ok=True)
  with open(output_path, "w") as f:
    try:
      json.dump(embeddings, f, indent=4)
    except Exception as e:
      print(e)
      print(type(e))
      print("open in process_embed, line 49")
  
  return output_path

if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("usage: python embed.py <xml_file>")
    sys.exit(1)
  file_path = sys.argv[1]
  result = process_embed(file_path)
  print(f"Embeddings written to {result}")