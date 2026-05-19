"""Email adapters for verification code retrieval."""

from adapters.email.base import EmailClient, EmailMessage
from adapters.email.code_extractor import extract_code, poll_verification_code
from adapters.email.generic_api import GenericApiClient, GenericApiConfig
from adapters.email.ouraihub import OuraihubClient, OuraihubConfig
from adapters.email.outlook_graph import OutlookGraphClient

__all__ = [
    'EmailClient',
    'EmailMessage',
    'GenericApiClient',
    'GenericApiConfig',
    'OuraihubClient',
    'OuraihubConfig',
    'OutlookGraphClient',
    'extract_code',
    'poll_verification_code',
]
