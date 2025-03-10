#!/usr/bin/env python3
"""RSS Feed Bouncer - Filter and save interesting articles to Raindrop."""

import logging
import os
import signal
import sys
import threading
import yaml
from src.rss_analyzer import RSSAnalyzer
from src.state import StateManager
from src.secrets_manager import get_secret

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for shutdown
should_shutdown = threading.Event()

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info("\nShutdown requested...")
    should_shutdown.set()

def load_config(config_path: str) -> dict:
    """Load configuration from YAML file and AWS Secrets Manager."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        # Get secrets from AWS Secrets Manager if running in Lambda
        if 'RAINDROP_SECRET_ARN' in os.environ and 'OPENAI_SECRET_ARN' in os.environ:
            config['raindrop']['token'] = get_secret(os.environ['RAINDROP_SECRET_ARN'])
            config['openai']['api_key'] = get_secret(os.environ['OPENAI_SECRET_ARN'])
            
        return config
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        raise

def lambda_handler(event, context):
    """AWS Lambda handler function."""
    try:
        # Load configuration
        config_path = os.environ.get('CONFIG_PATH', 'config.yaml')
        config = load_config(config_path)
        
        # Initialize State Manager
        state_manager = StateManager()
        
        # Initialize analyzer
        analyzer = RSSAnalyzer(config, state_manager)
        
        # Process feeds once
        analyzer.process_feeds()
        
        return {
            'statusCode': 200,
            'body': 'Successfully processed RSS feeds'
        }
    except Exception as e:
        logger.error(f"Error in Lambda execution: {str(e)}")
        return {
            'statusCode': 500,
            'body': f"Error processing RSS feeds: {str(e)}"
        }

if __name__ == "__main__":
    lambda_handler({}, {})