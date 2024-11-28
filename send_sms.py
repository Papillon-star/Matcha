import gspread
from oauth2client.service_account import ServiceAccountCredentials
import telnyx
import pandas as pd
import os
import re

#TODO SOPHIA EVERY TIME YOU UPDATE FORM/SHEET
#ALARUM
#ALARUM
matched_col_num = 16 #UPDATE THIS MANUALLY

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
      pair[1]['Phone Number'] = pair[1]["Phone Number (you'll get matched by text on Friday!)"]
      pair[0]['Phone Number'] = pair[0]["Phone Number (you'll get matched by text on Friday!)"]

      
      message_1 = {
          'sender': sender_phone_number,
          'recipient': format_phone_number(pair[0]["Phone Number (you'll get matched by text on Friday!)"]),
          'content': 
          (
          f"{pair[0]['First Name']}, you're matched with {pair[1]['First Name']}! Text them to meet this week: {format_phone_number(pair[1]['Phone Number'])}.\n\n"
          f"Bring your match to Great Dane on campus for a FREE pastry with purchase! Just ask for the 'Matcha Promo'.\n\n"
          f"Check out CreaCards to get through exam season: https://www.creacards.ca/user-signup?refer=07c71d24dc424a3427453c5e37670350.\n\n"
          f"Meet someone new by filling out the Matcha form again: {form_link} :)"
          )
      }
      message_2 = {
          'sender': sender_phone_number,
          'recipient': format_phone_number(pair[1]["Phone Number (you'll get matched by text on Friday!)"]),
          'content': 
          (
          f"{pair[1]['First Name']}, you're matched with {pair[0]['First Name']}! Text them to meet this week: {format_phone_number(pair[0]['Phone Number'])}.\n\n"
          f"Bring your match to Great Dane on campus for a FREE pastry with purchase! Just ask for the 'Matcha Promo'.\n\n"
          f"Check out CreaCards to get through exam season: https://www.creacards.ca/user-signup?refer=07c71d24dc424a3427453c5e37670350.\n\n"
          f"Meet someone new by filling out the Matcha form again: {form_link} :)"
          )
      }
      messages.extend([message_1, message_2])
    return messages

def print_group_names(group, group_name):
    print(f"\n{group_name} - Total: {len(group)}")
    if group.empty:
        print("No members in this group.")
    else:
        print(group['First Name'].tolist())

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
df['Row Number'] = df.index + 2

print_group_names(df, "unmatched")

# Check if the DataFrame is empty
if df.empty:
    print("No unmatched students available.")
