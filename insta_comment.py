from instagrapi import Client
import pandas as pd
import time
import os
from dotenv import load_dotenv

# ── LOAD CREDENTIALS FROM .env ───────────────────────────────────────────────
load_dotenv()
USERNAME = os.getenv("INSTAGRAM_USERNAME")
PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

if not USERNAME or not PASSWORD:
    raise ValueError("Missing credentials — make sure INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD are set in your .env file")

TARGET_URL = "https://www.instagram.com/p/DYAmnyrBhll/"  # <-- paste your target post URL here

DELAY_BETWEEN_COMMENTS = 30  # seconds to wait between comments (avoid bans)
COMMENTED_LOG = "Commented_List.csv"
USERNAME_LIST = "Instagram_List.csv"
# ────────────────────────────────────────────────────────────────────────────

def get_media_id_from_url(cl, url):
    """Extract the media ID from an Instagram post/reel URL."""
    media_pk = cl.media_pk_from_url(url)
    return str(media_pk)

def load_commented(log_file):
    """Load the list of usernames already commented."""
    try:
        df = pd.read_csv(log_file)
        return set(df["username"].astype(str).tolist())
    except (FileNotFoundError, KeyError):
        return set()

def save_commented(log_file, username):
    """Append a newly commented username to the log CSV."""
    try:
        df = pd.read_csv(log_file)
    except (FileNotFoundError, KeyError):
        df = pd.DataFrame(columns=["username"])
    df.loc[len(df)] = [username]
    df.to_csv(log_file, index=False, encoding="utf-8")

# ── LOGIN ────────────────────────────────────────────────────────────────────
cl = Client()
try:
    cl.login(USERNAME, PASSWORD)
    print("✅ Logged in successfully\n")
except Exception as e:
    if "Two-factor" in str(e) or "two_factor" in str(e).lower():
        verification_code = input("Enter your 2FA code from your authenticator app: ").strip()
        cl.login(USERNAME, PASSWORD, verification_code=verification_code)
        print("Logged in successfully with 2FA\n")
    else:
        raise

# ── GET TARGET MEDIA ID ──────────────────────────────────────────────────────
print(f"🔗 Fetching media ID for: {TARGET_URL}")
media_id = get_media_id_from_url(cl, TARGET_URL)
print(f"   Media ID: {media_id}\n")

# ── CONTINUOUS LOOP (press Ctrl+C to stop) ───────────────────────────────────
print("Running continuously — press Ctrl+C to stop\n")

try:
    while True:
        # Re-read both files each pass so new usernames added to the CSV are picked up
        usernames_df = pd.read_csv(USERNAME_LIST)
        all_usernames = usernames_df["Username"].dropna().astype(str).str.strip().tolist()
        already_commented = load_commented(COMMENTED_LOG)

        pending = [u for u in all_usernames if u not in already_commented]
        print(f"Pass check: {len(all_usernames)} in list | {len(already_commented)} already commented | {len(pending)} pending\n")

        if not pending:
            print(f"All usernames have been commented. Checking again in {DELAY_BETWEEN_COMMENTS}s (add new usernames to {USERNAME_LIST} to continue)...")
            time.sleep(DELAY_BETWEEN_COMMENTS)
            continue

        for username in pending:
            comment_text = f"@{username}"
            print(f"Commenting: {comment_text}")

            try:
                cl.media_comment(media_id, comment_text)
                save_commented(COMMENTED_LOG, username)
                print(f"   Done -- waiting {DELAY_BETWEEN_COMMENTS}s before next comment...")
            except Exception as error:
                print(f"   Failed to comment on @{username}: {error}")

            time.sleep(DELAY_BETWEEN_COMMENTS)

except KeyboardInterrupt:
    print("\nStopped by user. Goodbye!")
