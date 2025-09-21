import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import re
import sqlite3
from dataclasses import dataclass
from typing import List, Optional
import json
import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class Review:
    review_id: str
    title: str
    content: str
    rating: int
    date_time: datetime
    reviewer_name: str
    company_replied: bool
    reply_content: Optional[str] = None
    reply_date: Optional[datetime] = None

class TrustpilotScraper:
    def __init__(self, company_name: str, db_path: str = "reviews.db"):
        self.company_name = company_name
        self.base_url = f"https://www.trustpilot.com/review/{company_name}"
        self.db_path = db_path
        self.session = requests.Session()
        
        # Set headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database to store processed reviews"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_reviews (
                review_id TEXT PRIMARY KEY,
                title TEXT,
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
        """Check if a review has already been processed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM processed_reviews WHERE review_id = ?', (review_id,))
        result = cursor.fetchone()
        
        conn.close()
        return result is not None
    
    def save_review(self, review: Review):
        """Save a processed review to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO processed_reviews 
            (review_id, title, content, rating, date_time, reviewer_name, 
             company_replied, reply_content, reply_date, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            review.review_id,
            review.title,
            review.content,
            review.rating,
            review.date_time.isoformat(),
            review.reviewer_name,
            review.company_replied,
            review.reply_content,
            review.reply_date.isoformat() if review.reply_date else None,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def is_valid_review(self, review: Review) -> bool:
        """Check if a review has valid content and should be processed"""
        # Define invalid patterns
        invalid_titles = [
            "no title", 
            "", 
            "...", 
            "null", 
            "undefined", 
            "n/a",
            "not available"
        ]
        
        invalid_content_patterns = [
            "",  # Empty content
            "...",  # Just dots
            ".",  # Single dot
            "no content",
            "null",
            "undefined",
            "n/a",
            "not available"
        ]
        
        # Check title validity
        title_lower = review.title.lower().strip()
        if title_lower in invalid_titles:
            print(f"Skipping review with invalid title: '{review.title}'")
            return False
        
        # Check content validity
        content_lower = review.content.lower().strip()
        if content_lower in invalid_content_patterns:
            print(f"Skipping review with invalid content: '{review.content}'")
            return False
        
        # Check if content is just dots or very short
        if len(review.content.strip()) < 5:
            print(f"Skipping review with too short content: '{review.content}'")
            return False
        
        # Check if content is just dots or ellipsis
        if re.match(r'^\.{3,}$', review.content.strip()):
            print(f"Skipping review with only dots: '{review.content}'")
            return False
        
        # Check if reviewer name is valid
        if not review.reviewer_name or review.reviewer_name.lower() in ["anonymous", "", "null", "undefined"]:
            print(f"Skipping review with invalid reviewer name: '{review.reviewer_name}'")
            return False
        
        # Check if rating is valid (1-5)
        if review.rating < 1 or review.rating > 5:
            print(f"Skipping review with invalid rating: {review.rating}")
            return False
        
        return True
    
    def parse_date(self, date_text: str) -> Optional[datetime]:
        """Parse various date formats from Trustpilot"""
        try:
            # Remove extra whitespace
            date_text = date_text.strip()
            
            # Handle relative dates like "1 hour ago", "2 days ago"
            if "ago" in date_text.lower():
                if "hour" in date_text.lower():
                    hours_match = re.search(r'(\d+)', date_text)
                    if hours_match:
                        hours = int(hours_match.group(1))
                        return datetime.now() - timedelta(hours=hours)
                elif "day" in date_text.lower():
                    days_match = re.search(r'(\d+)', date_text)
                    if days_match:
                        days = int(days_match.group(1))
                        return datetime.now() - timedelta(days=days)
                elif "minute" in date_text.lower():
                    minutes_match = re.search(r'(\d+)', date_text)
                    if minutes_match:
                        minutes = int(minutes_match.group(1))
                        return datetime.now() - timedelta(minutes=minutes)
                elif "week" in date_text.lower():
                    weeks_match = re.search(r'(\d+)', date_text)
                    if weeks_match:
                        weeks = int(weeks_match.group(1))
                        return datetime.now() - timedelta(weeks=weeks)
            
            # Handle absolute dates (format may vary by region)
            # Try different date formats
            date_formats = [
                "%b %d, %Y",  # Jan 15, 2024
                "%B %d, %Y",  # January 15, 2024
                "%d %b %Y",   # 15 Jan 2024
                "%d %B %Y",   # 15 January 2024
                "%Y-%m-%d",   # 2024-01-15
                "%m/%d/%Y",   # 01/15/2024
                "%d/%m/%Y",   # 15/01/2024
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_text, fmt)
                except ValueError:
                    continue
                    
        except Exception as e:
            print(f"Error parsing date '{date_text}': {e}")
        
        return None
    
    def extract_review_data(self, review_element) -> Optional[Review]:
        """Extract review data from a review element"""
        try:
            # Extract review ID from href or generate one based on content
            review_link = review_element.find('a', attrs={'data-review-title-typography': True})
            review_id = None
            if review_link:
                href = review_link.get('href', '')
                # Extract ID from URL like "/reviews/680e0d032794400de8b82c66"
                id_match = re.search(r'/reviews/([a-f0-9]+)', href)
                if id_match:
                    review_id = id_match.group(1)
            
            # Fallback to generating ID from content
            if not review_id:
                review_id = str(abs(hash(str(review_element)[:200])))
            
            # Extract title using multiple selectors
            title = "No title"
            title_selectors = [
                'h2[data-service-review-title-typography="true"]',
                'a[data-review-title-typography="true"]',
                'h2[data-review-title-typography="true"]',
                '.typography_heading-xs__jSwUz',
                'a.title',
                'h2'
            ]
            
            for selector in title_selectors:
                title_element = review_element.select_one(selector)
                if title_element:
                    title_text = title_element.get_text(strip=True)
                    if title_text and title_text.lower() not in ["no title", "", "..."]:
                        title = title_text
                        break
            
            # Extract content using multiple selectors
            content = ""
            content_selectors = [
                'p[data-service-review-text-typography="true"]',
                'p[data-review-text-typography="true"]',
                '.typography_body-l__KUYFJ',
                '.review-content',
                'p'
            ]
            
            for selector in content_selectors:
                content_element = review_element.select_one(selector)
                if content_element:
                    content_text = content_element.get_text(strip=True)
                    if content_text and content_text not in ["", "...", ".", "null"]:
                        content = content_text
                        break
            
            # Extract rating from img alt attribute
            rating = 0
            rating_selectors = [
                'img.CDS_StarRating_starRating__614d2e',
                'img[alt*="Rated"]',
                'img[alt*="star"]',
                '.star-rating img'
            ]
            
            for selector in rating_selectors:
                rating_element = review_element.select_one(selector)
                if rating_element:
                    alt_text = rating_element.get('alt', '')
                    # Extract from "Rated 5 out of 5 stars"
                    rating_match = re.search(r'Rated (\d) out of \d stars', alt_text)
                    if rating_match:
                        rating = int(rating_match.group(1))
                        break
            
            # Extract date from time element
            date_time = None
            date_selectors = [
                'time[data-service-review-date-time-ago="true"]',
                'time[data-review-date-time-ago="true"]',
                'time',
                '.date'
            ]
            
            for selector in date_selectors:
                date_element = review_element.select_one(selector)
                if date_element:
                    # First try datetime attribute
                    datetime_attr = date_element.get('datetime')
                    if datetime_attr:
                        try:
                            # Parse ISO format: "2025-04-27T12:54:59.000Z"
                            date_time = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00')).replace(tzinfo=None)
                            break
                        except:
                            pass
                    
                    # Fallback to text content
                    date_text = date_element.get_text(strip=True)
                    if date_text:
                        date_time = self.parse_date(date_text)
                        if date_time:
                            break
            
            if not date_time:
                date_time = datetime.now()  # Fallback to current time
            
            # Extract reviewer name
            reviewer_name = "Anonymous"
            reviewer_selectors = [
                'span[data-consumer-name-typography="true"]',
                'span[data-reviewer-name-typography="true"]',
                '.consumer-name',
                '.reviewer-name',
                'span.name'
            ]
            
            for selector in reviewer_selectors:
                reviewer_element = review_element.select_one(selector)
                if reviewer_element:
                    reviewer_text = reviewer_element.get_text(strip=True)
                    if reviewer_text and reviewer_text.lower() not in ["anonymous", "", "null"]:
                        reviewer_name = reviewer_text
                        break
            
            # Check if company replied - look for company reply section
            reply_wrapper = review_element.find('div', class_='styles_wrapper__WD_1K')
            company_replied = False
            reply_content = None
            reply_date = None
            
            if reply_wrapper:
                # Found a company reply section
                company_replied = True
                
                # Extract reply content
                reply_text_element = reply_wrapper.find('p', attrs={'data-service-review-business-reply-text-typography': True})
                if reply_text_element:
                    reply_content = reply_text_element.get_text(strip=True)
                
                # Extract reply date
                reply_date_element = reply_wrapper.find('time', attrs={'data-service-review-business-reply-date-time-ago': True})
                if reply_date_element:
                    reply_datetime_attr = reply_date_element.get('datetime')
                    if reply_datetime_attr:
                        try:
                            reply_date = datetime.fromisoformat(reply_datetime_attr.replace('Z', '+00:00')).replace(tzinfo=None)
                        except:
                            reply_date_text = reply_date_element.get_text(strip=True)
                            reply_date = self.parse_date(reply_date_text)
            
            review = Review(
                review_id=review_id,
                title=title,
                content=content,
                rating=rating,
                date_time=date_time,
                reviewer_name=reviewer_name,
                company_replied=company_replied,
                reply_content=reply_content,
                reply_date=reply_date
            )
            
            # Validate the review before returning
            if not self.is_valid_review(review):
                return None
            
            return review
            
        except Exception as e:
            print(f"Error extracting review data: {e}")
            return None
    
    def scrape_reviews(self, max_pages: int = 3) -> List[Review]:
        """Scrape reviews from Trustpilot"""
        all_reviews = []
        
        for page in range(1, max_pages + 1):
            try:
                url = f"{self.base_url}?page={page}"
                print(f"Scraping page {page}: {url}")
                
                response = self.session.get(url)
                
                # Handle 404 gracefully
                if response.status_code == 404:
                    print(f"Page {page} not found (404). Stopping pagination.")
                    break
                
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find review containers using the exact structure from the HTML
                review_containers = soup.find_all('article', attrs={'data-service-review-card-paper': True}) or \
                                  soup.find_all('div', class_='styles_cardWrapper__g8amG') or \
                                  soup.find_all('article', class_=re.compile(r'styles_reviewCard'))
                
                if not review_containers:
                    print(f"No review containers found on page {page}")
                    break
                
                page_reviews = []
                skipped_count = 0
                for container in review_containers:
                    review = self.extract_review_data(container)
                    if review:
                        page_reviews.append(review)
                    else:
                        skipped_count += 1
                
                print(f"Found {len(page_reviews)} valid reviews on page {page} (skipped {skipped_count})")
                all_reviews.extend(page_reviews)
                
                # Add delay between requests
                time.sleep(2)
                
            except requests.RequestException as e:
                print(f"Error fetching page {page}: {e}")
                break
            except Exception as e:
                print(f"Error processing page {page}: {e}")
                continue
        
        return all_reviews
    
    def get_new_reviews(self, hours_back: int = 1) -> List[Review]:
        """Get new reviews from the last N hours that haven't been processed"""
        all_reviews = self.scrape_reviews()
        new_reviews = []
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        for review in all_reviews:
            # Check if review is within time range and not already processed
            if (review.date_time >= cutoff_time and 
                not self.is_review_processed(review.review_id)):
                new_reviews.append(review)
                self.save_review(review)  # Save to avoid reprocessing
        
        return new_reviews
    
    def get_negative_reviews(self, hours_back: int = 1, rating_threshold: int = 3) -> List[Review]:
        """Get negative reviews from the last N hours"""
        new_reviews = self.get_new_reviews(hours_back)
        negative_reviews = [r for r in new_reviews if r.rating <= rating_threshold]
        return negative_reviews
    
    def analyze_reviews(self, hours_back: int = 1, rating_threshold: int = 3) -> dict:
        """Analyze reviews and return both total new reviews and negative reviews"""
        print(f"Analyzing reviews from the past {hours_back} hour(s)...")
        
        # Get all new reviews first
        new_reviews = self.get_new_reviews(hours_back)
        
        # Filter negative reviews from the new reviews
        negative_reviews = [r for r in new_reviews if r.rating <= rating_threshold]
        
        return {
            'all_new_reviews': new_reviews,
            'negative_reviews': negative_reviews,
            'total_new_count': len(new_reviews),
            'negative_count': len(negative_reviews)
        }

def get_env_config():
    """Get configuration from environment variables with validation"""
    # Get company name
    company_name = os.getenv('TRUSTPILOT_COMPANY_NAME', '').strip()
    if not company_name:
        raise ValueError("TRUSTPILOT_COMPANY_NAME environment variable is required")
    
    # Get hours back (default to 1 if not set)
    try:
        hours_back = int(os.getenv('TRUSTPILOT_HOURS_BACK', '1'))
        if hours_back <= 0:
            raise ValueError("HOURS_BACK must be a positive integer")
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError("HOURS_BACK must be a valid integer")
        raise e
    
    # Get rating threshold (default to 3 if not set)
    try:
        rating_threshold = int(os.getenv('TRUSTPILOT_RATING_THRESHOLD', '3'))
        if rating_threshold < 1 or rating_threshold > 5:
            raise ValueError("RATING_THRESHOLD must be between 1 and 5")
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError("RATING_THRESHOLD must be a valid integer")
        raise e
    
    # Optional: Database path
    db_path = os.getenv('TRUSTPILOT_DATABASE_PATH', 'reviews.db')
    
    # Optional: Max pages to scrape
    try:
        max_pages = int(os.getenv('TRUSTPILOT_MAX_PAGES', '3'))
        if max_pages <= 0:
            raise ValueError("MAX_PAGES must be a positive integer")
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError("MAX_PAGES must be a valid integer")
        raise e
    
    # Optional: Additional check hours (for showing a different time period)
    try:
        additional_check_hours = int(os.getenv('TRUSTPILOT_ADDITIONAL_CHECK_HOURS', '0'))
        if additional_check_hours < 0:
            raise ValueError("ADDITIONAL_CHECK_HOURS must be a non-negative integer")
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError("ADDITIONAL_CHECK_HOURS must be a valid integer")
        raise e
    
    # Slack webhook URL
    slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL', '').strip()
    
    return {
        'company_name': company_name,
        'hours_back': hours_back,
        'rating_threshold': rating_threshold,
        'db_path': db_path,
        'max_pages': max_pages,
        'additional_check_hours': additional_check_hours,
        'slack_webhook_url': slack_webhook_url
    }

def get_star_emoji(rating: int) -> str:
    """Get star emoji representation for rating"""
    star_map = {
        1: "⭐",
        2: "⭐⭐", 
        3: "⭐⭐⭐",
        4: "⭐⭐⭐⭐",
        5: "⭐⭐⭐⭐⭐"
    }
    return star_map.get(rating, f"{rating} stars")

def get_rating_color(rating: int) -> str:
    """Get color for rating (for Slack message styling)"""
    if rating <= 2:
        return "danger"  # Red
    elif rating == 3:
        return "warning"  # Yellow
    else:
        return "good"  # Green

def send_review_to_slack(review: Review, company_name: str, slack_webhook_url: str):
    """Send individual review notification to Slack"""
    if not slack_webhook_url:
        logging.warning("No Slack webhook URL provided, skipping Slack notification")
        return
    
    logging.info(f"Preparing Slack message for review: {review.review_id}, Rating: {review.rating}, Company replied: {review.company_replied}")
    
    # Construct Trustpilot URL
    review_url = f"https://www.trustpilot.com/review/{company_name}"
    
    # Format review time
    review_time = review.date_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # Truncate content if too long for Slack
    max_content_length = 1000
    truncated_content = review.content[:max_content_length]
    if len(review.content) > max_content_length:
        truncated_content += "... (truncated)"
    
    # Create star rating display
    star_display = get_star_emoji(review.rating)
    
    # Determine if this is a negative review
    is_negative = review.rating <= 3
    
    # Create blocks for Slack message
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚨 {'Negative ' if is_negative else ''}Trustpilot Review Alert"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{review.title}*\n<{review_url}|View on Trustpilot>"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Rating:*\n{star_display} ({review.rating}/5)"
                },
                {
                    "type": "mrkdwn", 
                    "text": f"*Reviewer:*\n{review.reviewer_name}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Date:*\n{review_time}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Review ID:*\n{review.review_id}"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Review Content:*\n```{truncated_content}```"
            }
        }
    ]
    
    # Add company reply information if available
    if review.company_replied:
        reply_time = review.reply_date.strftime('%Y-%m-%d %H:%M:%S') if review.reply_date else "Unknown"
        reply_content = review.reply_content[:500] if review.reply_content else "No content"
        if review.reply_content and len(review.reply_content) > 500:
            reply_content += "... (truncated)"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Company Reply ({reply_time}):*\n```{reply_content}```"
            }
        })
        
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
    
    # Create payload with color coding
    payload = {
        "blocks": blocks,
        "attachments": [
            {
                "color": get_rating_color(review.rating),
                "blocks": []
            }
        ]
    }
    
    try:
        response = requests.post(slack_webhook_url, json=payload)
        response.raise_for_status()
        logging.info(f"Slack notification sent successfully for review {review.review_id}. Status: {response.status_code}")
    except requests.RequestException as e:
        logging.error(f"Failed to send Slack notification for review {review.review_id}: {e}")

