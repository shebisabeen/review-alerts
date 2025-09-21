from google_play_scraper import reviews, Sort
from datetime import datetime, timedelta, timezone
import sqlite3
import os
import time
import requests
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)

@dataclass
class Review:
    review_id: str
    title: str  # Play Store has no titles; we'll keep this as "No title"
    content: str
    rating: int
    date_time: datetime
    reviewer_name: str
    company_replied: bool
    reply_content: Optional[str] = None
    reply_date: Optional[datetime] = None

class PlayStoreMonitor:
    def __init__(self, app_id: str, db_path: str):
        self.app_id = app_id
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_reviews (
                review_id TEXT PRIMARY KEY,
                content TEXT,
                rating INTEGER,
                date_time TEXT,
                reviewer_name TEXT,
                company_replied BOOLEAN,
                reply_content TEXT,
                reply_date TEXT,
                processed_at TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def is_review_processed(self, review_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM processed_reviews WHERE review_id = ?', (review_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def save_review(self, review: Review):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO processed_reviews 
            (review_id, content, rating, date_time, reviewer_name, 
             company_replied, reply_content, reply_date, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            review.review_id,
            review.content,
            review.rating,
            review.date_time.isoformat(),
            review.reviewer_name,
            review.company_replied,
            review.reply_content,
            review.reply_date.isoformat() if review.reply_date else None,
            datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()

    def fetch_reviews(self, hours_back: int = 24):
        logging.info(f"Fetching Play Store reviews for {self.app_id} across mapped countries/languages")

        country_languages_map = {
            'us': ['en'],
            'gb': ['en'],
            'in': ['en', 'hi'],
            'br': ['pt'],
            'de': ['de', 'en'],
            'fr': ['fr', 'en']
        }

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        new_reviews = []

        for country, langs in country_languages_map.items():
            for lang in langs:
                try:
                    logging.info(f"Fetching for {country}-{lang}")
                    result, _ = reviews(
                        self.app_id,
                        lang=lang,
                        country=country,
                        count=50,
                        sort=Sort.NEWEST
                    )
                    for r in result:
                        r_dt = r['at'].replace(tzinfo=timezone.utc)
                        if r_dt < cutoff_time:
                            continue
                        review_id = r['reviewId']
                        if self.is_review_processed(review_id):
                            continue
                        review = Review(
                            review_id=review_id,
                            title="No title",
                            content=r['content'],
                            rating=r['score'],
                            date_time=r_dt,
                            reviewer_name=r['userName'],
                            company_replied=bool(r['replyContent']),
                            reply_content=r['replyContent'],
                            reply_date=r['repliedAt'].replace(tzinfo=timezone.utc) if r['repliedAt'] else None
                        )
                        self.save_review(review)
                        new_reviews.append(review)
                    time.sleep(1)
                except Exception as e:
                    logging.error(f"Failed for {country}-{lang}: {e}")

        logging.info(f"Fetched {len(new_reviews)} new reviews")
        return new_reviews

def send_review_to_slack(review: Review, app_name: str, webhook_url: str):
    if not webhook_url:
        logging.warning("No Slack webhook URL provided.")
        return

    stars = "⭐" * review.rating
    date_str = review.date_time.strftime('%Y-%m-%d %H:%M:%S')
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"📢 Google Play Store - New Review Received"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Rating:*\n{stars} ({review.rating}/5)"},
            {"type": "mrkdwn", "text": f"*Reviewer:*\n{review.reviewer_name}"},
            {"type": "mrkdwn", "text": f"*Date:*\n{date_str}"},
            {"type": "mrkdwn", "text": f"*Replied:*\n{'Yes' if review.company_replied else 'No'}"}
        ]},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Review:*```{review.content[:1000]}```"}}
    ]
    
    if review.company_replied:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":white_check_mark: *Company has replied to this review*"
                }
            ]
        })
    else:
        blocks.append({
            "type": "context", 
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":no_entry_sign: *No company reply yet*"
                }
            ]
        })
    
    blocks.append({"type": "divider"})

    payload = {"blocks": blocks}

    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        logging.info(f"Slack alert sent for review {review.review_id}")
    except Exception as e:
        logging.error(f"Error sending Slack alert: {e}")

# Usage Example
if __name__ == "__main__":
    app_id = os.getenv("PLAYSTORE_APP_ID")
    db_path = os.getenv("PLAYSTORE_DATABASE_PATH")
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    hours_back = int(os.getenv("PLAYSTORE_HOURS_BACK", "6"))
    monitor = PlayStoreMonitor(app_id, db_path)
    reviews = monitor.fetch_reviews(hours_back)
    for r in reviews:
        if r.rating <= 5:
            send_review_to_slack(r, app_name=app_id, webhook_url=slack_webhook_url)