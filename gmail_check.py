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
        # Save the credentials for the next runs
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
        payment_keyword (str): The keyword indicating a payment in the email body.

    Returns:
        List of first names that match the search criteria.
    """
    results = service.users().messages().list(userId='me', q='in:inbox').execute()
    messages = results.get('messages', [])
    confirmed_names = []

    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        msg_payload = msg['payload']
        body = ""

        # Extract and decode the email body
        if 'parts' in msg_payload:
            for part in msg_payload['parts']:
                if part['mimeType'] == 'text/plain' and 'data' in part:
                    body += base64.urlsafe_b64decode(part['data']).decode()

        if body == "" and 'data' in msg_payload['body']:
            body = base64.urlsafe_b64decode(msg_payload['body']['data']).decode()

        # Check for payment keyword and matching first name in the email body
        for first_name in first_names:
            if payment_keyword.lower() in body.lower() and first_name.lower() in body.lower():
                confirmed_names.append(first_name)
                break  # Stop searching once a match is found

    return confirmed_names

# Authenticate and connect to Google Sheets
def get_unmatched_first_names_from_sheet(sheet_name="Matcha Aug26 Responses"):
    """
    Retrieves the list of first names from the Google Sheet that have not yet been matched.
    
    Returns:
        List of unmatched first names and the DataFrame and sheet object for updating.
    """
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('config/matcha-aug26-4ff2f9ef6f54.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1

    # Load the sheet data into a DataFrame
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    # Filter for unmatched first names (where 'Matched' column is not 'Yes')
    unmatched_df = df[df['Matched'].str.lower() != 'yes']
    unmatched_first_names = unmatched_df['First Name'].tolist()

    return unmatched_first_names, df, sheet

# Main code to authenticate, check payments, and update the Google Sheet
if __name__ == "__main__":
    # Authenticate with Gmail API
    service = authenticate_gmail_api()

    # Get unmatched first names and DataFrame from the Google Sheet
    unmatched_first_names, df, sheet = get_unmatched_first_names_from_sheet()

    # Check for payment confirmations and print the matched names
    confirmed_names = check_payments_in_gmail(service, unmatched_first_names, payment_keyword="sent you $2")
    print("Confirmed names with payments:", confirmed_names)

    # Update 'Paid' status in the Google Sheet
    for name in confirmed_names:
        matching_index = df[df['First Name'].str.lower() == name.lower()].index
        if not matching_index.empty:
            sheet.update_cell(matching_index[0] + 2, df.columns.get_loc("Paid") + 1, "Paid")
            print(f"Updated 'Paid' status for {name}")

    print("All relevant users have been updated.")