def send_summary_to_slack(analysis: dict, company_name: str, hours_back: int, rating_threshold: int, slack_webhook_url: str):
    """Send summary notification to Slack"""
    if not slack_webhook_url:
        logging.warning("No Slack webhook URL provided, skipping Slack summary")
        return
        
    logging.info(f"Preparing Slack summary message: {analysis['total_new_count']} total, {analysis['negative_count']} negative")
    
    # Create rating breakdown
    rating_counts = {}
    for review in analysis['all_new_reviews']:
        rating_counts[review.rating] = rating_counts.get(review.rating, 0) + 1
    
    rating_breakdown = []
    for rating in sorted(rating_counts.keys(), reverse=True):
        count = rating_counts[rating]
        stars = get_star_emoji(rating)
        rating_breakdown.append(f"{stars}: {count} review{'s' if count != 1 else ''}")
    
    rating_text = "\n".join(rating_breakdown) if rating_breakdown else "No new reviews"
    
    # Determine message tone
    if analysis['negative_count'] > 0:
        header_text = f"🚨 Trustpilot Alert: {analysis['negative_count']} Negative Review{'s' if analysis['negative_count'] != 1 else ''} Found"
        summary_color = "danger"
    # else:
    #     header_text = f"✅ Trustpilot Summary: No Negative Reviews"
    #     summary_color = "good"
    
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Company:*\n{company_name.title()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Time Period:*\n{hours_back} hour{'s' if hours_back != 1 else ''}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Reviews:*\n{analysis['total_new_count']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Negative Reviews:*\n{analysis['negative_count']} (≤{rating_threshold} stars)"
                    }
                ]
            }
        ]
        
        if rating_breakdown:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Rating Breakdown:*\n{rating_text}"
                }
            })
        
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ]
        })
        
        payload = {
            "blocks": blocks,
            "attachments": [
                {
                    "color": summary_color,
                    "blocks": []
                }
            ]
        }
        
        try:
            response = requests.post(slack_webhook_url, json=payload)
            response.raise_for_status()
            logging.info(f"Slack summary sent successfully. Status: {response.status_code}")
        except requests.RequestException as e:
            logging.error(f"Failed to send Slack summary: {e}")

