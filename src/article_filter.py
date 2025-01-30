"""Article filtering logic for RSS Feed Bouncer."""

import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, Optional, Union, List
from openai import OpenAI
from .utils import get_article_date
import tiktoken

logger = logging.getLogger(__name__)

class ArticleFilter:
    """Filter for determining which articles to save and categorize."""
    
    def __init__(
        self,
        max_age_years: float = 1.0,
        personas: Optional[List[Dict[str, Any]]] = None,
        priority_topics: Optional[List[str]] = None,
        skip_criteria: Optional[List[str]] = None,
        collection_rules: Optional[Dict[str, List[str]]] = None,
        openai_config: Optional[Dict[str, str]] = None
    ):
        """
        Initialize article filter.
        
        Args:
            max_age_years: Maximum age of articles to keep (in years)
            personas: List of personas with their interests
            priority_topics: List of high-priority topics
            skip_criteria: Criteria for skipping articles
            collection_rules: Rules for categorizing articles into collections
            openai_config: OpenAI API configuration
        """
        self.max_age = timedelta(days=max_age_years * 365)
        self.personas = personas if personas is not None else []
        self.priority_topics = priority_topics if priority_topics is not None else []
        self.skip_criteria = skip_criteria if skip_criteria is not None else []
        self.collection_rules = collection_rules if collection_rules is not None else {}
        
        # Configure OpenAI if credentials provided
        if openai_config and openai_config.get('api_key'):
            self.client = OpenAI(api_key=openai_config['api_key'])
            self.openai_model = openai_config.get('model', 'gpt-4')
            logger.info(f"Using OpenAI model: {self.openai_model}")
        else:
            self.client = None
            self.openai_model = None
            logger.warning("No OpenAI API key provided, skipping content analysis")
        
        self.encoding = tiktoken.encoding_for_model(self.openai_model)
        # Reserve tokens for system message and completion
        self.max_tokens = 128000 - 4000  # Reserve 4k tokens for system and response
        
    def analyze_article(self, article: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """
        Analyze article and determine which collection it belongs in.
        
        Args:
            article: Article to analyze
            
        Returns:
            Tuple of (collection_name, reason)
        """
        logger.debug(f"Analyzing article: {article.get('title', 'No title')}")
        
        # Check if article has required fields
        if not article.get('link'):
            return "maybe", "Missing required link field"
        
        # Get article date
        pub_date = get_article_date(article)
        if not pub_date:
            return "maybe", "Could not determine publication date"
        
        # Check if article is too old
        if self._is_too_old(pub_date):
            return "skip", f"Article is older than {self.max_age.days} days"
        
        # Check content criteria if OpenAI is configured
        if self.client and self.openai_model:
            logger.info(f"Analyzing content for: {article.get('title', 'No title')}")
            collection, reason = self._analyze_content(article)
            logger.info(f"LLM suggests {collection}: {reason}")
            return collection, reason
        
        # Default to maybe if no content analysis is possible
        return "maybe", "No content analysis available"
        
    def _is_too_old(self, pub_date: datetime) -> bool:
        """
        Check if article is older than max_age.
        
        Args:
            pub_date: Publication date of article
            
        Returns:
            True if article is too old
        """
        now = datetime.now(timezone.utc)
        return now - pub_date > self.max_age
    
    def _analyze_content(self, article: Dict[str, Any]) -> Tuple[str, str]:
        """
        Analyze article content and determine appropriate collection.
        
        Args:
            article: Article to analyze
            
        Returns:
            Tuple of (collection_name, reason)
        """
        # Extract content for analysis
        content = self._get_article_content(article)
        if not content:
            return "maybe", "No content available for analysis"
            
        # Build prompt
        prompt = self._build_analysis_prompt(content)
        logger.debug(f"LLM Prompt:\n{prompt}")
        
        try:
            # Get response from OpenAI
            response = self.client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": "You are a content analyst helping categorize articles based on user interests and personas. Your task is to analyze articles and categorize them into collections based on their relevance and value."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent responses
                response_format={"type": "json_object"}
            )
            
            # Parse response
            try:
                raw_response = response.choices[0].message.content
                # Log exact raw response with visible whitespace
                logger.debug(f"Raw response length: {len(raw_response)}")
                logger.debug(f"Raw response repr: {repr(raw_response)}")
                logger.debug(f"Raw response bytes: {raw_response.encode()}")
                
                # Strip and clean the response
                cleaned_response = raw_response.strip()
                logger.debug(f"Cleaned response repr: {repr(cleaned_response)}")
                
                # Try to parse the JSON
                try:
                    result = json.loads(cleaned_response)
                    logger.debug(f"Parsed JSON response: {result}")
                except json.JSONDecodeError as je:
                    # Try to clean up common JSON formatting issues
                    if cleaned_response.startswith('\n'):
                        cleaned_response = cleaned_response.lstrip()
                    if cleaned_response.endswith('\n'):
                        cleaned_response = cleaned_response.rstrip()
                    # Try one more time with cleaned response
                    result = json.loads(cleaned_response)
                    logger.debug("JSON parsed successfully after cleaning")
                
                # Validate response format
                if not isinstance(result, dict):
                    logger.error(f"Response is not a dictionary: {type(result)}")
                    return "maybe", "Invalid response format from analysis"
                    
                collection = result.get("collection")
                reason = result.get("reason")
                
                logger.debug(f"Extracted collection: {collection}, reason: {reason}")
                
                if not collection:
                    logger.error("Missing 'collection' field in response")
                    return "maybe", "Missing collection in analysis response"
                    
                if not reason:
                    logger.error("Missing 'reason' field in response")
                    return "maybe", "Missing reason in analysis response"
                    
                if collection not in ["read", "maybe", "skip"]:
                    logger.error(f"Invalid collection value: {collection}")
                    return "maybe", f"Invalid collection value: {collection}"
                
                return collection, reason
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.error(f"Raw response causing error: {repr(raw_response)}")
                logger.error(f"Error position: {e.pos}, line: {e.lineno}, column: {e.colno}")
                return "maybe", f"Error parsing analysis response: {str(e)}"
                
        except Exception as e:
            logger.error(f"Error during OpenAI API call: {str(e)}")
            logger.error("OpenAI Error:", exc_info=True)
            return "maybe", f"Error during analysis: {str(e)}"
    
    def _build_analysis_prompt(self, content: str) -> str:
        """
        Build prompt for content analysis.
        
        Args:
            content: Content to analyze
            
        Returns:
            Analysis prompt
        """
        # Format personas and their interests
        personas_text = ""
        for persona in self.personas:
            interests = "\n      - ".join(persona["interests"])
            personas_text += f"""
    {persona["name"]}:
      - {interests}"""

        # Format priority topics
        priority_topics = "\n- ".join(self.priority_topics)
        
        # Format skip criteria
        skip_criteria = "\n- ".join(self.skip_criteria)
        
        # Format collection rules
        collection_rules = ""
        for collection, rules in self.collection_rules.items():
            rules_text = "\n      - ".join(rules)
            collection_rules += f"""
    {collection}:
      - {rules_text}"""
        
        prompt_template = f"""Analyze this article content and determine the most appropriate collection based on the following criteria:

1. User Personas and Interests:{personas_text}

2. Priority Topics:
- {priority_topics}

3. Skip Criteria:
- {skip_criteria}

4. Collection Rules:{collection_rules}

Important notes:
1. Articles matching skip criteria should always go to "skip" collection
2. When in doubt between read and maybe, prefer "maybe" to avoid noise in the read collection
3. Consider both technical depth and practical applicability

Article content:
{{}}

You must respond with a valid JSON object in this exact format:
{{{{
    "collection": "COLLECTION",
    "reason": "REASON"
}}}}

Where:
- COLLECTION must be exactly one of these values: "read", "maybe", or "skip" (including the quotes)
- REASON should be a brief explanation of why this collection was chosen

Do not include any other text in your response, only the JSON object.

Example response:
{{{{
    "collection": "read",
    "reason": "Directly addresses cloud security automation with novel insights and practical implementation details"
}}}}

Response:"""
        
        template_tokens = len(self.encoding.encode(prompt_template.format("")))
        
        # Calculate remaining tokens for article
        article_max_tokens = self.max_tokens - template_tokens
        
        # Truncate article text if needed
        truncated_content = self._truncate_to_token_limit(content, article_max_tokens)
        
        return prompt_template.format(truncated_content)
    
    def _get_article_content(self, article: Dict[str, Any]) -> str:
        """
        Extract content from article.
        
        Args:
            article: Article data
            
        Returns:
            Article content
        """
        content = f"Title: {article.get('title', '')}\n"
        content += f"Description: {article.get('summary', '')}\n"
        return content
    
    def _truncate_to_token_limit(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to stay within token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum number of tokens allowed
            
        Returns:
            Truncated text
        """
        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
            
        logger.warning(f"Text exceeds token limit ({len(tokens)} tokens). Truncating to {max_tokens} tokens.")
        truncated_tokens = tokens[:max_tokens]
        return self.encoding.decode(truncated_tokens)
