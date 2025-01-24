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
    
    def add_bookmarks(
        self,
        articles: List[Dict[str, Any]],
        collection_id: int,
        reasons: Optional[List[str]] = None
    ) -> int:
        """
        Add multiple articles as bookmarks in a single request.
        
        Args:
            articles: List of articles to add
            collection_id: Raindrop collection ID
            reasons: Optional list of reasons from LLM analysis
            
        Returns:
            Number of bookmarks successfully added
        """
        if not articles:
            return 0
            
        # Prepare items for batch request
        items = []
        for i, article in enumerate(articles):
            # Extract article data
            link = article.get('link')
            if not link:
                logger.warning("Article missing required link field")
                continue
                
            title = article.get('title', '')
            pub_date = get_article_date(article)
            reason = reasons[i] if reasons else None
            
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
            items.append(item)
        
        if not items:
            return 0
            
        try:
            # Make batch API request
            logger.debug(f"Adding {len(items)} bookmarks to collection {collection_id}")
            response = self.session.post(
                f"{self.API_BASE}/raindrops",
                json={"items": items}
            )
            response.raise_for_status()
            
            result = response.json()
            added_count = len(result.get('items', []))
            logger.info(f"Successfully added {added_count} bookmarks")
            return added_count
            
        except Exception as e:
            logger.error(f"Error adding bookmarks: {str(e)}")
            logger.error("API Response:", exc_info=True)
            raise
    
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
        self.add_bookmarks([article], collection_id, [reason] if reason else None)
    
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
