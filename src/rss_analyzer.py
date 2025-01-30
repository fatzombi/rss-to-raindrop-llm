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

# Configure feedparser
feedparser.USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

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
            personas=config['filters'].get('personas', []),
            priority_topics=config['filters'].get('priority_topics', []),
            skip_criteria=config['filters'].get('skip_criteria', []),
            collection_rules=config['filters'].get('collection_rules', {}),
            openai_config={
                'api_key': config['openai'].get('api_key'),
                'model': config['openai'].get('model')
            }
        )
        
        self.batch_size = config['processing'].get('batch_size', 5)
        self.collections = {
            name: int(id) for name, id in config['raindrop']['collections'].items()
        }
    
    def _fetch_feed_content(self, feed_url: str) -> Optional[str]:
        """
        Fetch feed content with proper encoding handling.
        
        Args:
            feed_url: URL of the feed to fetch
            
        Returns:
            Feed content as string or None if failed
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, application/atom+xml, application/json, text/xml;q=0.9, */*;q=0.8'
            }
            
            response = requests.get(feed_url, headers=headers, timeout=30)
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
            
        # Initialize article lists for each collection
        collection_articles = {
            collection: [] for collection in self.collections.keys()
        }
        collection_reasons = {
            collection: [] for collection in self.collections.keys()
        }
        
        for article in articles:
            try:
                # Log article details before processing
                logger.debug(f"Processing article: {article.get('title', 'No title')}")
                logger.debug(f"Article URL: {article.get('link', 'No link')}")
                logger.debug(f"Article content length: {len(str(article.get('content', '')))}")
                
                # Analyze article to determine collection
                try:
                    collection, reason = self.article_filter.analyze_article(article)
                    logger.debug(f"Analysis result - Collection: {collection}, Reason: {reason}")
                except Exception as analysis_error:
                    logger.error(f"Error during article analysis: {str(analysis_error)}", exc_info=True)
                    logger.error(f"Article that caused error: {article}")
                    raise
                
                if not collection or not isinstance(collection, str):
                    logger.error(f"Invalid collection type returned: {type(collection)}")
                    logger.error(f"Collection value: {collection}")
                    continue
                
                if collection not in self.collections:
                    logger.error(f"Unknown collection returned: {collection}")
                    logger.error(f"Valid collections are: {list(self.collections.keys())}")
                    continue
                
                logger.info(
                    f"Adding article to {collection} collection: {article.get('title', 'No title')} - "
                    f"Reason: {reason}"
                )
                collection_articles[collection].append(article)
                collection_reasons[collection].append(reason)
                
            except Exception as e:
                logger.error(f"Error processing article: {str(e)}")
                logger.error("Full error details:", exc_info=True)
                logger.error(f"Article that caused error: {article}")
                continue
        
        # Save articles to their respective collections
        processed_count = 0
        for collection, articles in collection_articles.items():
            if not articles:
                continue
                
            try:
                collection_id = self.collections[collection]
                reasons = collection_reasons[collection]
                
                # Only save to skip collection if configured
                if collection == 'skip' and not self.config['raindrop'].get('save_skipped', True):
                    logger.info(f"Skipping {len(articles)} articles (save_skipped=False)")
                    continue
                
                self.raindrop_client.add_bookmarks(
                    articles,
                    collection_id,
                    reasons
                )
                processed_count += len(articles)
                
            except Exception as e:
                logger.error(f"Error saving articles to {collection} collection: {str(e)}")
        
        return processed_count
