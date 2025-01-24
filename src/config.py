"""Configuration management for RSS Feed Bouncer."""

import os
import yaml
from typing import Dict, Any

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Dict containing configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuration file not found at {config_path}. "
            "Please copy config.example.yaml to config.yaml and update it."
        )
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    validate_config(config)
    
    # Set OpenAI API key from environment if not in config
    if not config.get('openai', {}).get('api_key'):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError(
                "OpenAI API key not found. Please either:\n"
                "1. Set it in config.yaml under openai.api_key, or\n"
                "2. Set the OPENAI_API_KEY environment variable"
            )
        if 'openai' not in config:
            config['openai'] = {}
        config['openai']['api_key'] = api_key
    
    return config

def validate_config(config: Dict[str, Any]) -> None:
    """
    Validate configuration structure and required fields.
    
    Args:
        config: Configuration dictionary
        
    Raises:
        ValueError: If configuration is invalid
    """
    required_keys = ['raindrop', 'filters', 'feeds']
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required configuration section: {key}")
    
    if not config['raindrop'].get('token'):
        raise ValueError("Raindrop API token is required")
    
    if not config['raindrop'].get('collections', {}).get('read'):
        raise ValueError("Raindrop read collection ID is required")
    
    if config['raindrop'].get('save_skipped', True) and \
       not config['raindrop'].get('collections', {}).get('skip'):
        raise ValueError("Raindrop skip collection ID is required when save_skipped is true")
    
    if not isinstance(config['feeds'], list) or not config['feeds']:
        raise ValueError("At least one feed URL must be configured")
    
    # Validate OpenAI configuration
    openai_config = config.get('openai', {})
    if not openai_config.get('model'):
        # Set default model if not specified
        if 'openai' not in config:
            config['openai'] = {}
        config['openai']['model'] = "gpt-4-turbo-preview"
