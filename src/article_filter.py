"""Article filtering logic for RSS Feed Bouncer."""

import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, Optional, Union
from openai import OpenAI
from .utils import get_article_date

logger = logging.getLogger(__name__)

class ArticleFilter:
    """Filter for determining which articles to save."""
    
    def __init__(
        self,
        max_age_years: float = 1.0,
        skip_criteria: Optional[Union[Dict[str, Any], list]] = None,
        openai_config: Optional[Dict[str, str]] = None
    ):
        """
        Initialize article filter.
        
        Args:
            max_age_years: Maximum age of articles to keep (in years)
            skip_criteria: Criteria for skipping articles (list or dict)
            openai_config: OpenAI API configuration
        """
        self.max_age = timedelta(days=max_age_years * 365)
        self.skip_criteria = skip_criteria if skip_criteria is not None else []
        
        # Configure OpenAI if credentials provided
        if openai_config and openai_config.get('api_key'):
            self.client = OpenAI(api_key=openai_config['api_key'])
            self.openai_model = openai_config.get('model', 'gpt-4')
            logger.info(f"Using OpenAI model: {self.openai_model}")
        else:
            self.client = None
            self.openai_model = None
            logger.warning("No OpenAI API key provided, skipping content analysis")
    
    def should_skip(self, article: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Check if an article should be skipped.
        
        Args:
            article: Article to check
            
        Returns:
            Tuple of (should_skip, reason)
        """
        logger.debug(f"Checking article: {article.get('title', 'No title')}")
        
        # Check if article has required fields
        if not article.get('link'):
            return True, "Missing required link field"
        
        # Get article date
        pub_date = get_article_date(article)
        if not pub_date:
            return True, "Could not determine publication date"
        
        # Check if article is too old
        if self._is_too_old(pub_date):
            return True, f"Article is older than {self.max_age.days} days"
        
        # Check content criteria if OpenAI is configured
        if self.client and self.openai_model and self.skip_criteria:
            logger.info(f"Analyzing content for: {article.get('title', 'No title')}")
            skip_content, reason = self._should_skip_article(article)
            if skip_content:
                logger.info(f"LLM suggests skipping: {reason}")
            else:
                logger.info(f"LLM suggests reading: {reason}")
            return skip_content, reason
        
        return False, None
        
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
    
    def _should_skip_article(self, article: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Determine if an article should be skipped.
        
        Args:
            article: Article to check
            
        Returns:
            Tuple of (should_skip, reason)
        """
        # Extract content for analysis
        content = self._get_article_content(article)
        if not content:
            return True, "No content available for analysis"
            
        # Build prompt
        prompt = self._build_analysis_prompt(content)
        logger.debug(f"LLM Prompt:\n{prompt}")
        
        try:
            # Get response from OpenAI
            response = self.client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": "You are a content analyst helping filter articles based on specific criteria."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            logger.debug(f"LLM Response: {result}")
            
            should_skip = result["status"].lower() == "skip"
            reason = result["reason"]
            
            return should_skip, reason
            
        except Exception as e:
            logger.error(f"Error analyzing article: {str(e)}")
            logger.error("OpenAI Error:", exc_info=True)
            return True, f"Error during analysis: {str(e)}"
    
    def _build_analysis_prompt(self, content: str) -> str:
        """
        Build prompt for content analysis.
        
        Args:
            content: Content to analyze
            
        Returns:
            Analysis prompt
        """
        skip_criteria = self.skip_criteria
        if isinstance(skip_criteria, dict):
            skip_criteria = skip_criteria.get('criteria', [])
            
        criteria_text = "\n".join(f"- {c}" for c in skip_criteria)
        
        return f"""Analyze this article content and determine if it should be read or skipped based on the following criteria that I don't want to read about:

{criteria_text}

Important notes:
1. Default to "read" unless the article clearly matches one of the skip criteria
3. Only skip if you are very confident the article matches a skip criterion

Article content:
{content}

Respond with a JSON object containing:
1. "status": Either "read" or "skip"
2. "reason": A brief explanation of why the article should be read or skipped

Example response for a good article:
{{
    "status": "read",
    "reason": "Article contains novel security research findings about a zero-day vulnerability"
}}

or

{{
    "status": "skip",
    "reason": "Article is a basic tutorial covering well-known concepts"
}}

Response:"""

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
