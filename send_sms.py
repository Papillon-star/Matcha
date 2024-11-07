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

# Authenticate and connect to Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('config/matcha-aug26-4ff2f9ef6f54.json', scope)
client = gspread.authorize(creds)
sheet = client.open("Matcha Aug26 Responses").sheet1

# Define unique expected headers
expected_headers = [
    "Timestamp", "First Name", "Year Group", 
    "Phone Number (you'll get matched by text on Friday!)", "Paid", "Matched", 
    "Your gender", "Your match's gender"
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

    # Group students by year group and mark paid users
    group_1_2 = df[(df['Year Group'].str.contains('Years 1 & 2')) & (df['Paid'].str.lower() == 'yes')]
    group_3_4_plus = df[(df['Year Group'].str.contains('Years 3 & 4+')) & (df['Paid'].str.lower() == 'yes')]

    pairs = []

    # Function to pair students based on gender preference within the same year group
    def pair_students_by_gender(group):
        paired = []
        for index, user in group.iterrows():
            if user['Matched'].lower() == 'yes':
                continue

            # Find potential matches based on gender preference
            potential_matches = group[
                (group['Gender'].str.lower() == user["Your match's gender"].strip().lower()) &
                (group["Your match's gender"].str.lower() == user['Your gender'].strip().lower()) &
                (group.index != index)
            ]

            if not potential_matches.empty:
                match = potential_matches.iloc[0]
                pairs.append((user, match))
                df.at[index, 'Matched'] = 'Yes'
                df.at[match.name, 'Matched'] = 'Yes'
                paired.extend([user.name, match.name])

        return paired

    # Pair students by gender within the same year groups
    paired_1_2 = pair_students_by_gender(group_1_2)
    paired_3_4_plus = pair_students_by_gender(group_3_4_plus)

    # Handle leftover students after gender-specific matching
    leftover_1_2 = group_1_2[~group_1_2.index.isin(paired_1_2)]
    leftover_3_4_plus = group_3_4_plus[~group_3_4_plus.index.isin(paired_3_4_plus)]

    # Combine unmatched users and perform random matching across groups
    unmatched = pd.concat([leftover_1_2, leftover_3_4_plus])
    if not unmatched.empty:
        while len(unmatched) > 1:
            user1 = unmatched.iloc[0]
            user2 = unmatched.iloc[1]
            pairs.append((user1, user2))
            df.at[user1.name, 'Matched'] = 'Yes'
            df.at[user2.name, 'Matched'] = 'Yes'
            unmatched = unmatched.iloc[2:]

    # Match overflow users with Sophia if necessary
    if not unmatched.empty:
        sophia = {
            'First Name': 'Sophia',
            'Phone Number (you\'ll get matched by text on Friday!)': '2369781211',
            'Year Group': 'N/A',
            'Your gender': 'female',
            'Matched': 'N/A'
        }
        pairs.append((unmatched.iloc[0], sophia))
        df.at[unmatched.index[0], 'Matched'] = 'Yes'
        print(f"Matching {unmatched.iloc[0]['First Name']} with Sophia.")

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
