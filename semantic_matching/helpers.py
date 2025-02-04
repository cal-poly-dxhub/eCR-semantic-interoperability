import boto3
import json
import numpy as np
import tiktoken
from typing import List, Dict
from dotenv import load_dotenv
import os
import time

# Load environment variables if .env exists
load_dotenv()

def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception as e:
        print(f"Warning: Error counting tokens: {e}. Using character-based approximation.")
        return len(text) // 4

# def truncate_text(text: str, max_tokens: int = 7900) -> str:
#     """Truncate text to stay within token limit."""
#     current_tokens = count_tokens(text)
#     if current_tokens <= max_tokens:
#         return text
    
#     encoding = tiktoken.get_encoding("cl100k_base")
#     tokens = encoding.encode(text)
#     truncated_tokens = tokens[:max_tokens-50]
#     return encoding.decode(truncated_tokens)
def truncate_text(text: str, max_tokens: int = 7900, max_chars: int = None) -> str:
    """Truncate text to stay within token or character limit."""
    if max_chars and len(text) > max_chars:
        return text[:max_chars]
    
    current_tokens = count_tokens(text)
    if current_tokens <= max_tokens:
        return text
    
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    truncated_tokens = tokens[:max_tokens - 50]
    return encoding.decode(truncated_tokens)

def init_bedrock_client(profile_name: str = "ecr-profile", region_name: str = "us-west-2"):
    """
    Initialize AWS Bedrock client using AWS SSO credentials.
    
    Args:
        profile_name: AWS profile name (default: ecr-profile)
        region_name: AWS region name (default: us-west-2)
    """
    try:
        # Create a session with the specified profile
        session = boto3.Session(profile_name=profile_name)
        
        # Create the bedrock client using the session
        return session.client('bedrock-runtime', region_name=region_name)
    except Exception as e:
        print(f"Error initializing Bedrock client: {str(e)}")
        print("Make sure:")
        print("1. You've run 'asp ecr-profile' to refresh SSO credentials")
        print("2. Your AWS SSO session is active")
        raise

def generate_embedding(text: str, 
                      client,
                      model_id: str) -> List[float]:
    """Generate embeddings for given text using AWS Bedrock."""
    text = truncate_text(text)
    body = json.dumps({"inputText": text})
    response = client.invoke_model(modelId=model_id, body=body)
    return json.loads(response['body'].read())['embedding']

def invoke_llm(prompt: str, 
               client, 
               model_id: str,
               max_tokens: int = 1000,
               temperature: float = 0.7,
               top_p: float = 1.0,
               stop_sequences: List[str] = None) -> str:
    """
    Invoke LLM model to generate text response using message format.
    """
    prompt = truncate_text(prompt)
    
    inference_config = {
        "temperature": temperature,
        "maxTokens": max_tokens,
        "topP": top_p,
    }
    
    if stop_sequences:
        inference_config["stopSequences"] = stop_sequences
    
    messages = [
        {
            "role": "user",
            "content": [{"text": prompt}]
        }
    ]
    
    try:
        response = client.converse(
            modelId=model_id,
            messages=messages,
            inferenceConfig=inference_config,
        )
        return response['output']['message']['content'][0]['text']
    except Exception as e:
        print(f"Error invoking model: {str(e)}")
        if "ThrottlingException" in str(e):
            # wait 3 seconds and retry
            print("ThrottlingException, retrying in 3 seconds")
            time.sleep(3)
            return invoke_llm(prompt, client, model_id, max_tokens, temperature, top_p, stop_sequences)
            
        print("If using SSO, try refreshing your credentials with 'asp ecr-profile'")
        raise

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    return dot_product / (norm_v1 * norm_v2)