else:
    print("Data loaded successfully!")
    
    # Group students by year group and mark paid users
    

    group_1_2_paid = df[(df['Year Group'].str.contains('Years 1 & 2')) & (df['Paid'].str.lower() == 'yes')]
    group_3_4_plus_paid = df[(df['Year Group'].str.contains('Years 3 & 4+')) & (df['Paid'].str.lower() == 'yes')]

    group_1_2_unpaid = df[(df['Year Group'].str.contains('Years 1 & 2')) & ((df['Paid'].isnull()) | (df['Paid'].str.lower() != 'yes'))]
    group_3_4_plus_unpaid = df[(df['Year Group'].str.contains('Years 3 & 4+')) & ((df['Paid'].isnull()) | (df['Paid'].str.lower() != 'yes'))]

    print_group_names(group_1_2_paid, "paid 1-2 years")
    print_group_names(group_3_4_plus_paid, "paid 3-4 years")
    print_group_names(group_1_2_unpaid, "unpaid 1-2 years")
    print_group_names(group_3_4_plus_unpaid, "unpaid 3-4 years")


    pairs = []
    unmatched_users = []
    df['Paid'] = df['Paid'].fillna('').str.lower().str.strip()
    
    #print(df.head())


    # Function to pair students based on gender preference within the same year group
    def pair_students_by_gender(group):
      paired = []
      for index, user in group.iterrows():
          # Update 'Matched' status from df to group to ensure synchronization
          user_matched_status = df.at[index, 'Matched']
          if user_matched_status.lower() == 'yes':
              print(f"{user['First Name']} is already matched, moving on.")
              continue

          # Find potential matches based on gender preference and unmatched status
          potential_matches = group[
              (group['Your gender'].str.lower() == user["You want to match with"].strip().lower()) &
              (group["You want to match with"].str.lower() == user['Your gender'].strip().lower()) &
              (group.index != index) &
              (group['Matched'].str.lower() != 'yes')  # Exclude matched users
          ]

          if not potential_matches.empty:
              match = potential_matches.iloc[0]
              pairs.append((user, match))

              # Update 'Matched' status in both df and group
              df.at[index, 'Matched'] = 'Yes'
              df.at[match.name, 'Matched'] = 'Yes'

              group.at[index, 'Matched'] = 'Yes'
              group.at[match.name, 'Matched'] = 'Yes'

              paired.extend([index, match.name])
              print(f"Matched {user['First Name']} with {match['First Name']}")
          else:
              print(f"No potential matches found for {user['First Name']}")

      return paired


    # Pair students by gender within the paid groups
    paired_1_2 = pair_students_by_gender(group_1_2_paid)
    paired_3_4_plus = pair_students_by_gender(group_3_4_plus_paid)

    # Handle leftover students after gender-specific matching for paid users
    leftover_1_2_paid = group_1_2_paid[~group_1_2_paid.index.isin(paired_1_2)]
    leftover_3_4_plus_paid = group_3_4_plus_paid[~group_3_4_plus_paid.index.isin(paired_3_4_plus)]

    print_group_names(leftover_1_2_paid, "leftover paid 1-2 years")
    print_group_names(leftover_3_4_plus_paid, "leftover paid 3-4 years")

    # Add the leftover paid students to the unpaid groups for regular matching
    group_1_2_unpaid_combined = pd.concat([group_1_2_unpaid, leftover_1_2_paid])
    group_3_4_plus_unpaid_combined = pd.concat([group_3_4_plus_unpaid, leftover_3_4_plus_paid])
    

    print_group_names(group_1_2_unpaid_combined, "unpaid+leftover paid 1-2 years")
    print_group_names(group_3_4_plus_unpaid_combined, "unpaid+leftover paid 3-4 years")

    def pair_students_randomly(group):
      paired = []
      # Exclude users who have already been matched
      group = group[group['Matched'].str.lower() != 'yes'].copy()
      group = group.sample(frac=1).reset_index(drop=False)  # Shuffle and reset index

      for i in range(0, len(group) - 1, 2):
          user1 = group.iloc[i]
          user2 = group.iloc[i + 1]
          pairs.append((user1, user2))

          # Update 'Matched' status in df using original index
          df.at[user1['index'], 'Matched'] = 'Yes'
          df.at[user2['index'], 'Matched'] = 'Yes'

          # Optionally update 'Matched' status in group
          group.at[user1.name, 'Matched'] = 'Yes'
          group.at[user2.name, 'Matched'] = 'Yes'

          print(f"Randomly matched {user1['First Name']} with {user2['First Name']}")

      # Handle the last unpaired user, if any
      if len(group) % 2 == 1:
          unpaired_user = group.iloc[-1]
          unmatched_users.append(unpaired_user)
          print(f"No match for {unpaired_user['First Name']}, they will be unmatched.")

      return paired



    print("matching combined leftovers randomly")
    # Now handle pairing for the combined unpaid groups (including leftover paid users)
    paired_1_2_unpaid = pair_students_randomly(group_1_2_unpaid_combined)
    paired_3_4_plus_unpaid = pair_students_randomly(group_3_4_plus_unpaid_combined)

    unmatched_users_df = pd.DataFrame(unmatched_users)

    # Now, handle unmatched users from both groups
    if not unmatched_users_df.empty:
        unmatched_users_df = unmatched_users_df.reset_index(drop=True)
        while len(unmatched_users_df) > 1:
            user1 = unmatched_users_df.iloc[0]
            user2 = unmatched_users_df.iloc[1]
            pairs.append((user1, user2))
            df.at[user1['index'], 'Matched'] = 'Yes'
            df.at[user2['index'], 'Matched'] = 'Yes'
            unmatched_users_df = unmatched_users_df.iloc[2:].reset_index(drop=True)
            print(f"Matched leftover {user1['First Name']} with {user2['First Name']}")
        # If there's still an unmatched user, match with Sophia
        if len(unmatched_users_df) == 1:
            unmatched_user = unmatched_users_df.iloc[0]
            sophia = {
                'First Name': 'Sophia',
                "Phone Number (you'll get matched by text on Friday!)": '2369781211',
                'Phone Number': '2369781211',
                'Year Group': 'N/A',
                'Your gender': 'female',
                'Matched': 'N/A'
            }
            pairs.append((unmatched_user, sophia))
            df.at[unmatched_user['index'], 'Matched'] = 'Yes'
            print(f"Matching {unmatched_user['First Name']} with Sophia.")
      
    def print_pairs(pairs):
      print("\nFinished pairing:")
      if not pairs:
          print("No pairs were formed.")
      else:
          for i, (user1, user2) in enumerate(pairs, start=1):
              user1_name = user1['First Name']
              user2_name = user2['First Name']
              print(f"Pair {i}: {user1_name} matched with {user2_name}")
    print_pairs(pairs)


    # # Prepare and send SMS messages
    messages = prepare_sms_messages(pairs)
    for message in messages:
        send_sms(message)


  # Mark matched students in the Google 
  



for pair in pairs:
    user1 = pair[0]
    user2 = pair[1]

    if isinstance(user1, pd.Series):
      # print(user1.head())
      row_num1 = user1['Row Number']
      col_num = df.columns.get_loc("Matched") + 1  # +1 because gspread columns are 1-based
      sheet.update_cell(row_num1, matched_col_num, "Yes")
      print(f"Updated 'Matched' status at row {row_num1}, col {matched_col_num} for {user1['First Name']}")

    if isinstance(user2, pd.Series):  # Check if the second person is a DataFrame row (not Sophia)
      # print(user2.head())      
      row_num2 = user2['Row Number']
      col_num = df.columns.get_loc("Matched") + 1
      sheet.update_cell(row_num2, matched_col_num, "Yes")
      print(f"Updated 'Matched' status at row {row_num2}, col {matched_col_num} for {user2['First Name']}")


