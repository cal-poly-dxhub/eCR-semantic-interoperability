import pickle
import logging
from typing import List, Tuple, Dict, Any
from helpers import *

class SchemaSearchInterface:
    def __init__(self, embeddings_file: str, client, model_id: str):
        """Initialize search interface with pre-computed embeddings."""
        with open(embeddings_file, 'rb') as f:
            self.field_embeddings = pickle.load(f)
        self.client = client
        self.model_id = model_id

    def search_fields(self, query: str, top_k: int = 5) -> List[Tuple[str, float, List[str]]]:
        """Search for relevant fields based on a query.
        Returns: List of (field_path, similarity, questions)"""
        query_embedding = generate_batch_embeddings([query], self.client, self.model_id)[0]
        
        results = []
        for field_path, field_data in self.field_embeddings.items():
            if not field_data['question_embeddings']:
                continue
                
            max_similarity = max(
                batch_similarities(query_embedding, [q_emb])[0]
                for q_emb in field_data['question_embeddings']
            )
            results.append((
                field_path, 
                max_similarity,
                field_data['questions']
            ))
            
        return sorted(results, key=lambda x: x[1], reverse=True)[:top_k]

    def search_field_values(self, field_path: str, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Search for similar values within a specific field."""
        field_data = self.field_embeddings.get(field_path)
        if not field_data or not field_data['value_embeddings']:
            return []
            
        query_embedding = generate_batch_embeddings([query], self.client, self.model_id)[0]
        similarities = []
        
        for value, value_embedding in field_data['value_embeddings'].items():
            similarity = batch_similarities(query_embedding, [value_embedding])[0]
            similarities.append((value, similarity))
            
        return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_k]

    def get_field_info(self, field_path: str) -> Dict[str, Any]:
        """Get all information about a specific field."""
        return self.field_embeddings.get(field_path, {})

    def list_fields(self) -> List[str]:
        """List all available fields."""
        return sorted(self.field_embeddings.keys())

def main():
    # Example usage
    client = init_bedrock_client()
    cohere_embed = "cohere.embed-english-v3"
    
    interface = SchemaSearchInterface("ecr_schema_embeddings.pkl", client, cohere_embed)
    
    while True:
        print("\nSchema Search Interface")
        print("1. Search fields by question")
        print("2. Search values in a field")
        print("3. Show field information")
        print("4. List all fields")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == "1":
            query = input("Enter your question: ")
            results = interface.search_fields(query)
            print("\nMatching fields:")
            for field, similarity, questions in results:
                print(f"\nField: {field} (Similarity: {similarity:.4f})")
                print("Related questions:")
                for q in questions:
                    print(f"  - {q}")
                    
        elif choice == "2":
            field = input("Enter field path: ")
            query = input("Enter search text: ")
            results = interface.search_field_values(field, query)
            print("\nMatching values:")
            for value, similarity in results:
                print(f"  {value}: {similarity:.4f}")
                
        elif choice == "3":
            field = input("Enter field path: ")
            info = interface.get_field_info(field)
            print("\nField information:")
            print(json.dumps(info, indent=2))
            
        elif choice == "4":
            fields = interface.list_fields()
            print("\nAvailable fields:")
            for field in fields:
                print(f"  - {field}")
                
        elif choice == "5":
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()