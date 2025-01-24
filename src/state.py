"""State management for RSS Feed Bouncer."""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dateutil import tz

logger = logging.getLogger(__name__)

class StateManager:
    """Manages application state between runs."""
    
    def __init__(self, state_file: str = "state.json"):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to state file
        """
        self.state_file = state_file
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """
        Load state from file or create new state.
        
        Returns:
            Dict containing state data
        """
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return self._create_initial_state()
        return self._create_initial_state()
    
    def _create_initial_state(self) -> Dict[str, Any]:
        """
        Create initial state structure.
        
        Returns:
            Dict containing initial state
        """
        return {
            "feeds": {},
            "version": 1  # Add version for future schema migrations
        }
    
    def save_state(self) -> None:
        """Save current state to file."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def get_feed_state(self, feed_url: str) -> Dict[str, Any]:
        """
        Get complete state for a feed.
        
        Args:
            feed_url: URL of the feed
            
        Returns:
            Dict containing feed state or empty dict if not found
        """
        return self.state["feeds"].get(feed_url, {})
    
    def get_feed_last_run(self, feed_url: str) -> Optional[datetime]:
        """
        Get last run time for a feed.
        
        Args:
            feed_url: URL of the feed
            
        Returns:
            datetime of last run or None if feed hasn't been run
        """
        feed_state = self.get_feed_state(feed_url)
        last_run = feed_state.get("last_run")
        return datetime.fromisoformat(last_run) if last_run else None
    
    def get_feed_last_publish_date(self, feed_url: str) -> Optional[datetime]:
        """
        Get last processed article publish date for a feed.
        
        Args:
            feed_url: URL of the feed
            
        Returns:
            datetime of last processed article or None if no articles processed
        """
        feed_state = self.get_feed_state(feed_url)
        last_pub = feed_state.get("last_publish_date")
        return datetime.fromisoformat(last_pub) if last_pub else None
    
    def get_last_pub_date(self, feed_url: str) -> Optional[datetime]:
        """
        Get the last publication date for a feed.
        
        Args:
            feed_url: URL of the feed
            
        Returns:
            Last publication date or None if not found
        """
        feed_state = self.state.get('feeds', {}).get(feed_url, {})
        last_pub = feed_state.get('last_pub_date')
        
        if not last_pub:
            logger.debug(f"No last publication date found for feed: {feed_url}")
            return None
            
        try:
            date = datetime.fromisoformat(last_pub)
            logger.debug(f"Found last publication date for {feed_url}: {date.isoformat()}")
            return date
        except Exception as e:
            logger.error(f"Error parsing last publication date for {feed_url}: {str(e)}")
            return None
    
    def update_feed_state(
        self,
        feed_url: str,
        last_pub_date: datetime,
        processed_count: int
    ) -> None:
        """
        Update the state for a feed.
        
        Args:
            feed_url: URL of the feed
            last_pub_date: Last publication date processed
            processed_count: Number of articles processed
        """
        logger.debug(
            f"Updating state for feed {feed_url}\n"
            f"Last pub date: {last_pub_date.isoformat()}\n"
            f"Processed count: {processed_count}"
        )
        
        # Ensure the date is timezone-aware
        if last_pub_date.tzinfo is None:
            last_pub_date = last_pub_date.replace(tzinfo=tz.tzutc())
            logger.debug(f"Added UTC timezone to last_pub_date: {last_pub_date.isoformat()}")
        
        if 'feeds' not in self.state:
            self.state['feeds'] = {}
            
        self.state['feeds'][feed_url] = {
            'last_pub_date': last_pub_date.isoformat(),
            'last_processed': datetime.now(tz.tzutc()).isoformat(),
            'processed_count': processed_count
        }
        
        logger.debug(f"New state for feed {feed_url}: {self.state['feeds'][feed_url]}")
        self.save_state()
