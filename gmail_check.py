import os.path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# Define the scope for Gmail and Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Authenticate and connect to Gmail API
def authenticate_gmail_api():
    """
    Authenticates with the Gmail API and returns a service object.
    Saves credentials to 'token.json' for future use.
    """
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_console()  # Use run_console() instead of run_local_server()
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

# Function to parse incoming emails for payment confirmations
def check_payments_in_gmail(service, first_names, payment_keyword="sent you $2"):
    """
    Checks emails in the inbox for a specific keyword in the body and matches the first name.
    
    Args:
        service: Authenticated Gmail API service object.
        first_names (list): List of first names to match in the email body.
        payment_keyword (str): The k
