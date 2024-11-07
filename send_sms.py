# Import necessary modules from gmail_check.py
from gmail_check import authenticate_gmail_api, check_payments_in_gmail, get_unmatched_first_names_from_sheet
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import telnyx
import pandas as pd
import os
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
        print(response)
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

# Main function for your script
def main():
    # Authenticate with Gmail API
    service = authenticate_gmail_api()

    # Authenticate and connect to Google Sheets
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('config/matcha-aug26-4ff2f9ef6f54.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open("Matcha Aug26 Responses").sheet1

    # Get unmatched first names and DataFrame from the Google Sheet
    unmatched_first_names, df, sheet = get_unmatched_first_names_from_sheet()

    # Check for payment confirmations
    confirmed_names = check_payments_in_gmail(service, unmatched_first_names, payment_keyword="sent you $2")
    print("Confirmed names with payments:", confirmed_names)

    # Update 'Paid' status in the Google Sheet
    for name in confirmed_names:
        matching_index = df[df['First Name'].str.lower() == name.lower()].index
        if not matching_index.empty:
            sheet.update_cell(matching_index[0] + 2, df.columns.get_loc("Paid") + 1, "Paid")
            print(f"Updated 'Paid' status for {name}")

    # Filter out people who have already been matched
    df = df[df['Matched'].str.lower() != 'yes']

    # Check if the DataFrame is empty
    if df.empty:
        print("No unmatched students available.")
        return
    else:
        print("Data loaded successfully!")
        print(df.head())  # Display the first few rows if data is available

        # Group students by year group as strings
        group_1_2 = df[df['Year Group'].str.contains('Years 1 & 2')]
        group_3_4_plus = df[df['Year Group'].str.contains('Years 3 & 4+')]

        pairs = []

        # Function to pair students and handle remainders
        def pair_students_and_handle_remainders(group):
            paired = []
            for i in range(0, len(group) - 1, 2):
                pairs.append((group.iloc[i], group.iloc[i + 1]))
                paired.extend([group.index[i], group.index[i + 1]])  # Store indexes for updating
            return paired

        # Initial pairing within the same year group
        paired_1_2 = pair_students_and_handle_remainders(group_1_2)
        paired_3_4_plus = pair_students_and_handle_remainders(group_3_4_plus)

        # Handle leftover students
        leftover_1_2 = group_1_2[~group_1_2.index.isin(paired_1_2)]
        leftover_3_4_plus = group_3_4_plus[~group_3_4_plus.index.isin(paired_3_4_plus)]

        # Pair leftover students across groups if both groups have leftovers
        while not leftover_1_2.empty and not leftover_3_4_plus.empty:
            pairs.append((leftover_1_2.iloc[0], leftover_3_4_plus.iloc[0]))
            paired_1_2.append(leftover_1_2.index[0])
            paired_3_4_plus.append(leftover_3_4_plus.index[0])
            leftover_1_2 = leftover_1_2.iloc[1:]
            leftover_3_4_plus = leftover_3_4_plus.iloc[1:]

        # If any students are still unpaired, match them with 'Sophia'
        unpaired = pd.concat([leftover_1_2, leftover_3_4_plus])

        if not unpaired.empty:
            sophia = {
                'First Name': 'Sophia',
                'Phone Number (you\'ll get matched by text on Friday!)': '2369781211'
            }
            print(f"Matching {unpaired.iloc[0]['First Name']} with Sophia.")
            pairs.append((unpaired.iloc[0], sophia))

        # Prepare and send SMS messages
        messages = prepare_sms_messages(pairs)
        for message in messages:
            send_sms(message)

        # Mark matched students in the Google Sheet
        for pair in pairs:
            if isinstance(pair[1], pd.Series):  # This checks if the second person is a DataFrame row (not Sophia)
                sheet.update_cell(pair[0].name + 2, df.columns.get_loc("Matched") + 1, "Yes")
                sheet.update_cell(pair[1].name + 2, df.columns.get_loc("Matched") + 1, "Yes")
            else:  # If the second person is Sophia, update only the student
                sheet.update_cell(pair[0].name + 2, df.columns.get_loc("Matched") + 1, "Yes")

# Run the main function
if __name__ == "__main__":
    main()
