import json
import logging
from typing import Dict, Any, List, Tuple
import os
from collections import defaultdict
import pickle
from helpers import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SchemaEmbeddingsGenerator:
    def __init__(self, client, model_id: str):
        """Initialize the embeddings generator with Bedrock client and model ID."""
        self.client = client
        self.model_id = model_id
        self.field_embeddings = {}
        
    def _process_field(self, field_path: str, field_schema: Dict[str, Any]) -> None:
        """Process a single field to generate embeddings for its values and questions."""
        try:
            field_data = {
                'field_path': field_path,
                'type': field_schema.get('type', 'string'),
                'questions': field_schema.get('questions', []),
                'enum_values': field_schema.get('enum', []),
                'value_embeddings': {},
                'question_embeddings': []
            }
            
            # Generate embeddings for enum values if they exist
            if field_data['enum_values']:
                logger.info(f"Generating embeddings for enum values of {field_path}")
                value_embeddings = generate_batch_embeddings(
                    field_data['enum_values'],
                    self.client,
                    self.model_id
                )
                field_data['value_embeddings'] = {
                    value: embedding
                    for value, embedding in zip(field_data['enum_values'], value_embeddings)
                }
            
            # Generate embeddings for questions
            if field_data['questions']:
                logger.info(f"Generating embeddings for questions of {field_path}")
                # Add "Question:" prefix to each question
                prefixed_questions = [f"Question: {q}" for q in field_data['questions']]
                question_embeddings = generate_batch_embeddings(
                    prefixed_questions,
                    self.client,
                    self.model_id
                )
                field_data['question_embeddings'] = question_embeddings
            
            # Store the field data
            self.field_embeddings[field_path] = field_data
            
        except Exception as e:
            logger.error(f"Error processing field {field_path}: {str(e)}")

    def _process_schema_recursively(self, 
                                  schema: Dict[str, Any], 
                                  parent_path: str = "") -> None:
        """Recursively process all fields in the schema."""
        if 'properties' in schema:
            for field_name, field_schema in schema['properties'].items():
                field_path = f"{parent_path}.{field_name}" if parent_path else field_name
                
                if field_schema.get('type') == 'object':
                    # Recursively process nested objects
                    self._process_schema_recursively(field_schema, field_path)
                elif field_schema.get('type') == 'array' and 'items' in field_schema:
                    # Handle array types with nested objects
                    if field_schema['items'].get('type') == 'object':
                        self._process_schema_recursively(
                            field_schema['items'],
                            f"{field_path}[]"
                        )
                else:
                    # Process regular fields
                    self._process_field(field_path, field_schema)

    def generate_embeddings(self, schema: Dict[str, Any]) -> Dict[str, Dict]:
        """Generate embeddings for the entire schema."""
        logger.info("Starting embeddings generation process...")
        self._process_schema_recursively(schema)
        logger.info("Embeddings generation completed")
        return self.field_embeddings

class SchemaEmbeddingsSearcher:
    def __init__(self, field_embeddings: Dict[str, Dict]):
        """Initialize the searcher with pre-computed embeddings."""
        self.field_embeddings = field_embeddings

    def find_most_similar_field(self, 
                              query_text: str, 
                              client,
                              model_id: str,
                              top_k: int = 3) -> List[Tuple[str, float]]:
        """Find the most similar fields based on question similarity."""
        # Generate embedding for the query
        query_embedding = generate_batch_embeddings([query_text], client, model_id)[0]
        
        similarities = []
        for field_path, field_data in self.field_embeddings.items():
            # Skip fields without questions
            if not field_data['question_embeddings']:
                continue
                
            # Calculate max similarity with any question for this field
            max_similarity = max(
                batch_similarities(query_embedding, [q_emb])[0]  # Get the first (only) similarity value
                for q_emb in field_data['question_embeddings']
            )
            similarities.append((field_path, max_similarity))
        
        # Return top-k most similar fields
        return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_k]

    def find_most_similar_values(self,
                               field_path: str,
                               query_text: str,
                               client,
                               model_id: str,
                               top_k: int = 3) -> List[Tuple[str, float]]:
        """Find the most similar enum values for a specific field."""
        field_data = self.field_embeddings.get(field_path)
        if not field_data or not field_data['value_embeddings']:
            return []
            
        # Generate embedding for the query
        query_embedding = generate_batch_embeddings([query_text], client, model_id)[0]
        
        # Calculate similarities with all enum values
        similarities = []
        for value, value_embedding in field_data['value_embeddings'].items():
            similarity = batch_similarities(query_embedding, [value_embedding])[0]  # Get the first (only) similarity value
            similarities.append((value, similarity))
            
        return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_k]

def save_embeddings(embeddings: Dict[str, Dict], filename: str):
    """Save embeddings to a file using pickle."""
    with open(filename, 'wb') as f:
        pickle.dump(embeddings, f)

def load_embeddings(filename: str) -> Dict[str, Dict]:
    """Load embeddings from a file."""
    with open(filename, 'rb') as f:
        return pickle.load(f)

def main():
    try:
        # Initialize Bedrock client
        client = init_bedrock_client()
        # make test llm call
        q = "What is the capital of France?"
        model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        response = invoke_llm(q, client, model_id)
        print(f"Model Test Response: {response}")
        
        cohere_embed = "cohere.embed-english-v3"
        
        # Load the enriched schema
        input_file = "ecr_schema_with_questions.json"
        logger.info(f"Loading enriched schema from {input_file}")
        with open(input_file, 'r') as f:
            schema = json.load(f)
            
        # Generate embeddings
        generator = SchemaEmbeddingsGenerator(client, cohere_embed)
        field_embeddings = generator.generate_embeddings(schema)
        
        # Save embeddings
        output_file = "ecr_schema_embeddings.pkl"
        logger.info(f"Saving embeddings to {output_file}")
        save_embeddings(field_embeddings, output_file)
        
        # Example usage of the searcher
        logger.info("\nTesting embeddings search functionality...")
        searcher = SchemaEmbeddingsSearcher(field_embeddings)
        
        # Example: Find relevant fields for a query
        test_query = "What is the patient's gender?"
        similar_fields = searcher.find_most_similar_field(
            test_query,
            client,
            cohere_embed
        )
        logger.info(f"\nMost similar fields for query '{test_query}':")
        for field_path, similarity in similar_fields:
            logger.info(f"  {field_path}: {similarity:.4f}")
        
        # Example: Find similar values for a specific field
        if similar_fields:
            test_field = similar_fields[0][0]  # Use the most similar field
            test_value_query = "The patient identifies as a woman"
            similar_values = searcher.find_most_similar_values(
                test_field,
                test_value_query,
                client,
                cohere_embed
            )
            logger.info(f"\nMost similar values for field '{test_field}' with query '{test_value_query}':")
            for value, similarity in similar_values:
                logger.info(f"  {value}: {similarity:.4f}")
        
        logger.info("\nProcess completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()