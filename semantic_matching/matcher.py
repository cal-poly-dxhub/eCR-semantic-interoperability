import json
import pickle
from typing import Dict, List, Tuple, Any
import logging
from collections import defaultdict
from helpers import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentSchemaMapper:
    def __init__(self, schema_embeddings_file: str, client, model_id: str):
        """Initialize with schema embeddings and embedding model."""
        self.client = client
        self.model_id = model_id
        with open(schema_embeddings_file, 'rb') as f:
            self.schema_embeddings = pickle.load(f)
        # self.document_embeddings = {}
        # Load document embeddings if they exist
        self.document_embeddings = {}
        try:
            with open("document_embeddings_new.pkl", "rb") as f:
                self.document_embeddings = pickle.load(f)
            logger.info("Loaded document embeddings from disk.")
        except FileNotFoundError:
            logger.info("No existing document embeddings found. Starting from scratch.")

    def process_document(self, document_path: str) -> Dict[str, List[Tuple[str, float]]]:
        """Process document and find matches for schema fields."""
        # Load and process document
        with open(document_path, 'r') as f:
            doc_items = json.load(f)

        # Generate embeddings for document items
        if not self.document_embeddings:
            self._generate_document_embeddings(doc_items)
        
        # Match against schema fields
        matches = self._find_schema_matches()
        
        return matches

    # def _generate_document_embeddings(self, doc_items: List[Dict[str, str]]) -> None:
    #     """Generate embeddings for document items."""
    #     logger.info("Generating document embeddings...")
        
    #     # Prepare texts for batch embedding
    #     combined_texts = []
    #     path_texts = []
    #     value_texts = []
    #     items = []
        
    #     for item in doc_items:
    #         path = item['path']
    #         value = item['value']
    #         combined_text = f"{path} {value}"
            
    #         combined_texts.append(combined_text)
    #         path_texts.append(path)
    #         value_texts.append(value)
    #         items.append(item)

    #     # Generate embeddings in batches
    #     combined_embeddings = generate_batch_embeddings(combined_texts, self.client, self.model_id)
    #     path_embeddings = generate_batch_embeddings(path_texts, self.client, self.model_id)
    #     value_embeddings = generate_batch_embeddings(value_texts, self.client, self.model_id)

    #     # Store embeddings
    #     for i, item in enumerate(items):
    #         self.document_embeddings[item['path']] = {
    #             'item': item,
    #             'combined_embedding': combined_embeddings[i],
    #             'path_embedding': path_embeddings[i],
    #             'value_embedding': value_embeddings[i]
    #         }

    def _generate_document_embeddings(self, doc_items: List[Dict[str, str]]) -> None:
        """Generate embeddings for document items."""
        logger.info("Generating document embeddings...")
        
        # Prepare texts for embedding
        combined_texts = []
        path_texts = []
        value_texts = []
        items = []
        
        for item in doc_items:
            path = item['path']
            value = item['value']
            combined_text = f"{path} {value}"
            
            combined_texts.append(combined_text)
            path_texts.append(path)
            value_texts.append(value)
            items.append(item)

        # Debugging: Inspect the input data
        logger.info(f"Total items: {len(doc_items)}")
        logger.info(f"Sample combined text: {combined_texts[0]}")
        logger.info(f"Sample path text: {path_texts[0]}")
        logger.info(f"Sample value text: {value_texts[0]}")

        # Generate embeddings sequentially
        combined_embeddings = generate_batch_embeddings(
            combined_texts, 
            self.client, 
            model_id=self.model_id,
            input_type="search_document",  # Adjust as needed
            truncate="END"  # Truncate long texts from the end
        )
        path_embeddings = generate_batch_embeddings(
            path_texts, 
            self.client, 
            model_id=self.model_id,
            input_type="search_document",  # Adjust as needed
            truncate="END"  # Truncate long texts from the end
        )
        value_embeddings = generate_batch_embeddings(
            value_texts, 
            self.client, 
            model_id=self.model_id,
            input_type="search_document",  # Adjust as needed
            truncate="END"  # Truncate long texts from the end
        )

        # Store embeddings
        for i, item in enumerate(items):
            self.document_embeddings[item['path']] = {
                'item': item,
                'combined_embedding': combined_embeddings[i],
                'path_embedding': path_embeddings[i],
                'value_embedding': value_embeddings[i]
            }
        with open("document_embeddings_new.pkl", "wb") as f:
            pickle.dump(self.document_embeddings, f)
    logger.info("Document embeddings saved to disk.")
    def _find_schema_matches(self, top_k: int = 10) -> Dict[str, List[Tuple[str, float]]]:
        """Find matches between document items and schema fields."""
        logger.info("Finding matches for schema fields...")
        
        matches = {}
        
        for field_path, field_data in self.schema_embeddings.items():
            field_matches = []
            
            # Skip if field has no questions or values
            if not (field_data.get('question_embeddings') or field_data.get('value_embeddings')):
                continue

            # Calculate similarities for each document item
            for doc_path, doc_data in self.document_embeddings.items():
                max_similarity = 0.0
                
                # Check question similarities
                if field_data.get('question_embeddings'):
                    for q_emb in field_data['question_embeddings']:
                        # Try both combined and path embeddings
                        sim1 = batch_similarities(q_emb, [doc_data['combined_embedding']])[0]
                        sim2 = batch_similarities(q_emb, [doc_data['path_embedding']])[0]
                        max_similarity = max(max_similarity, sim1, sim2)

                # Check value similarities if field has enum values
                if field_data.get('value_embeddings'):
                    for val_emb in field_data['value_embeddings'].values():
                        sim = batch_similarities(val_emb, [doc_data['value_embedding']])[0]
                        max_similarity = max(max_similarity, sim)

                if max_similarity > 0.3:  # Similarity threshold
                    field_matches.append((doc_data['item']['value'], max_similarity))

            # Sort and keep top_k matches
            field_matches.sort(key=lambda x: x[1], reverse=True)
            if field_matches:
                matches[field_path] = field_matches[:top_k]

        return matches

def main():
    try:
        # Initialize
        client = init_bedrock_client()
        cohere_embed = "cohere.embed-english-v3"
        
        # Create mapper
        mapper = DocumentSchemaMapper(
            "ecr_schema_embeddings.pkl",
            client,
            cohere_embed
        )
        
        # Process document
        matches = mapper.process_document("out/step4_filtered.json")
        
        # Save results
        output_file = "schema_matches_new.json"
        with open(output_file, 'w') as f:
            json.dump(matches, f, indent=2)
            
        # Print some example matches
        print("\nExample matches (top 3 for first 5 fields):")
        for i, (field, matches) in enumerate(matches.items()):
            if i >= 5:
                break
            print(f"\nField: {field}")
            for value, similarity in matches[:3]:
                print(f"  {value}: {similarity:.4f}")

    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()