import json
import os
from typing import Any

import boto3
import torch
from transformers import BertModel, BertTokenizer

model_id = "amazon.titan-embed-text-v1"
client = boto3.client(  # type: ignore
    "bedrock-runtime",
    region_name="us-west-2",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

bedrock = boto3.client(  # type: ignore
    "bedrock",
    region_name="us-west-2",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)


def test_bedrock():
    response = bedrock.list_foundation_models(  # type: ignore
        byOutputModality="EMBEDDING",
    )
    summarries = response["modelSummaries"]  # type: ignore
    for model in summarries:  # type: ignore
        print(model["modelName"], model["modelId"])  # type: ignore

    """
    Titan Text Embeddings v2 amazon.titan-embed-g1-text-02
    Titan Embeddings G1 - Text amazon.titan-embed-text-v1:2:8k
    Titan Embeddings G1 - Text amazon.titan-embed-text-v1
    Titan Text Embeddings V2 amazon.titan-embed-text-v2:0
    Titan Multimodal Embeddings G1 amazon.titan-embed-image-v1:0
    Titan Multimodal Embeddings G1 amazon.titan-embed-image-v1
    Embed English cohere.embed-english-v3:0:512
    Embed English cohere.embed-english-v3
    Embed Multilingual cohere.embed-multilingual-v3:0:512
    Embed Multilingual cohere.embed-multilingual-v3
    """


def embed_text(data: str) -> dict[str, Any]:
    # test_bedrock()
    # exit(0)
    native_request = {"inputText": data}
    request = json.dumps(native_request)

    response = client.invoke_model(modelId=model_id, body=request)  # type: ignore
    model_response = json.loads(response["body"].read())  # type: ignore

    embedding = model_response["embedding"]
    input_token_count = model_response["inputTextTokenCount"]

    print("input:", data)
    print(f"number of input tokens: {input_token_count}")
    print(f"embedding size: {len(embedding)}")
    print("embedding:", embedding[:10], "...")

    return model_response


# LOCAL

tokenizer = BertTokenizer.from_pretrained("dmis-lab/biobert-v1.1")  # type: ignore
model = BertModel.from_pretrained("dmis-lab/biobert-v1.1")  # type: ignore


def get_biobert_embeddings(data: dict[str, Any]) -> dict[str, Any]:
    # Tokenize the text
    text: str = data["text"]
    inputs = tokenizer(  # type: ignore
        text, return_tensors="pt", truncation=True, padding=True, max_length=512
    )

    # Get the embeddings from BioBERT
    with torch.no_grad():  # type: ignore
        outputs = model(**inputs)  # type: ignore

    # The embeddings are in outputs[0], which is the hidden states of the model
    # You can use the last hidden state or pooler_output
    embeddings = outputs.last_hidden_state.mean(  # type: ignore
        dim=1
    ).squeeze()  # Using mean of token embeddings

    embeddings = embeddings.tolist()  # type: ignore
    r = {  # type: ignore
        "chunk_id": data["chunk_id"],
        "path": data["path"],
        "chunk_size": data["chunk_size"],
        "embedding": embeddings,
    }

    return r  # type: ignore
