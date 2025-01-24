"""Utility functions for RSS Feed Bouncer."""

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Any, Optional
import time

logger = logging.getLogger(__name__)

def ensure_timezone(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure datetime has timezone info, using UTC if none provided.
    
    Args:
        dt: Datetime to check
        
    Returns:
        Timezone-aware datetime or None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse a date string in various formats.
    
    Args:
        date_str: Date string to parse
        
    Returns:
        Parsed datetime or None if parsing failed
    """
    try:
        # Try email date format first (RFC 2822)
        return ensure_timezone(parsedate_to_datetime(date_str))
    except (TypeError, ValueError):
        try:
            # Try ISO format (e.g., "2024-09-23T00:00:00Z")
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return ensure_timezone(dt)
        except ValueError:
            logger.debug(f"Failed to parse date: {date_str}")
            return None

def get_article_date(article: Dict[str, Any]) -> Optional[datetime]:
    """
    Get article publication date from various possible fields.
    
    Args:
        article: Article data dictionary
        
    Returns:
        Article publication date or None if not found
    """
    logger.debug(f"Attempting to get date for article: {article.get('title', 'No title')}")
    logger.debug(f"Available fields: {list(article.keys())}")
    
    # First try feedparser's normalized published_parsed
    if article.get('published_parsed'):
        try:
            dt = datetime(*article['published_parsed'][:6])
            logger.debug(f"Found published_parsed date: {dt}")
            return ensure_timezone(dt)
        except Exception as e:
            logger.debug(f"Error parsing published_parsed: {str(e)}")
    
    # Order of fields to check, with their parsing functions
    field_parsers = [
        ('published', parse_date),
        ('pubDate', parse_date),
        ('created', parse_date),
        ('createDate', parse_date),
        ('updated', parse_date),
        # Add more field mappings as needed
    ]
    
    for field, parser in field_parsers:
        value = article.get(field)
        if value:
            logger.debug(f"Trying field '{field}' with value: {value}")
            try:
                date = parser(value)
                if date:
                    logger.debug(f"Successfully parsed date from {field}: {date.isoformat()}")
                    return date
            except Exception as e:
                logger.debug(f"Error parsing date from {field}: {str(e)}")
                continue
    
    logger.warning(f"No valid date found in article: {article.get('title', 'No title')}")
    return None

def datetime_to_struct_time(dt: datetime) -> time.struct_time:
    """
    Convert datetime object to time.struct_time.
    
    Args:
        dt: datetime object
        
    Returns:
        time.struct_time object
    """
    return dt.timetuple()
