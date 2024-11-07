import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import random
import telnyx
import re

# Set your Telnyx API key
telnyx.api_key = "***REMOVED***"

# Define your sender phone number
sender_phone_number = "+12364848188"

# Function to format phone numbers to include country code
def format_phone_number(phone_number, country_code="+1"):
    phone_number = str(phone_number)  # Convert to string if not already
    phone_number = re.sub(r"[^\d]", "", phone_number)  # Remove delimiters
    if not phone_number.startswith("+"):
        phone_number = country_code + phone_number
    return phone_number

# Function to send SMS using Telnyx API
def send_sms(message):
    try:
        response = telnyx.Message.create(
            from_=message['sender'],
            to=message['recipient'],
            text=message['content']
        )
        print(f"Message sent to {message['recipient']}")
        if 'to' in response and response['to'][0]['status']:
            print(f"Message status: {response['to'][0]['status']}")
            return response['to'][0]['status']
        else:
            print("Unexpected response structure, could not find status.")
            return "unknown"
    except telnyx.error.InvalidRequestError as e:
        print(f"Failed to send message to {message['recipient']}: {e}")
        print(f"Full details: {e.errors}")
        return None

# Function to prepare SMS messages
def prepare_sms_messages(pairs):
    form_link = "https://forms.gle/UQbWiWj8j5mf6KzNA"
    messages = []
    for pair in pairs:
        message_1 = {
            'sender': sender_phone_number,
            'recipient': format_phone_number(pair[0]["Phone Number (you'll get matched by text on Friday!)"]),
            'content': f"{pair[0]['First Name']}, you're matched with {pair[1]['First Name']}! Text them to meet this week: {format_phone_number(pair[1]['Phone Number (you\'ll get matched by text on Friday!)'])}.\n\n"
                       f"Bring your match to Great Dane on campus for a FREE pastry with purchase! Just ask staff for the 'Matcha Promo'.\n\n"
                       f"Meet someone new by filling out the Matcha form again: {form_link} :)"
        }
        message_2 = {
            'sender': sender_phone_number,
            'recipient': format_phone_number(pair[1]["Phone Number (you'll get matched by text on Friday!)"]),
            'content': f"{pair[1]['First Name']}, you're matched with {pair[0]['First Name']}! Text them to meet this week: {format_phone_number(pair[0]['Phone Number (you\'ll get matched by text on Friday!)'])}.\n\n"
                       f"Bring your match to Great Dane on campus for a FREE pastry with purchase! Just ask staff for the 'Matcha Promo'.\n\n"
                       f"Meet someone new by filling out the Matcha form again: {form_link} :)"
        }
        messages.extend([message_1, message_2])
    return messages

# Authenticate and connect to Google Sheets
def connect_to_google_sheets(sheet_name="Matcha Aug26 Responses"):
    """
    Connects to the specified Google Sheet and returns the sheet object and DataFrame.
    """
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('config/matcha-aug26-4ff2f9ef6f54.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1

    # Load the sheet data into a DataFrame
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    return df, sheet

# Function to find gender-specific matches for paid users
def find_gender_matches(df):
    """
    Finds gender-specific matches for users marked as 'Paid' and not 'Matched'.
    
    Args:
        df (DataFrame): The DataFrame containing user data.

    Returns:
        List of tuples representing matched pairs and the updated DataFrame.
    """
    paid_users = df[(df['Paid'].str.lower() == 'yes') & (df['Matched'].str.lower() != 'yes')]
    matches = []

    for index, user in paid_users.iterrows():
        if user['Matched'].lower() == 'yes':
            continue
        
        # Find potential matches based on gender preference
        potential_matches = paid_users[
            (paid_users['Gender'].str.lower() == user['Gender Preference'].strip().lower()) &
            (paid_users['Gender Preference'].str.lower() == user['Gender'].strip().lower()) &
            (paid_users.index != index)
        ]

        if not potential_matches.empty:
            match = potential_matches.iloc[0]
            matches.append((user, match))
            df.at[index, 'Matched'] = 'Yes'
            df.at[match.name, 'Matched'] = 'Yes'
        else:
            # Check if user can be matched with Sophia if they want a female
            if user['Gender Preference'].strip().lower() == 'female':
                sophia = {
                    'First Name': 'Sophia',
                    'Gender': 'female',
                    'Gender Preference': 'N/A',
                    'Paid': 'N/A',
                    'Matched': 'N/A',
                    'Phone Number (you\'ll get matched by text on Friday!)': '2369781211'
                }
                matches.append((user, sophia))
                df.at[index, 'Matched'] = 'Yes'
                print(f"{user['First Name']} matched with Sophia.")
            else:
                print(f"No match found for {user['First Name']} this week. They will be re-evaluated next week.")

    return matches, df

# Function to perform random matching for everyone else
def random_matching(df):
    """
    Matches all remaining unmatched users randomly.
    
    Args:
        df (DataFrame): The DataFrame containing user data.

    Returns:
        List of tuples representing random matches and the updated DataFrame.
    """
    unmatched_users = df[df['Matched'].str.lower() != 'yes']
    matches = []

    while len(unmatched_users) > 1:
        user1 = unmatched_users.iloc[0]
        user2 = unmatched_users.iloc[1]
        matches.append((user1, user2))
        df.at[user1.name, 'Matched'] = 'Yes'
        df.at[user2.name, 'Matched'] = 'Yes'
        unmatched_users = unmatched_users.iloc[2:]

    return matches, df

# Main function to run the matching process and send SMS
if __name__ == "__main__":
    # Connect to the Google Sheet and get data
    df, sheet = connect_to_google_sheets()

    # Step 1: Find gender-specific matches for paid users
    gender_matches, df = find_gender_matches(df)

    # Step 2: Perform random matching for everyone else
    random_matches, df = random_matching(df)

    # Combine all matches
    all_matches = gender_matches + random_matches

    # Prepare and send SMS messages
    if all_matches:
        messages = prepare_sms_messages(all_matches)
        for message in messages:
            send_sms(message)

        # Update the Google Sheet with the matched users
        for match in all_matches:
            user1 = match[0]
            user2 = match[1]
            sheet.update_cell(user1.name + 2, df.columns.get_loc("Matched") + 1, "Yes")
            if isinstance(user2, pd.Series):
                sheet.update_cell(user2.name + 2, df.columns.get_loc("Matched") + 1, "Yes")
        print("All matches have been updated and SMS messages sent.")
    else:
        print("No matches were found.")
