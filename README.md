# DxHub eCR Freeform Information Extraction and Classification

## Setup:

1. Create a virtual environment:

```bash
python3.9 -m venv .venv
```

2. Install the required packages:

```bash
pip install -r requirements.txt
```

## Usage:

1. Run the following command to submit an eCR for LLM classification:

```bash
python src/embed.py <path_to_ecr>
```

2. Run the following command to test another eCR against the dataset of embeddings:

```bash
python src/test.py <path_to_ecr>
```

- After runnung `src/embed.py` the output embedding will be saved in the `embeddings/` directory under the filepath of the embedded file.
- Intermediate files that may be useful for debugging are saved in the `temp/` directory after running either `src/embed.py` or `src/test.py`
- Final xml test output file `xml_source_inference.xml` will be saved in the `out/` directory.
