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
    # Remove common delimiters such as spaces, dashes, and parentheses
    phone_number = re.sub(r"[^\d]", "", phone_number)
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

        # Check if the response contains the expected data
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
    form_link = "https://forms.gle/UQbWiWj8j5mf6KzNA"  # Your Google Forms link
    messages = []
    for pair in pairs:
        if len(pair) == 2:  # Pair of two students
            message_1 = {
                'sender': sender_phone_number,
                'recipient': format_phone_number(pair[0]["Phone Number (you'll get matched by text on Friday!)"]),
                'content': f"{pair[0]['First Name']}, you're matched with {pair[1]['First Name']}! Text them to meet this week: {format_phone_number(pair[1]['Phone Number (you\'ll get matched by text on Friday!)'])}. Meet someone new by filling out the Matcha form again: {form_link} :)"
            }
            message_2 = {
                'sender': sender_phone_number,
                'recipient': format_phone_number(pair[1]["Phone Number (you'll get matched by text on Friday!)"]),
                'content': f"{pair[1]['First Name']}, you're matched with {pair[0]['First Name']}! Text them to meet this week: {format_phone_number(pair[0]['Phone Number (you\'ll get matched by text on Friday!)'])}. Meet someone new by filling out the Matcha form again: {form_link} :)"
            }
            messages.extend([message_1, message_2])
        elif len(pair) == 3:  # Group of three students
            message_1 = {
                'sender': sender_phone_number,
                'recipient': format_phone_number(pair[0]["Phone Number (you'll get matched by text on Friday!)"]),
                'content': f"{pair[0]['First Name']}, you're matched with {pair[1]['First Name']} and {pair[2]['First Name']}! Text them to meet this week: {format_phone_number(pair[1]['Phone Number (you\'ll get matched by text on Friday!)'])}, {format_phone_number(pair[2]['Phone Number (you\'ll get matched by text on Friday!)'])}. Meet someone new by filling out the Matcha form again: {form_link} :)"
            }
            messages.append(message_1)
    return messages

# Authenticate and connect to Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('config/matcha-aug26-4ff2f9ef6f54.json', scope)
client = gspread.authorize(creds)
sheet = client.open("Matcha Aug26 Responses").sheet1

# Define unique expected headers
expected_headers = [
    "Timestamp", "First Name", "Year Group", 
    "Phone Number (you'll get matched by text on Friday!)", "Any Feedback?", "Matched"
]

# Retrieve data using expected_headers
data = sheet.get_all_records(expected_headers=expected_headers)
df = pd.DataFrame(data)

# Ensure the "Matched" column exists in the DataFrame
if 'Matched' not in df.columns:
    df['Matched'] = 'No'

# Filter out people who have already been matched
df = df[df['Matched'].str.lower() != 'yes']
# Check if the DataFrame is empty
if df.empty:
    print("No unmatched students available.")
else:
    print("Data loaded successfully!")
    print(df.head())  # Display the first few rows if data is available

    # Group students by year group as strings
    group_1_2 = df[df['Year Group'].str.contains('Years 1 & 2')]
    group_3_4_plus = df[df['Year Group'].str.contains('Years 3 & 4+')]

    pairs = []

    # Function to pair students and handle groups of three if necessary
    def pair_students_and_handle_remainders(group):
        paired = []
        for i in range(0, len(group) - 1, 2):
            pairs.append((group.iloc[i], group.iloc[i + 1]))
            paired.extend([group.iloc[i]['First Name'], group.iloc[i + 1]['First Name']])
        return paired

    # Initial pairing within the same year group
    paired_1_2 = pair_students_and_handle_remainders(group_1_2)
    paired_3_4_plus = pair_students_and_handle_remainders(group_3_4_plus)

    # Handle leftover students
    leftover_1_2 = group_1_2[~group_1_2['First Name'].isin(paired_1_2)]
    leftover_3_4_plus = group_3_4_plus[~group_3_4_plus['First Name'].isin(paired_3_4_plus)]

    # Pair leftover students across groups if both groups have leftovers
    while not leftover_1_2.empty and not leftover_3_4_plus.empty:
        pairs.append((leftover_1_2.iloc[0], leftover_3_4_plus.iloc[0]))
        leftover_1_2 = leftover_1_2.iloc[1:]
        leftover_3_4_plus = leftover_3_4_plus.iloc[1:]

    # If any students are still unpaired, try to form a group of three
    unpaired = pd.concat([leftover_1_2, leftover_3_4_plus])
    if len(unpaired) == 3:
        pairs.append((unpaired.iloc[0], unpaired.iloc[1], unpaired.iloc[2]))
    elif len(unpaired) == 2:
        pairs.append((unpaired.iloc[0], unpaired.iloc[1]))
    elif len(unpaired) == 1:
        if pairs:
            pairs[-1] = pairs[-1] + (unpaired.iloc[0],)

    # Prepare and send SMS messages
    messages = prepare_sms_messages(pairs)
    for message in messages:
        send_sms(message)
    
    # Mark matched students in the Google Sheet
    for pair in pairs:
        if len(pair) == 2:  # Pair of two students
            sheet.update_cell(pair[0].name + 2, df.columns.get_loc("Matched") + 1, "Yes")
            sheet.update_cell(pair[1].name + 2, df.columns.get_loc("Matched") + 1, "Yes")
        elif len(pair) == 3:  # Group of three students
            sheet.update_cell(pair[0].name + 2, df.columns.get_loc("Matched") + 1, "Yes")
            sheet.update_cell(pair[1].name + 2, df.columns.get_loc("Matched") + 1, "Yes")
            sheet.update_cell(pair[2].name + 2, df.columns.get_loc("Matched") + 1, "Yes")
