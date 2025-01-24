"""Main RSS analysis logic for RSS Feed Bouncer."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Iterator, Callable
import feedparser
import requests
from .article_filter import ArticleFilter
from .raindrop_client import RaindropClient
from .state import StateManager
from .utils import get_article_date, ensure_timezone

logger = logging.getLogger(__name__)

class RSSAnalyzer:
    """Main class for processing RSS feeds and filtering articles."""
    
    def __init__(
        self,
        config: Dict[str, Any],
        state_manager: StateManager
    ):
        """
        Initialize RSS analyzer.
        
        Args:
            config: Configuration dictionary
            state_manager: State manager instance
        """
        self.config = config
        self.state_manager = state_manager
        
        # Initialize components
        self.raindrop_client = RaindropClient(
            token=config['raindrop']['token']
        )
        
        self.article_filter = ArticleFilter(
            max_age_years=config['filters'].get('max_article_age_years', 5),
            skip_criteria=config['filters'].get('skip_criteria', []),
            openai_config={
                'api_key': config['openai'].get('api_key'),
                'model': config['openai'].get('model')
            }
        )
        
        self.batch_size = config['processing'].get('batch_size', 5)
        self.read_collection = int(config['raindrop']['collections']['read'])
        self.skip_collection = int(config['raindrop']['collections']['skip'])
    
    def _fetch_feed_content(self, feed_url: str) -> Optional[str]:
        """
        Fetch feed content with proper encoding handling.
        
        Args:
            feed_url: URL of the feed to fetch
            
        Returns:
            Feed content as string or None if failed
        """
        try:
            response = requests.get(feed_url, timeout=30)
            response.raise_for_status()
            
            # Try to detect the encoding from the response headers
            content_type = response.headers.get('content-type', '')
            if 'charset=' in content_type:
                encoding = content_type.split('charset=')[-1].strip()
                try:
                    return response.content.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    logger.warning(f"Failed to decode content with declared charset {encoding}")
            
            # If no charset in headers or decoding failed, try common encodings
            encodings = ['utf-8', 'utf-16', 'iso-8859-1', 'us-ascii', 'windows-1252']
            content = response.content
            
            for encoding in encodings:
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            
            # If all else fails, use utf-8 with error handling
            return content.decode('utf-8', errors='replace')
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch feed {feed_url}: {str(e)}")
            print(f"Error fetching feed: {str(e)}")
            return None
    
    def process_feeds(self, should_shutdown: Optional[Callable[[], bool]] = None) -> None:
        """
        Process all configured RSS feeds.
        
        Args:
            should_shutdown: Optional callback to check if shutdown is requested
        """
        total_feeds = len(self.config['feeds'])
        for feed_num, feed_url in enumerate(self.config['feeds'], 1):
            try:
                print(f"\nProcessing feed {feed_num}/{total_feeds}: {feed_url}")
                logger.info(f"Starting to process feed: {feed_url}")
                
                # Check for shutdown request before starting each feed
                if should_shutdown and should_shutdown():
                    remaining = total_feeds - feed_num
                    print(f"\nSkipping remaining {remaining} feed(s) due to shutdown request.")
                    logger.info(f"Shutdown requested. Skipping {remaining} remaining feeds.")
                    break
                
                self._process_single_feed(feed_url, should_shutdown)
            except Exception as e:
                logger.error(f"Error processing feed {feed_url}: {str(e)}", exc_info=True)
                print(f"Error processing feed: {str(e)}")
    
    def _process_single_feed(
        self,
        feed_url: str,
        should_shutdown: Callable[[], bool]
    ) -> None:
        """
        Process a single RSS feed.
        
        Args:
            feed_url: URL of the feed to process
            should_shutdown: Function that returns True if we should shutdown
        """
        try:
            # Get feed content
            content = self._fetch_feed_content(feed_url)
            if not content:
                return
                
            # Parse feed
            feed = feedparser.parse(content)
            if not feed.entries:
                logger.info(f"No entries found in feed: {feed_url}")
                return
                
            feed_title = feed.get('feed', {}).get('title', feed_url)
            total_entries = len(feed.entries)
            logger.info(f"Successfully fetched feed: {feed_title}")
            logger.info(f"Found {total_entries} total entries in feed")
            print(f"Found {total_entries} entries in feed: {feed_title}")
            
            # Get last processed date for this feed
            last_pub_date = self.state_manager.get_last_pub_date(feed_url)
            
            # Get new articles
            new_articles = self._get_new_articles(feed.entries, last_pub_date)
            if not new_articles:
                logger.info(f"No new articles found in feed: {feed_url}")
                return
            
            # Process articles in batches
            total_processed = 0
            latest_date = None
            
            for batch_num, batch in enumerate(
                self._batch_articles(new_articles), 1
            ):
                if should_shutdown():
                    logger.info("Shutdown requested, stopping feed processing")
                    break
                
                # Process the batch
                batch_count = self._process_article_batch(batch)
                total_processed += batch_count
                
                # Update the latest processed date
                if batch_count > 0:
                    # Get the latest date from successfully processed articles
                    batch_dates = [a['normalized_date'] for a in batch]
                    max_date = max(batch_dates)
                    latest_date = max(max_date, latest_date) if latest_date else max_date
                
                logger.info(
                    f"Successfully processed {batch_count}/{len(batch)} "
                    f"articles in batch {batch_num}"
                )
            
            # Update state if we processed any articles
            if total_processed > 0 and latest_date:
                self.state_manager.update_feed_state(
                    feed_url=feed_url,
                    last_pub_date=latest_date,
                    processed_count=total_processed
                )
        
        except Exception as e:
            logger.error(f"Error processing feed {feed_url}: {str(e)}")
            logger.error("Error processing feed:", exc_info=True)
            raise
    
    def _get_new_articles(
        self,
        entries: List[Dict[str, Any]],
        last_pub_date: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """
        Get new articles from feed entries.
        
        Args:
            entries: List of feed entries
            last_pub_date: Last processed publication date
            
        Returns:
            List of new articles to process
        """
        # Ensure last_pub_date is timezone-aware
        last_pub_date = ensure_timezone(last_pub_date)
        logger.debug(f"Last publication date: {last_pub_date.isoformat() if last_pub_date else 'None'}")
        
        # Add normalized dates to entries
        for entry in entries:
            entry['normalized_date'] = get_article_date(entry)
            if entry['normalized_date']:
                logger.debug(
                    f"Article '{entry.get('title', 'No title')}' date: "
                    f"{entry['normalized_date'].isoformat()}"
                )
            else:
                logger.warning(
                    f"No date found for article: {entry.get('title', 'No title')}"
                )
        
        # Filter out entries without dates
        dated_entries = []
        for entry in entries:
            if not entry['normalized_date']:
                continue
                
            if not last_pub_date or entry['normalized_date'] > last_pub_date:
                logger.debug(
                    f"Including article '{entry.get('title', 'No title')}' "
                    f"with date {entry['normalized_date'].isoformat()}"
                )
                dated_entries.append(entry)
            else:
                logger.debug(
                    f"Skipping old article '{entry.get('title', 'No title')}' "
                    f"with date {entry['normalized_date'].isoformat()}"
                )
        
        # Sort by date, newest first
        dated_entries.sort(
            key=lambda x: x['normalized_date'],
            reverse=True
        )
        
        logger.info(f"Found {len(dated_entries)} new articles to process")
        return dated_entries
    
    def _batch_articles(
        self,
        articles: List[Dict[str, Any]],
        batch_size: Optional[int] = None
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Split articles into batches.
        
        Args:
            articles: List of articles to batch
            batch_size: Size of each batch, defaults to self.batch_size
            
        Returns:
            Iterator of article batches
        """
        if batch_size is None:
            batch_size = self.batch_size
            
        for i in range(0, len(articles), batch_size):
            yield articles[i:i + batch_size]
    
    def _process_article_batch(self, articles: List[Dict[str, Any]]) -> int:
        """
        Process a batch of articles.
        
        Args:
            articles: List of articles to process
            
        Returns:
            Number of articles successfully processed
        """
        if not articles:
            return 0
            
        # Analyze all articles in batch
        read_articles = []
        read_reasons = []
        skip_articles = []
        skip_reasons = []
        
        for article in articles:
            try:
                # Check if we should skip this article
                should_skip, reason = self.article_filter.should_skip(article)
                
                if should_skip:
                    logger.info(
                        f"Adding article to skip collection: {article.get('title', 'No title')} - "
                        f"Reason: {reason}"
                    )
                    skip_articles.append(article)
                    skip_reasons.append(reason)
                else:
                    logger.info(
                        f"Adding article to read collection: {article.get('title', 'No title')} - "
                        f"Reason: {reason}"
                    )
                    read_articles.append(article)
                    read_reasons.append(reason)
                    
            except Exception as e:
                logger.error(
                    f"Error analyzing article {article.get('title', 'No title')}: "
                    f"{str(e)}"
                )
                continue
        
        processed_count = 0
        
        # Add read articles in batch
        if read_articles:
            try:
                logger.info(f"Saving batch of {len(read_articles)} articles to read collection")
                count = self.raindrop_client.add_bookmarks(
                    read_articles,
                    self.read_collection,
                    read_reasons
                )
                processed_count += count
            except Exception as e:
                logger.error(f"Error adding read articles: {str(e)}")
        
        # Add skip articles in batch if configured
        if skip_articles and self.config['raindrop'].get('save_skipped', True):
            try:
                logger.info(f"Saving batch of {len(skip_articles)} articles to skip collection")
                count = self.raindrop_client.add_bookmarks(
                    skip_articles,
                    self.skip_collection,
                    skip_reasons
                )
                processed_count += count
            except Exception as e:
                logger.error(f"Error adding skip articles: {str(e)}")
        elif skip_articles:
            logger.info(f"Skipping {len(skip_articles)} articles (not saving)")
            for article in skip_articles:
                logger.info(
                    f"Skipping article (not saving): {article.get('title', 'No title')}"
                )
        
        return processed_count
