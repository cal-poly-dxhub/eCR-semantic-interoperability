from helpers import *

client = init_bedrock_client()
texts = [
    "Interesting (Non software) books?",
    "Non-tech books that have helped you grow professionally?",
    "I sold my company last month for $5m. What do I do with the money?",
]
embeddings = generate_batch_embeddings(
    texts, 
    client, 
    model_id="cohere.embed-english-v3",
    input_type="search_document",
    truncate="END"
)
print(embeddings)
