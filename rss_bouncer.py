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
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        raise

def main():
    """Main entry point."""
    try:
        # Load configuration
        config_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(config_dir, 'config.yaml')
        config = load_config(config_path)
        
        # Initialize state manager
        state_path = os.path.join(config_dir, 'state.json')
        state_manager = StateManager(state_path)
        
        # Initialize analyzer
        analyzer = RSSAnalyzer(config, state_manager)
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start processing
        logger.info("Starting RSS Feed Bouncer...")
        logger.info("Press Ctrl+C to gracefully shutdown")
        
        analyzer.process_feeds(lambda: should_shutdown.is_set())
        
    except Exception as e:
        logger.error(f"Application error: {str(e)}", exc_info=True)
        print(f"\nError: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
