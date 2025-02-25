import json
import numpy as np
from bedrock_client import BedrockClient  # Assuming your class is in bedrock_client.py

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def test_embeddings():
    print("🚀 Starting embeddings validation test...\n")
    
    # Initialize client
    client = BedrockClient()
    embeddings_file = "test_embeddings.jsonl"
    
    # Test data - carefully chosen samples
    questions = [
        "What is the capital of France?",
        "How does photosynthesis work?"
    ]
    
    answers = [
        {"text": "Paris is the capital city of France", "expected_score": 0.85},
        {"text": "Berlin is the capital of Germany", "expected_score": 0.65},
        {"text": "Plants convert sunlight into energy through photosynthesis", "expected_score": 0.90},
        {"text": "The mitochondria is the powerhouse of the cell", "expected_score": 0.40},
        {"text": "French cuisine is famous for its pastries", "expected_score": 0.35},
    ]
    
    # Generate embeddings for all texts
    print("🔧 Generating embeddings for all test texts...")
    all_texts = [q for q in questions] + [a["text"] for a in answers]
    client.generate_embeddings(all_texts, filename=embeddings_file)
    print("✅ Embeddings generated successfully\n")
    
    # Load embeddings from file
    print("📂 Loading generated embeddings...")
    embeddings = {}
    with open(embeddings_file, "r") as f:
        for line in f:
            data = json.loads(line)
            embeddings[data["text"]] = data["embedding"]
    print(f"📊 Loaded {len(embeddings)} embeddings\n")
    
    # Validate embeddings
    print("🔍 Running similarity checks...")
    for i, question in enumerate(questions):
        print(f"\n🔎 Testing question {i+1}: '{question}'")
        q_embedding = embeddings[question]
        
        print(f"  {'Answer':<60} {'Similarity':<10} {'Status'}")
        print("  " + "-"*80)
        
        results = []
        for answer in answers:
            a_embedding = embeddings[answer["text"]]
            similarity = cosine_similarity(q_embedding, a_embedding)
            results.append((answer["text"], similarity, answer["expected_score"]))
        
        # Sort by similarity score descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Print and validate results
        passed = True
        for text, score, expected in results:
            status = "PASS" if score >= expected else f"FAIL (Expected ≥{expected})"
            print(f"  {text:<60} {score:.4f}     {status}")
            
            if score < expected:
                passed = False
            
        if not passed:
            print(f"\n❌ Validation failed for question: '{question}'")
        else:
            print(f"\n✅ All checks passed for question: '{question}'")
    
    print("\n🧪 Test complete. Check results above for validation status.")

if __name__ == "__main__":
    test_embeddings()