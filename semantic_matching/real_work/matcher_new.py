import json
import pickle
import numpy as np
from typing import Dict, List, Tuple, Any
import logging
from collections import defaultdict
from bedrock_client import BedrockClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    logger.debug(f"Calculating cosine similarity between vectors of lengths {len(a)} and {len(b)}")
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

class DocumentSchemaMapper:
    def __init__(self, schema_embeddings_file: str, client: BedrockClient):
        """Initialize with schema embeddings and Bedrock client."""
        logger.info(f"Initializing DocumentSchemaMapper with schema file: {schema_embeddings_file}")
        self.client = client
        with open(schema_embeddings_file, 'rb') as f:
            self.schema_embeddings = pickle.load(f)
        logger.info(f"Loaded schema embeddings with {len(self.schema_embeddings)} fields")
        
        self.document_embeddings = {}
        try:
            with open("document_embeddings_new.pkl", "rb") as f:
                self.document_embeddings = pickle.load(f)
            logger.info(f"Loaded {len(self.document_embeddings)} document embeddings from disk")
        except FileNotFoundError:
            logger.info("No existing document embeddings found. Starting fresh.")

    def process_document(self, document_path: str) -> Dict[str, List[Tuple[str, float]]]:
        """Process document and find schema field matches."""
        logger.info(f"Processing document: {document_path}")
        with open(document_path, 'r') as f:
            doc_items = json.load(f)
        logger.info(f"Loaded document with {len(doc_items)} items")
        
        if not self.document_embeddings:
            logger.info("No document embeddings found, generating new ones")
            self._generate_document_embeddings(doc_items)
        else:
            logger.info("Using existing document embeddings")
            
        logger.info("Starting schema matching process")
        return self._find_schema_matches()

    def _generate_document_embeddings(self, doc_items: List[Dict[str, str]]) -> None:
        """Generate embeddings for document items using BedrockClient."""
        logger.info(f"Generating embeddings for {len(doc_items)} document items")
        combined_texts, path_texts, value_texts, items = [], [], [], []
        
        logger.debug("Preparing texts for embedding generation")
        for item in doc_items:
            path = item['path']
            value = item['value']
            combined_texts.append(f"{path} {value}")
            path_texts.append(path)
            value_texts.append(value)
            items.append(item)

        logger.info("Generating combined embeddings")
        combined_embeddings = self.client.generate_embeddings(combined_texts, "combined_embeddings.jsonl")
        logger.info("Generating path embeddings")
        path_embeddings = self.client.generate_embeddings(path_texts, "path_embeddings.jsonl")
        logger.info("Generating value embeddings")
        value_embeddings = self.client.generate_embeddings(value_texts, "value_embeddings.jsonl")

        logger.debug("Storing generated embeddings")
        for i, item in enumerate(items):
            self.document_embeddings[item['path']] = {
                'item': item,
                'combined_embedding': combined_embeddings[i],
                'path_embedding': path_embeddings[i],
                'value_embedding': value_embeddings[i]
            }
            
        with open("document_embeddings_new.pkl", "wb") as f:
            pickle.dump(self.document_embeddings, f)
        logger.info(f"Saved {len(self.document_embeddings)} document embeddings to disk")

    def _find_schema_matches(self, top_k: int = 10) -> Dict[str, List[Tuple[str, float]]]:
        """Match document items to schema fields using cosine similarity."""
        logger.info(f"Finding schema matches with top_k={top_k}")
        matches = defaultdict(list)
        
        logger.info(f"Processing {len(self.schema_embeddings)} schema fields")
        for field_path, field_data in self.schema_embeddings.items():
            field_matches = []
            if not (field_data.get('question_embeddings') or field_data.get('value_embeddings')):
                logger.debug(f"Skipping field {field_path} - no embeddings found")
                continue

            logger.debug(f"Processing field: {field_path}")
            for doc_path, doc_data in self.document_embeddings.items():
                max_sim = 0.0
                
                # Check question similarities
                if field_data.get('question_embeddings'):
                    logger.debug(f"Checking {len(field_data['question_embeddings'])} question embeddings")
                    for q_emb in field_data['question_embeddings']:
                        sim1 = cosine_similarity(q_emb, doc_data['combined_embedding'])
                        sim2 = cosine_similarity(q_emb, doc_data['path_embedding'])
                        max_sim = max(max_sim, sim1, sim2)
                        logger.debug(f"Question similarity scores: {sim1:.4f}, {sim2:.4f}")
                
                # Check value similarities
                if field_data.get('value_embeddings'):
                    logger.debug(f"Checking {len(field_data['value_embeddings'])} value embeddings")
                    for val_emb in field_data['value_embeddings'].values():
                        sim = cosine_similarity(val_emb, doc_data['value_embedding'])
                        max_sim = max(max_sim, sim)
                        logger.debug(f"Value similarity score: {sim:.4f}")
                
                if max_sim > 0.3:
                    logger.debug(f"Found match with similarity {max_sim:.4f} for {doc_path}")
                    field_matches.append((doc_data['item']['value'], max_sim))
            
            # Keep top matches
            field_matches.sort(key=lambda x: x[1], reverse=True)
            matches[field_path] = field_matches[:top_k]
            logger.info(f"Found {len(matches[field_path])} matches for field {field_path}")
            
        return matches

def main():
    try:
        logger.info("Starting main execution")
        # Initialize Bedrock client with appropriate credentials
        logger.info("Initializing Bedrock client")
        client = BedrockClient(
            region='us-west-2',
            account_id='REMOVED_ID',
            profile_name='public-records-profile'
        )
        
        # Create mapper and process document
        logger.info("Creating DocumentSchemaMapper instance")
        mapper = DocumentSchemaMapper("../ecr_schema_embeddings.pkl", client)
        logger.info("Processing document")
        matches = mapper.process_document("../out/step4_filtered.json")
        
        # Save and display results
        logger.info("Saving results to schema_matches_new.json")
        with open("schema_matches_new.json", 'w') as f:
            json.dump(matches, f, indent=2)
            
        logger.info("Displaying top matches")
        print("\nTop matches:")
        for field, matches_list in list(matches.items())[:5]:
            print(f"\n{field}:")
            for val, sim in matches_list[:3]:
                print(f"  {val}: {sim:.4f}")
                
        logger.info("Main execution completed successfully")
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    logger.info("Starting script execution")
    main()
    logger.info("Script execution completed")