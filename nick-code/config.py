# config.py
from dataclasses import dataclass
import yaml
import os
from typing import Optional

@dataclass
class Config:
    BEDROCK_REGION: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    EMBEDDING_MODEL: str = "amazon.titan-embed-text-v1"
    file_path = "your path here"

    @classmethod
    def from_yaml(cls, file_path: str) -> 'Config':
        """Load configuration from YAML file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Config file not found: {file_path}")
            
        try:
            with open(file_path, 'r') as f:
                config_data = yaml.safe_load(f)
                
            if config_data is None:
                raise ValueError(f"Config file is empty or invalid YAML: {file_path}")
                
            # Check for required fields
            required_fields = ['bedrock_region', 'aws_access_key_id', 'aws_secret_access_key']
            missing_fields = [field for field in required_fields if field not in config_data]
            
            if missing_fields:
                raise ValueError(f"Missing required fields in config: {', '.join(missing_fields)}")
                
            return cls(
                BEDROCK_REGION=config_data['bedrock_region'],
                AWS_ACCESS_KEY_ID=config_data['aws_access_key_id'],
                AWS_SECRET_ACCESS_KEY=config_data['aws_secret_access_key'],
                EMBEDDING_MODEL=config_data.get('embedding_model', cls.EMBEDDING_MODEL)
            )
            
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {str(e)}")