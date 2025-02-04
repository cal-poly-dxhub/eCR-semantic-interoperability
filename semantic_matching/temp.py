from helpers import *
import json
from tqdm import tqdm
import pickle as pkl
from operator import itemgetter

def save_progress(matches, filename="results.txt"):
    """Save current progress to a text file in descending order of scores."""
    # Sort matches by score in descending order
    sorted_matches = sorted(matches, key=itemgetter('score'), reverse=True)
    
    # Write to text file
    with open(filename, 'w') as f:
        for match in sorted_matches:
            f.write(f"Score: {match['score']:.4f}\n")
            f.write(f"Text: {match['text']}\n")
            f.write("-" * 50 + "\n")

def process_embeddings():
    # Initialize the client
    client = init_bedrock_client()
    sonnet_35 = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    titan_embed = "amazon.titan-embed-text-v2:0"
    cohere_embed = "cohere.embed-english-v3"
    
    # File path
    file_path = "/Users/swayamchidrawar/repos/eCR-semantic-interoperability/semantic_matching/out/step4_filtered.json"
    
    # Initialize lists to store data
    matches = []
    processed_count = 0
    
    try:
        # Generate question embedding first
        question = "Question: What is the title of this report?"
        # question_embedding = generate_embedding(question, client, titan_embed)
        question_embedding = generate_batch_embeddings([question], client, cohere_embed)[0]
        
        # Read and process the JSON file
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        # Process each item
        for item in tqdm(data, desc="Embedding Progress", unit="item"):
            try:
                if "value" in item:
                    embed_text = item["value"].strip()
                    if embed_text:  # Only process non-empty strings
                        # Generate embedding
                        # embedding = generate_embedding(embed_text, client, titan_embed)
                        embedding = generate_batch_embeddings([embed_text], client, cohere_embed)[0]
                        
                        # Calculate similarity immediately
                        score = batch_similarities(question_embedding, [embedding])[0]
                        
                        # Store the match
                        matches.append({
                            'text': embed_text,
                            'embedding': embedding,
                            'score': score
                        })
                        
                        processed_count += 1
                        
                        # Save progress every 10 items
                        if processed_count % 10 == 0:
                            save_progress(matches)
                            
                            # Also save binary backup
                            with open("matches_backup.pkl", "wb") as f:
                                pkl.dump(matches, f)
                            
                            print(f"Progress saved. Processed {processed_count} items.")
                            
            except Exception as e:
                print(f"Error processing item: {str(e)}")
                continue  # Continue with next item even if current one fails
                
        # Final save
        save_progress(matches)
        with open("matches_final.pkl", "wb") as f:
            pkl.dump(matches, f)
                
        print(f"Processing complete! Processed {processed_count} texts.")
        print("Results saved to results.txt in descending order of similarity.")
                
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        # Save whatever progress we have
        if matches:
            save_progress(matches, "results_incomplete.txt")
            with open("matches_incomplete.pkl", "wb") as f:
                pkl.dump(matches, f)
            print("Partial progress saved to results_incomplete.txt")

if __name__ == "__main__":
    process_embeddings()
    # client = init_bedrock_client()
    # titan_embed = "amazon.titan-embed-text-v2:0"
    # cohere_embed = "cohere.embed-english-v3"
    # capitals = ["London", "Paris", "Berlin", "Madrid", "Rome"]
    # query = "What is the capital of France?"

    # # Titan embeddings (unchanged)
    # capital_embeddings = [generate_embedding(capital, client, titan_embed) for capital in capitals]
    # query_embedding = generate_embedding(query, client, titan_embed)
    # similarities = batch_similarities(query_embedding, capital_embeddings)
    # print("Titan similarities:", similarities)

    # # Cohere embeddings (updated to use batch processing)
    # capital_embeddings = generate_batch_embeddings(capitals, client, cohere_embed)
    # query_embeddings = generate_batch_embeddings([query], client, cohere_embed)[0]  # Get first embedding since we only have one query
    # similarities = batch_similarities(query_embeddings, capital_embeddings)
    # print("Cohere similarities:", similarities)