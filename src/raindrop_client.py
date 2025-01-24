"""Raindrop API client for RSS Feed Bouncer."""

import logging
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from .utils import get_article_date

logger = logging.getLogger(__name__)

class RaindropClient:
    """Client for interacting with Raindrop.io API."""
    
    API_BASE = "https://api.raindrop.io/rest/v1"
    
    def __init__(self, token: str):
        """
        Initialize Raindrop client.
        
        Args:
            token: Raindrop API token
        """
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        })
    
    def add_bookmark(
        self,
        article: Dict[str, Any],
        collection_id: int,
        reason: Optional[str] = None
    ) -> None:
        """
        Add a single article as a bookmark.
        
        Args:
            article: Article to add
            collection_id: Raindrop collection ID
            reason: Optional reason from LLM analysis
        """
        # Extract article data
        link = article.get('link')
        if not link:
            logger.warning("Article missing required link field")
            return
            
        title = article.get('title', '')
        pub_date = get_article_date(article)
        
        try:
            # Prepare bookmark data
            item = {
                "link": link,
                "title": title,
                "excerpt": reason if reason else article.get('summary', ''),
                "created": pub_date.isoformat() if pub_date else None,
                "collection": {"$id": collection_id}
            }
            
            # Remove None values
            item = {k: v for k, v in item.items() if v is not None}
            
            logger.debug(f"Adding bookmark: {item}")
            
            # Make API request with items array
            response = self.session.post(
                f"{self.API_BASE}/raindrops",
                json={"items": [item]}
            )
            response.raise_for_status()
            
            logger.info(f"Successfully added bookmark: {title}")
            
        except Exception as e:
            logger.error(f"Error adding bookmark {title}: {str(e)}")
            logger.error("API Response:", exc_info=True)
            raise
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an API request.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request data
            
        Returns:
            Response data
        """
        try:
            response = self.session.request(
                method,
                f"{self.API_BASE}{endpoint}",
                json=data
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            raise
