#!/usr/bin/env python3
"""Migrate state data from state.json to DynamoDB."""

import json
import logging
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from dateutil import tz

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_state():
    """Migrate state data from JSON file to DynamoDB."""
    try:
        # Read the state.json file
        with open('state.json', 'r') as f:
            state_data = json.load(f)
        
        # Initialize DynamoDB
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('rss-to-raindrop-feed-state')
        
        # Get the feeds data
        feeds = state_data.get('feeds', {})
        
        # Migrate each feed's state
        for feed_url, feed_state in feeds.items():
            try:
                logger.info(f"Migrating state for feed: {feed_url}")
                
                # Create DynamoDB item
                item = {
                    'feed_url': feed_url,
                    'processed_count': feed_state.get('processed_count', 0)
                }
                
                # Handle last_pub_date
                last_pub_date = feed_state.get('last_pub_date')
                if last_pub_date:
                    item['last_pub_date'] = last_pub_date
                
                # Handle last_processed
                last_processed = feed_state.get('last_processed')
                if last_processed:
                    item['last_processed'] = last_processed
                
                # Put item in DynamoDB
                table.put_item(Item=item)
                logger.info(f"Successfully migrated state for feed: {feed_url}")
                
            except ClientError as e:
                logger.error(f"Error migrating feed {feed_url}: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error migrating feed {feed_url}: {str(e)}")
                continue
        
        logger.info("Migration completed successfully")
        
    except FileNotFoundError:
        logger.error("state.json file not found")
    except json.JSONDecodeError:
        logger.error("Error parsing state.json file")
    except ClientError as e:
        logger.error(f"AWS error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

if __name__ == '__main__':
    migrate_state()
