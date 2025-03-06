## chunks

### setup

- basic stuff

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### usage

#### embedding documents

```python
python embed.py <path-to-document>
```

#### testing document

```python
python test.py <path-to-document>
```

#### intermediate files (out/)

- chunks.json: chunks with text and metadata
- similarities.json: similarity scores between chunks for test document chunks
- whole_doc_similarities.json: best similarity scores between chunks for test document chunks
- xml_source_inference.json: reconstructed document with llm inference
