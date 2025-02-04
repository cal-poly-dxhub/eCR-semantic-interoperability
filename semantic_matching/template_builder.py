import os
import json
from typing import Dict, List, Any, Set, Optional, Union
from collections import defaultdict
from datetime import datetime
import re
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SchemaField:
    """Helper class to represent a schema field."""
    def __init__(self, type_name: str, description: str, default: Any = None, enum: List[str] = None):
        self.type_name = type_name
        self.description = description
        self.default = default
        self.enum = enum

    def to_dict(self) -> Dict[str, Any]:
        schema = {
            "type": self.type_name,
            "description": self.description
        }
        if self.default is not None:
            schema["default"] = self.default
        if self.enum is not None:
            schema["enum"] = self.enum
        return schema

class ECRSchemaGenerator:
    def __init__(self):
        self.field_values: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.field_types: Dict[str, str] = {}
        self.array_fields: Set[str] = set()
        self.na_variants = {'n/a', 'N/A', 'NA', 'none', 'None', 'NONE'}
        
    def analyze_json_files(self, directory_path: str) -> None:
        """Analyze all JSON files in the given directory."""
        if not os.path.exists(directory_path):
            raise FileNotFoundError(f"Directory not found: {directory_path}")
            
        json_files = [f for f in os.listdir(directory_path) if f.endswith('.json')]
        logger.info(f"Found {len(json_files)} JSON files to analyze")
        
        for file_name in json_files:
            file_path = os.path.join(directory_path, file_name)
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                self._process_document(data)
            except Exception as e:
                logger.error(f"Error processing {file_name}: {str(e)}")
                
    def _process_document(self, data: Dict, parent_key: str = "") -> None:
        """Process a single document recursively."""
        for key, value in data.items():
            full_key = f"{parent_key}.{key}" if parent_key else key
            
            if isinstance(value, dict):
                self._process_document(value, full_key)
            elif isinstance(value, list):
                # Mark this as an array field
                array_key = full_key
                if "_Entry" in array_key:
                    array_key = array_key.replace("_Entry", "_Entries")
                self.array_fields.add(array_key)
                
                for item in value:
                    if isinstance(item, dict):
                        self._process_document(item, array_key)
                    else:
                        self.field_values[array_key][str(item)] += 1
            else:
                self.field_values[full_key][str(value)] += 1
                
    def _detect_field_type(self, values: Dict[str, int], field_name: str = "") -> str:
        """Detect the type of a field based on its values and name."""
        if not values:
            return "text"
            
        all_values = list(values.keys())
        sample_value = all_values[0]
        
        # Handle numeric fields
        try:
            float_values = [float(v) for v in all_values]
            return "numeric"
        except ValueError:
            pass
        
        # Check for date fields
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        if re.match(date_pattern, sample_value):
            return "date"
            
        # Check for boolean-like fields
        bool_values = set(v.lower() for v in all_values)
        if bool_values <= {'yes', 'no', 'n/a', 'true', 'false'} or bool_values <= self.na_variants:
            return "boolean"
            
        # Check for enumerated fields
        total_occurrences = sum(values.values())
        if len(values) <= 30 and total_occurrences > len(values) * 2:
            return "enum"
            
        # For fields with many unique values
        if len(values) > 50:
            return "free_text"
            
        return "text"
        
    def _get_default_value(self, values: Dict[str, int], field_type: str) -> Any:
        """Determine the default value for a field."""
        if not values:
            return ""
            
        # Check for N/A values first
        for na_value in self.na_variants:
            if na_value in values:
                return na_value
                
        # For boolean and enum fields, use most common value
        if field_type in ["boolean", "enum"]:
            return max(values.items(), key=lambda x: x[1])[0]
            
        # Type-specific defaults
        defaults = {
            "date": "1900-01-01",
            "numeric": "0",
            "text": "",
            "free_text": ""
        }
        return defaults.get(field_type, "")
        
    def _create_field_schema(self, field_type: str, values: Dict[str, int], 
                           default_value: str) -> SchemaField:
        """Create schema definition for a field."""
        if field_type == "numeric":
            return SchemaField("number", "Numeric value")
            
        schema_field = SchemaField("string", f"Field type: {field_type}", default_value)
        
        if field_type == "enum":
            schema_field.enum = list(values.keys())
        elif field_type == "date":
            schema_field.description = "Date in YYYY-MM-DD format"
        elif field_type == "free_text":
            schema_field.description = "Free-form text field"
            
        return schema_field

    def _get_or_create_object(self, current: Dict[str, Any], key: str, 
                            is_array: bool = False) -> Dict[str, Any]:
        """Get or create a nested object structure in the schema."""
        if is_array:
            if key not in current:
                current[key] = {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                }
            return current[key]["items"]["properties"]
        else:
            if key not in current:
                current[key] = {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            return current[key]["properties"]

    def generate_schema(self) -> Dict[str, Any]:
        """Generate the complete schema based on analyzed data."""
        schema = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
            "$schema": "http://json-schema.org/draft-07/schema#",
            "description": "ECR Document Schema"
        }
        
        # Process all fields
        for field, values in self.field_values.items():
            try:
                field_parts = field.split('.')
                current = schema["properties"]
                
                # Handle nested structure
                for part in field_parts[:-1]:
                    is_array = any(part in array_field for array_field in self.array_fields)
                    current = self._get_or_create_object(current, part, is_array)
                
                # Create the field schema
                field_type = self._detect_field_type(values, field)
                default_value = self._get_default_value(values, field_type)
                field_schema = self._create_field_schema(field_type, values, default_value)
                
                # Add the field to the schema
                current[field_parts[-1]] = field_schema.to_dict()
                
            except Exception as e:
                logger.error(f"Error processing field {field}: {str(e)}")
                continue
        
        return schema
        
    def save_schema(self, schema: Dict[str, Any], output_file: str) -> None:
        """Save the generated schema to a file."""
        with open(output_file, 'w') as f:
            json.dump(schema, f, indent=2)
        logger.info(f"Schema saved to {output_file}")
        
    def print_field_analysis(self) -> None:
        """Print analysis of all fields."""
        logger.info("\nField Analysis:")
        logger.info("-" * 50)
        
        for field in self.field_values.keys():
            values = self.field_values[field]
            field_type = self._detect_field_type(values, field)
            default_value = self._get_default_value(values, field_type)
            unique_values = len(values)
            
            print(f"\nField: {field}")
            print(f"Type: {field_type}")
            print(f"Default: {default_value}")
            print(f"Unique values: {unique_values}")
            
            if field_type == "enum" or unique_values <= 10:
                print("All values:")
                for value, count in sorted(values.items(), key=lambda x: x[1], reverse=True):
                    print(f"  - {value}: {count} occurrences")
            else:
                print("Sample values (top 5):")
                for value, count in sorted(values.items(), 
                                        key=lambda x: x[1], reverse=True)[:5]:
                    print(f"  - {value}: {count} occurrences")

def main():
    # Initialize the schema generator
    generator = ECRSchemaGenerator()
    
    try:
        # Get the path to JSON files
        json_path = "/Users/swayamchidrawar/repos/eCR-semantic-interoperability/semantic_matching/makedata/human_readable"
        
        # Analyze the files
        logger.info("Starting analysis of JSON files...")
        generator.analyze_json_files(json_path)
        
        # Print analysis
        logger.info("\nGenerating field analysis...")
        generator.print_field_analysis()
        
        # Generate and save schema
        logger.info("\nGenerating schema...")
        schema = generator.generate_schema()
        
        # Save the schema
        output_file = "ecr_schema.json"
        generator.save_schema(schema, output_file)
        
        logger.info("\nProcess completed successfully!")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()