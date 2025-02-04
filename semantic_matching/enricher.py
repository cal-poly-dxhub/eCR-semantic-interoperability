import json
import logging
from typing import Dict, Any, List
import os
from copy import deepcopy
from helpers import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SchemaQuestionEnricher:
    def __init__(self, client, model_id: str):
        """Initialize the enricher with Bedrock client and model ID."""
        self.client = client
        self.model_id = model_id
        
    def _generate_prompt(self, field_name: str, field_schema: Dict[str, Any]) -> str:
        """Generate an appropriate prompt based on field type and properties."""
        field_type = field_schema.get('type', 'string')
        description = field_schema.get('description', '')
        enum_values = field_schema.get('enum', [])
        
        prompt = f"""Generate 5 clear, concise questions that would help collect information for a field named "{field_name}" in a medical form. 

Field details:
- Type: {field_type}
- Description: {description}
"""

        if enum_values:
            prompt += f"- Possible values: {', '.join(enum_values)}\n"
            prompt += "\nMake sure the questions are appropriate for collecting this specific enumerated information."
            
        prompt += """
Format your response as a Python list of strings, like this:
["Question 1?", "Question 2?", "Question 3?", "Question 4?", "Question 5?"]

Ensure each question:
1. Is clear and unambiguous
2. Uses appropriate medical terminology when relevant
3. Can be answered with the field's data type
4. Is specific to the field's purpose
"""

        return prompt

    def _parse_llm_response(self, response: str) -> List[str]:
        """Parse the LLM response to extract the list of questions."""
        print(f"Parse response: {response}")
        try:
            # Find the list in the response using string manipulation
            start_idx = response.find('[')
            end_idx = response.rfind(']') + 1
            if start_idx == -1 or end_idx == 0:
                raise ValueError("Could not find valid list in response")
            
            questions_str = response[start_idx:end_idx]
            questions = eval(questions_str)  # Safe since we control the input format
            
            # Validate the result
            if not isinstance(questions, list) or not all(isinstance(q, str) for q in questions):
                raise ValueError("Invalid question format")
                
            return questions
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            logger.error(f"Raw response: {response}")
            return ["What is the value for this field?"]  # Fallback question

    def _process_field(self, field_name: str, field_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single field and generate questions for it."""
        print(f"Processing field: {field_name}")
        # Skip processing if this is an object or array type
        if field_schema.get('type') in ['object', 'array']:
            return field_schema

        try:
            # Generate and send prompt to LLM
            prompt = self._generate_prompt(field_name, field_schema)
            response = invoke_llm(
                prompt=prompt,
                client=self.client,
                model_id=self.model_id,
                temperature=0.7
            )
            
            # Parse questions from response
            questions = self._parse_llm_response(response)
            
            # Create a new schema with questions added
            new_schema = deepcopy(field_schema)
            new_schema['questions'] = questions
            
            return new_schema
            
        except Exception as e:
            logger.error(f"Error processing field {field_name}: {str(e)}")
            return field_schema

    def _process_schema_recursively(self, schema: Dict[str, Any], parent_key: str = "") -> Dict[str, Any]:
        """Recursively process all fields in the schema."""
        print(f"Processing schema: {schema}")
        new_schema = deepcopy(schema)
        
        if 'properties' in schema:
            new_properties = {}
            for field_name, field_schema in schema['properties'].items():
                full_field_name = f"{parent_key}.{field_name}" if parent_key else field_name
                logger.info(f"Processing field: {full_field_name}")
                
                if field_schema.get('type') == 'object':
                    # Recursively process nested objects
                    new_properties[field_name] = self._process_schema_recursively(
                        field_schema, 
                        full_field_name
                    )
                elif field_schema.get('type') == 'array' and 'items' in field_schema:
                    # Handle array types with nested objects
                    if field_schema['items'].get('type') == 'object':
                        field_schema['items'] = self._process_schema_recursively(
                            field_schema['items'],
                            f"{full_field_name}[]"
                        )
                    new_properties[field_name] = field_schema
                else:
                    # Process regular fields
                    new_properties[field_name] = self._process_field(full_field_name, field_schema)
                    
            new_schema['properties'] = new_properties
            
        return new_schema

    def enrich_schema(self, input_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich the entire schema with questions."""
        print(f"Enriching schema: {input_schema}")
        logger.info("Starting schema enrichment process...")
        enriched_schema = self._process_schema_recursively(input_schema)
        logger.info("Schema enrichment completed")
        return enriched_schema

def main():
    try:
        # Initialize Bedrock client
        print("Initializing Bedrock client...")
        client = init_bedrock_client()
        print("Bedrock client initialized successfully!")
        # make test llm call
        q = "What is the capital of France?"
        model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        response = invoke_llm(q, client, model_id)
        print(f"Model Test Response: {response}")
        
        # Load the schema
        input_file = "ecr_schema.json"
        logger.info(f"Loading schema from {input_file}")
        with open(input_file, 'r') as f:
            schema = json.load(f)
            
        # Create enricher and process schema
        print("Creating schema enricher...")
        enricher = SchemaQuestionEnricher(client, model_id)
        enriched_schema = enricher.enrich_schema(schema)
        
        # Save enriched schema)
        output_file = "ecr_schema_with_questions.json"
        logger.info(f"Saving enriched schema to {output_file}")
        with open(output_file, 'w') as f:
            json.dump(enriched_schema, f, indent=2)
            
        logger.info("Schema enrichment completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()