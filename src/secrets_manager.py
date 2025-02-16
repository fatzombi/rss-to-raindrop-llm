"""AWS Secrets Manager utilities."""

import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

def get_secret(secret_arn: str) -> str:
    """
    Retrieve a secret from AWS Secrets Manager.
    
    Args:
        secret_arn: ARN of the secret to retrieve
        
    Returns:
        The secret string value
        
    Raises:
        ClientError: If there's an error retrieving the secret
    """
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager'
    )
    
    try:
        response = client.get_secret_value(
            SecretId=secret_arn
        )
        return response['SecretString']
    except ClientError as e:
        logger.error(f"Error retrieving secret: {str(e)}")
        raise
