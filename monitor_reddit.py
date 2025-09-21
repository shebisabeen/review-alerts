import requests
import sqlite3
import os
import time
from typing import List
from dotenv import load_dotenv
from datetime import datetime
import logging

# Load environment variables from .env file
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# -------- CONFIGURATION -------- #
CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER = os.getenv("REDDIT_USER")
REDDIT_PASS = os.getenv("REDDIT_PASS")
USER_AGENT = os.getenv("REDDIT_USER_AGENT")
SUBREDDIT = os.getenv("REDDIT_SUBREDDIT")
MOD_USERNAMES = set(os.getenv("REDDIT_MOD_USERNAMES").split(","))
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
DB_PATH = os.getenv("REDDIT_DATABASE_PATH")
FETCH_LIMIT = int(os.getenv("REDDIT_FETCH_LIMIT"))
# -------------------------------- #

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS alerted_posts (
            post_id TEXT PRIMARY KEY,
            mod_replied INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def has_been_alerted(post_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM alerted_posts WHERE post_id = ?", (post_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_as_alerted(post_id: str, mod_replied: bool = False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO alerted_posts (post_id, mod_replied) VALUES (?, ?)",
        (post_id, int(mod_replied))
    )
    conn.commit()
    conn.close()

def get_reddit_token() -> str:
    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    data = {'grant_type': 'password', 'username': REDDIT_USER, 'password': REDDIT_PASS}
    headers = {'User-Agent': USER_AGENT}
    res = requests.post("https://www.reddit.com/api/v1/access_token", auth=auth, data=data, headers=headers)
    res.raise_for_status()
    return res.json()['access_token']

def fetch_new_posts(token: str):
    headers = {'Authorization': f'bearer {token}', 'User-Agent': USER_AGENT}
    url = f"https://oauth.reddit.com/r/{SUBREDDIT}/new"
    res = requests.get(url, headers=headers, params={'limit': FETCH_LIMIT})
    res.raise_for_status()
    return res.json()['data']['children']

def fetch_comments(token: str, permalink: str):
    headers = {'Authorization': f'bearer {token}', 'User-Agent': USER_AGENT}
    url = f"https://oauth.reddit.com{permalink}.json"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return res.json()[1]['data']['children']

def extract_all_comments(comments: List[dict]) -> List[dict]:
    """Flatten all nested comments into a single list"""
    result = []
    for comment in comments:
        if comment["kind"] != "t1":
            continue
        data = comment["data"]
        result.append(data)
        if data.get("replies") and isinstance(data["replies"], dict):
            children = data["replies"]["data"]["children"]
            result.extend(extract_all_comments(children))
    return result

def has_mod_reply(comments: List[dict]) -> (bool, List[str]):
    mod_names = []
    for c in comments:
        author = c.get("author", "").lower()
        if author in MOD_USERNAMES:
            mod_names.append(author)
    return bool(mod_names), mod_names

def send_to_slack(post, mod_replied=False, mod_names=None):
    if mod_names is None:
        mod_names = []
    mod_names = list(set(mod_names))
    logging.info(f"Preparing Slack message for post: {post['id']}, Mod replied: {mod_replied}, Mods: {mod_names}")
    
    post_title = post["title"]
    post_url = f"https://reddit.com{post['permalink']}"
    post_content = post.get("selftext", "")
    post_time = datetime.utcfromtimestamp(post["created_utc"]).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    # Create a Slack message using block kit
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Reddit Post Notification"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<{post_url}|{post_title} >"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*User:* u/{post['author']}\n*Date:* {post_time}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"> ```{post_content}```"
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "> :white_check_mark: *Mod(s) " + ", ".join(mod_names) + " have replied*" if mod_replied else "> :no_entry_sign: *No mod has replied yet*"
                }
            ]
        },
        {
            "type": "divider"
        }
    ]
    
    payload = {"blocks": blocks}
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    logging.info(f"Slack response status: {response.status_code}")

def main():
    logging.info("Initializing database")
    init_db()
    token = get_reddit_token()
    logging.info("Fetched Reddit token")
    posts = fetch_new_posts(token)
    logging.info(f"Loaded mod usernames: {MOD_USERNAMES}")
    logging.info(f"Fetched {len(posts)} new posts")

    for post in posts:
        post_data = post["data"]
        post_id = post_data["id"]
        logging.info(f"Processing post ID: {post_id}")

        permalink = post_data["permalink"]
        comments = fetch_comments(token, permalink)
        flat_comments = extract_all_comments(comments)
        logging.info(f"Extracted {len(flat_comments)} comments for post ID: {post_id}")

        mod_reply_found, mod_names = has_mod_reply(flat_comments)
        logging.info(f"Mod replied: {mod_reply_found}, Mods: {mod_names}")

        if not has_been_alerted(post_id):
            logging.info(f"Sending post ID: {post_id} to Slack")
            send_to_slack(post_data, mod_replied=mod_reply_found, mod_names=mod_names)
            mark_as_alerted(post_id, mod_replied=mod_reply_found)
        elif mod_reply_found and not has_been_alerted(post_id):
            logging.info(f"Sending update for post ID: {post_id} to Slack due to new mod reply")
            send_to_slack(post_data, mod_replied=mod_reply_found, mod_names=mod_names)
            mark_as_alerted(post_id, mod_replied=mod_reply_found)
        else:
            logging.info(f"Post ID: {post_id} has already been alerted and no new mod reply found")

        time.sleep(1)  # to avoid hitting rate limits

if __name__ == "__main__":
    main()
