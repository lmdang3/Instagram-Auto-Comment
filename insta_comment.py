# ── IMPORTS ──────────────────────────────────────────────────────────────────
# instagrapi: third-party library that lets us interact with Instagram's API
# pandas: used to read/write CSV files (our username list and comment log)
# time: used to add delays between comments to avoid Instagram bans
# os: used to read environment variables (username/password from .env)
# dotenv: loads the .env file so os.getenv() can access our credentials
from instagrapi import Client
import pandas as pd
import time
import os
from dotenv import load_dotenv

# ── CONFIG ────────────────────────────────────────────────────────────────────
# Load the .env file into the environment so we can safely read credentials
# without hardcoding them in the script
load_dotenv()

# Read the Instagram login credentials from the .env file
# If either is missing, the script will raise an error below
USERNAME = os.getenv("INSTAGRAM_USERNAME")
PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

# Stop the script early if credentials are missing rather than failing mid-run
if not USERNAME or not PASSWORD:
    raise ValueError("Missing credentials — make sure INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD are set in your .env file")

# The Instagram post URL you want to comment on — change this to any post/reel URL
TARGET_URL = "https://www.instagram.com/p/DYAmnyrBhll/"

# How long to wait (in seconds) between each comment
# Keeping this at 30+ seconds reduces the risk of Instagram flagging the account
DELAY_BETWEEN_COMMENTS = 30

# The CSV file used to log every comment made (acts as a history/audit trail)
COMMENTED_LOG = "Commented_List.csv"

# The CSV file containing the list of usernames to comment
USERNAME_LIST = "Instagram_List.csv"

# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────

def get_media_id_from_url(cl, url):
    """
    Converts an Instagram post URL into a numeric media ID.
    Instagram's API requires a media ID (not a URL) to post comments.
    Example: https://www.instagram.com/p/ABC123/ -> 3012345678901234567
    """
    media_pk = cl.media_pk_from_url(url)
    return str(media_pk)

def load_commented(log_file):
    """
    Reads the comment log CSV and returns a set of usernames already commented.
    Returns an empty set if the file doesn't exist or has no data yet.
    Used at startup to avoid re-commenting users from a previous session.
    """
    try:
        df = pd.read_csv(log_file)
        return set(df["username"].astype(str).tolist())
    except (FileNotFoundError, KeyError):
        return set()

def save_commented(log_file, username):
    """
    Appends a username to the comment log CSV after successfully commenting.
    This keeps a running history of every comment made across all sessions.
    If the file doesn't exist yet, it creates it automatically.
    """
    try:
        df = pd.read_csv(log_file)
    except (FileNotFoundError, KeyError):
        df = pd.DataFrame(columns=["username"])
    df.loc[len(df)] = [username]
    df.to_csv(log_file, index=False, encoding="utf-8")

# ── LOGIN ─────────────────────────────────────────────────────────────────────
# Create a new Instagram client instance
cl = Client()

try:
    # Attempt to log in with username and password from .env
    cl.login(USERNAME, PASSWORD)
    print("Logged in successfully\n")
except Exception as e:
    # If Instagram requires a 2FA code, prompt the user to enter it
    # This happens when Two-Factor Authentication is enabled on the account
    if "Two-factor" in str(e) or "two_factor" in str(e).lower():
        verification_code = input("Enter your 2FA code from your authenticator app: ").strip()
        cl.login(USERNAME, PASSWORD, verification_code=verification_code)
        print("Logged in successfully with 2FA\n")
    else:
        # If it's a different error (wrong password, banned, etc.) raise it so we can see it
        raise

# ── RESOLVE TARGET POST ───────────────────────────────────────────────────────
# Convert the TARGET_URL into a media ID that Instagram's API can use
# This only runs once at startup — the media ID stays the same for the whole session
print(f"Fetching media ID for: {TARGET_URL}")
media_id = get_media_id_from_url(cl, TARGET_URL)
print(f"Media ID: {media_id}\n")

# ── INFINITE COMMENT LOOP ─────────────────────────────────────────────────────
# The script runs forever, cycling through all usernames repeatedly
# Add new usernames to Instagram_List.csv while running — they'll be picked up next cycle
# Press Ctrl+C at any time to stop cleanly
print("Running infinitely -- press Ctrl+C to stop\n")

# Tracks which cycle (full pass through the username list) we are on
cycle = 1

try:
    while True:
        # Re-read the username list at the start of every cycle
        # This means any names you add to Instagram_List.csv while the script
        # is running will automatically be included in the next cycle
        usernames_df = pd.read_csv(USERNAME_LIST)

        # Drop empty rows and clean up any extra whitespace around usernames
        all_usernames = usernames_df["Username"].dropna().astype(str).str.strip().tolist()

        # If the CSV is empty, wait and check again instead of crashing
        if not all_usernames:
            print(f"No usernames found in {USERNAME_LIST}, waiting {DELAY_BETWEEN_COMMENTS}s...")
            time.sleep(DELAY_BETWEEN_COMMENTS)
            continue

        print(f"--- Cycle {cycle} | {len(all_usernames)} username(s) ---")

        # Loop through every username in the list and post a comment
        for username in all_usernames:
            # Format the comment as a tag e.g. @john_doe
            comment_text = f"@{username}"
            print(f"Commenting: {comment_text}")

            try:
                # Post the comment to the target Instagram post
                cl.media_comment(media_id, comment_text)

                # Log the comment to Commented_List.csv as a history record
                save_commented(COMMENTED_LOG, username)

                print(f"   Done -- waiting {DELAY_BETWEEN_COMMENTS}s before next comment...")

            except Exception as error:
                # If a comment fails (post has comments disabled, rate limited, etc.)
                # print the error and move on to the next username instead of crashing
                print(f"   Failed to comment on @{username}: {error}")

            # Wait between comments regardless of success or failure
            # This is important to avoid triggering Instagram's spam detection
            time.sleep(DELAY_BETWEEN_COMMENTS)

        # After finishing all usernames, increment the cycle counter and start over
        print(f"--- Cycle {cycle} complete, starting over ---\n")
        cycle += 1

except KeyboardInterrupt:
    # Triggered when the user presses Ctrl+C — exits cleanly without a crash traceback
    print("\nStopped by user. Goodbye!")