def main():
    try:
        # Get configuration from environment variables
        config = get_env_config()
        
        print(f"=== TRUSTPILOT REVIEW MONITOR ===")
        print(f"Company: {config['company_name']}")
        print(f"Time period: Past {config['hours_back']} hour(s)")
        print(f"Negative rating threshold: <= {config['rating_threshold']}")
        print(f"Database: {config['db_path']}")
        print(f"Max pages to scrape: {config['max_pages']}")
        print(f"Slack notifications: {'Enabled' if config['slack_webhook_url'] else 'Disabled'}")
        if config['additional_check_hours'] > 0:
            print(f"Additional check period: Past {config['additional_check_hours']} hour(s)")
        print("=" * 40)
        
        # Initialize scraper
        scraper = TrustpilotScraper(config['company_name'], config['db_path'])
        
        # Analyze reviews
        analysis = scraper.analyze_reviews(
            hours_back=config['hours_back'], 
            rating_threshold=config['rating_threshold']
        )
        
        print(f"\n=== ANALYSIS RESULTS ===")
        print(f"Time period: Past {config['hours_back']} hour(s)")
        print(f"Total new reviews: {analysis['total_new_count']}")
        print(f"Negative reviews (rating <= {config['rating_threshold']}): {analysis['negative_count']}")
        
        # Send individual review notifications to Slack for negative reviews
        if analysis['negative_reviews'] and config['slack_webhook_url']:
            print(f"\n📤 Sending {len(analysis['negative_reviews'])} negative review notification(s) to Slack...")
            for review in analysis['negative_reviews']:
                send_review_to_slack(review, config['company_name'], config['slack_webhook_url'])
                time.sleep(1)  # Small delay between messages
        
        if analysis['negative_reviews']:
            print(f"\n🚨 NEGATIVE REVIEWS FOUND 🚨")
            for i, review in enumerate(analysis['negative_reviews'], 1):
                print(f"\n--- Negative Review #{i} (ID: {review.review_id}) ---")
                print(f"Rating: {review.rating}/5")
                print(f"Title: {review.title}")
                print(f"Content: {review.content[:200]}...")
                print(f"Reviewer: {review.reviewer_name}")
                print(f"Date: {review.date_time}")
                print(f"Company Replied: {review.company_replied}")
                if review.company_replied and review.reply_content:
                    print(f"Reply Date: {review.reply_date}")
                    print(f"Reply: {review.reply_content[:100]}...")
        else:
            print(f"\n✅ No new negative reviews found in the past {config['hours_back']} hour(s).")
        
        # Send summary to Slack
        if config['slack_webhook_url']:
            print(f"\n📤 Sending summary to Slack...")
            send_summary_to_slack(
                analysis, 
                config['company_name'], 
                config['hours_back'], 
                5, 
                config['slack_webhook_url']
            )
            # send_summary_to_slack(
            #     analysis, 
            #     config['company_name'], 
            #     config['hours_back'], 
            #     config['rating_threshold'], 
            #     config['slack_webhook_url']
            # )
        
        # Show summary of all new reviews by rating
        if analysis['all_new_reviews']:
            rating_counts = {}
            for review in analysis['all_new_reviews']:
                rating_counts[review.rating] = rating_counts.get(review.rating, 0) + 1
            
            print(f"\n=== NEW REVIEWS BREAKDOWN ===")
            for rating in sorted(rating_counts.keys(), reverse=True):
                count = rating_counts[rating]
                stars = "⭐" * rating
                print(f"{stars} {rating}/5 stars: {count} review(s)")
        
        # Show additional time period analysis if configured
        if config['additional_check_hours'] > 0 and config['additional_check_hours'] != config['hours_back']:
            print(f"\n=== ADDITIONAL CHECK: PAST {config['additional_check_hours']} HOUR(S) ===")
            additional_analysis = scraper.analyze_reviews(
                hours_back=config['additional_check_hours'], 
                rating_threshold=config['rating_threshold']
            )
            print(f"Reviews in past {config['additional_check_hours']} hour(s): {additional_analysis['total_new_count']}")
            print(f"Negative reviews in past {config['additional_check_hours']} hour(s): {additional_analysis['negative_count']}")
            
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("\nRequired environment variables:")
        print("- TRUSTPILOT_COMPANY_NAME: The company name from Trustpilot URL")
        print("\nOptional environment variables:")
        print("- HOURS_BACK: Hours to look back (default: 1)")
        print("- RATING_THRESHOLD: Rating threshold for negative reviews (default: 3)")
        print("- DATABASE_PATH: Path to SQLite database (default: reviews.db)")
        print("- MAX_PAGES: Maximum pages to scrape (default: 3)")
        print("- ADDITIONAL_CHECK_HOURS: Additional time period to check (default: 0 = disabled)")
        print("- SLACK_WEBHOOK_URL: Slack webhook URL for notifications (optional)")
        print("\nExample .env file:")
        print("TRUSTPILOT_COMPANY_NAME=voicenotes.com")
        print("HOURS_BACK=24")
        print("RATING_THRESHOLD=3")
        print("DATABASE_PATH=trustpilot_reviews.db")
        print("MAX_PAGES=5")
        print("ADDITIONAL_CHECK_HOURS=1")
        print("SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL")
        return 1
        
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())