def generate_batch_embeddings(
    texts: List[str],
    client,
    model_id: str = "cohere.embed-english-v3",
    input_type: str = "search_document",
    truncate: str = "END",
    max_text_length: int = 2048
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts using AWS Bedrock with Cohere model.
    
    Args:
        texts: List of texts to generate embeddings for
        client: AWS Bedrock client
        model_id: Model ID (default: cohere.embed-english-v3)
        input_type: Input type for embedding (default: search_document)
        truncate: Truncation strategy (default: "END")
        max_text_length: Maximum length of each text (default: 2048)
        
    Returns:
        List of embeddings (one per input text)
    """
    embeddings = []
    
    for i, text in enumerate(texts):
        # Truncate the text to stay within character limits
        truncated_text = truncate_text(text, max_chars=max_text_length)
        
        # Prepare the request body
        body = json.dumps({
            "texts": [truncated_text],  # Send one text at a time
            "input_type": input_type,
            "truncate": truncate
        })
        
        try:
            # Make the API call
            response = client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            
            # Parse and append the embeddings
            response_body = json.loads(response['body'].read())
            embeddings.extend(response_body['embeddings'])
            
            # Log progress
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1} of {len(texts)} texts")
        
        except Exception as e:
            print(f"Error generating embedding for text {i + 1}: {str(e)}")
            print(f"Text: {truncated_text}")
            print("If using SSO, try refreshing your credentials with 'asp ecr-profile'")
            raise
    
    return embeddings
# def generate_batch_embeddings(
#     texts: List[str],
#     client,
#     model_id: str = "cohere.embed-english-v3",
#     input_type: str = "search_document",
#     truncate: str = "NONE",
#     batch_size: int = 128,
#     max_text_length: int = 2048
# ) -> List[List[float]]:
#     """
#     Generate embeddings for multiple texts using AWS Bedrock with Cohere model.
    
#     Args:
#         texts: List of texts to generate embeddings for
#         client: AWS Bedrock client
#         model_id: Model ID (default: cohere.embed-english-v3)
#         input_type: Input type for embedding (default: search_document)
#         truncate: Truncation strategy (default: "NONE")
#         batch_size: Maximum number of texts per batch (default: 128)
#         max_text_length: Maximum length of each text (default: 2048)
        
#     Returns:
#         List of embeddings (one per input text)
#     """
#     # Truncate each text to stay within character limits
#     truncated_texts = [truncate_text(text, max_chars=max_text_length) for text in texts]
    
#     # Split texts into batches
#     embeddings = []
#     for i in range(0, len(truncated_texts), batch_size):
#         batch_texts = truncated_texts[i:i + batch_size]
        
#         # Prepare the request body
#         body = json.dumps({
#             "texts": batch_texts,
#             "input_type": input_type,
#             "truncate": truncate
#         })
        
#         try:
#             # Make the API call
#             response = client.invoke_model(
#                 modelId=model_id,
#                 body=body,
#                 contentType="application/json",
#                 accept="application/json"
#             )
            
#             # Parse and append the embeddings
#             response_body = json.loads(response['body'].read())
#             embeddings.extend(response_body['embeddings'])
            
#         except Exception as e:
#             print(f"Error generating batch embeddings: {str(e)}")
#             print("If using SSO, try refreshing your credentials with 'asp ecr-profile'")
#             raise
    
#     return embeddings
# def generate_batch_embeddings(
#     texts: List[str],
#     client,
#     model_id: str = "cohere.embed-english-v3",
#     input_type: str = "search_document",
#     batch_size: int = 128,
#     max_text_length: int = 2048
# ) -> List[List[float]]:
#     """
#     Generate embeddings for multiple texts using AWS Bedrock with Cohere model.
    
#     Args:
#         texts: List of texts to generate embeddings for
#         client: AWS Bedrock client
#         model_id: Model ID (default: cohere.embed-english-v3)
#         input_type: Input type for embedding (default: search_document)
#         batch_size: Maximum number of texts per batch (default: 128)
#         max_text_length: Maximum length of each text (default: 2048)
        
#     Returns:
#         List of embeddings (one per input text)
#     """
#     # Truncate each text to stay within character limits
#     truncated_texts = [truncate_text(text, max_chars=max_text_length) for text in texts]
    
#     # Split texts into batches
#     embeddings = []
#     for i in range(0, len(truncated_texts), batch_size):
#         batch_texts = truncated_texts[i:i + batch_size]
        
#         # Prepare the request body
#         body = json.dumps({
#             "texts": batch_texts,
#             "input_type": input_type
#         })
        
#         try:
#             # Make the API call
#             response = client.invoke_model(
#                 modelId=model_id,
#                 body=body,
#                 contentType="application/json",
#                 accept="application/json"
#             )
            
#             # Parse and append the embeddings
#             response_body = json.loads(response['body'].read())
#             embeddings.extend(response_body['embeddings'])
            
#         except Exception as e:
#             print(f"Error generating batch embeddings: {str(e)}")
#             print(f"Texts: {batch_texts}")
#             print("If using SSO, try refreshing your credentials with 'asp ecr-profile'")
#             raise
    
#     return embeddings
def batch_similarities(query_embedding: List[float], 
                      reference_embeddings: List[List[float]]) -> List[float]:
    """Calculate cosine similarities between one query and multiple reference embeddings."""
    query_array = np.array(query_embedding)
    reference_array = np.array(reference_embeddings)
    
    # Normalize vectors
    query_norm = np.linalg.norm(query_array)
    reference_norms = np.linalg.norm(reference_array, axis=1)
    
    # Calculate similarities
    similarities = np.dot(reference_array, query_array) / (reference_norms * query_norm)
    return similarities.tolist()

# def generate_batch_embeddings(texts: List[str],
#                            client,
#                            model_id: str = "cohere.embed-english-v3",
#                            input_type: str = "search_document") -> List[List[float]]:
#     """
#     Generate embeddings for multiple texts using AWS Bedrock with Cohere model.
    
#     Args:
#         texts: List of texts to generate embeddings for
#         client: AWS Bedrock client
#         model_id: Model ID (default: cohere.embed-english-v3)
#         input_type: Input type for embedding (default: search_document)
        
#     Returns:
#         List of embeddings (one per input text)
#     """
#     # Truncate each text to stay within token limits
#     truncated_texts = [truncate_text(text) for text in texts]
    
#     print(f"Generating embeddings for {len(truncated_texts)} texts...")
#     # Prepare the request body
#     body = json.dumps({
#         "texts": truncated_texts,
#         "input_type": input_type
#     })
    
#     try:
#         # Make the API call
#         response = client.invoke_model(
#             modelId=model_id,
#             body=body,
#             contentType="application/json",
#             accept="*/*"
#         )
        
#         # Parse and return the embeddings
#         response_body = json.loads(response['body'].read())
#         return response_body['embeddings']
        
#     except Exception as e:
#         print(f"Error generating batch embeddings: {str(e)}")
#         print("If using SSO, try refreshing your credentials with 'asp ecr-profile'")
#         raise