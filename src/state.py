"""State management for RSS Feed Bouncer."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dateutil import tz
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class StateManager:
    """Manages application state between runs using DynamoDB."""
    
    def __init__(self, table_name: str = "rss-to-raindrop-feed-state"):
        """
        Initialize state manager with DynamoDB.
        
        Args:
            table_name: Name of the DynamoDB table
        """
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
    
    def get_feed_state(self, feed_url: str) -> Dict[str, Any]:
        """
        Get state for a feed.
        
        Args:
            feed_url: URL of the feed
            
        Returns:
            Dict containing feed state or empty dict if not found
        """
        try:
            response = self.table.get_item(
                Key={'feed_url': feed_url}
            )
            return response.get('Item', {})
        except ClientError as e:
            logger.error(f"Error getting feed state for {feed_url}: {str(e)}")
            return {}
    
    def get_feed_last_run(self, feed_url: str) -> Optional[datetime]:
        """
        Get last run time for a feed.
        
        Args:
            feed_url: URL of the feed
            
        Returns:
            datetime of last run or None if feed hasn't been run
        """
        feed_state = self.get_feed_state(feed_url)
        last_run = feed_state.get("last_processed")
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
        last_pub = feed_state.get("last_pub_date")
        return datetime.fromisoformat(last_pub) if last_pub else None
    
    def get_last_pub_date(self, feed_url: str) -> Optional[datetime]:
        """
        Get the last publication date for a feed.
        
        Args:
            feed_url: URL of the feed
            
        Returns:
            Last publication date or None if not found
        """
        feed_state = self.get_feed_state(feed_url)
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
            processed_count: Number of articles processed in this run
        """
        logger.debug(
            f"Updating state for feed {feed_url}\n"
            f"Last pub date: {last_pub_date.isoformat()}\n"
            f"Articles processed in this run: {processed_count}"
        )
        
        # Ensure the date is timezone-aware
        if last_pub_date.tzinfo is None:
            last_pub_date = last_pub_date.replace(tzinfo=tz.tzutc())
            logger.debug(f"Added UTC timezone to last_pub_date: {last_pub_date.isoformat()}")
        
        now = datetime.now(tz.tzutc())
        
        try:
            # Get current total processed count
            current_state = self.get_feed_state(feed_url)
            total_processed = current_state.get('processed_count', 0) + processed_count
            
            # Update state in DynamoDB
            self.table.update_item(
                Key={'feed_url': feed_url},
                UpdateExpression='SET last_pub_date = :lpd, last_processed = :lp, processed_count = :pc',
                ExpressionAttributeValues={
                    ':lpd': last_pub_date.isoformat(),
                    ':lp': now.isoformat(),
                    ':pc': total_processed
                }
            )
            
            logger.debug(
                f"Updated state for feed {feed_url}:\n"
                f"Total processed: {total_processed}\n"
                f"Last pub date: {last_pub_date.isoformat()}"
            )
        except ClientError as e:
            logger.error(f"Error updating feed state for {feed_url}: {str(e)}")
            raise

    def get_all_feeds(self) -> list:
        """
        Get all unique feed URLs from the DynamoDB table.
        
        Returns:
            List of unique feed URLs
        """
        feed_urls = []
        try:
            # Use scan operation to get all items
            # Note: For production with many feeds, consider using a secondary index or pagination
            response = self.table.scan(
                ProjectionExpression='feed_url'
            )
            
            # Extract feed URLs from response
            for item in response.get('Items', []):
                feed_urls.append(item.get('feed_url'))
                
            # Handle pagination if there are more items
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(
                    ProjectionExpression='feed_url',
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                for item in response.get('Items', []):
                    feed_urls.append(item.get('feed_url'))
            
            logger.info(f"Retrieved {len(feed_urls)} unique feed URLs from DynamoDB")
            return feed_urls
            
        except ClientError as e:
            logger.error(f"Error retrieving feeds from DynamoDB: {str(e)}")
            return []
