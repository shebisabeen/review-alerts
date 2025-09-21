
# Review Alerts

This project is designed to monitor reviews from various platforms such as Reddit, Google Play Store, and Trustpilot. It collects reviews, processes them, and sends alerts to Slack for any significant findings, such as negative reviews or moderator replies.

## Features

- **Reddit Monitoring**: Fetches new posts from a specified subreddit, checks for moderator replies, and sends alerts to Slack.
- **Google Play Store Monitoring**: Retrieves recent reviews for a specified app, processes them, and sends alerts for new reviews to Slack.
- **Trustpilot Monitoring**: Scrapes reviews from Trustpilot for a specified company, processes them, and sends alerts for negative reviews to Slack.
- **Centralized Monitoring**: A main script (`main_monitor.py`) orchestrates the execution of individual monitoring scripts and logs the results.
- **Database Storage**: Uses SQLite databases to store processed reviews and posts to avoid duplicate processing.
- **Environment Configuration**: Utilizes environment variables for configuration, allowing easy customization and deployment.

## Setup

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd review-alerts
   ```

2. **Set Up Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   - Create a `.env` file in the root directory from the `.env.example`.
   - Add necessary environment variables as shown in the example below:

     ```ini
     REDDIT_ALERTS = true
     TRUSTPILOT_ALERTS = true
     PLAYSTORE_ALERTS = true

     # Reddit Configuration
     REDDIT_CLIENT_ID=your_client_id
     REDDIT_CLIENT_SECRET=your_client_secret
     REDDIT_USER=your_username
     REDDIT_PASS=your_password
     REDDIT_USER_AGENT=your_user_agent
     REDDIT_SUBREDDIT=your_subreddit
     REDDIT_MOD_USERNAMES=mod1,mod2
     REDDIT_DATABASE_PATH=reddit_alerts.db
     REDDIT_FETCH_LIMIT=10

     # Google Play Store Configuration
     PLAYSTORE_APP_ID=your_app_id
     PLAYSTORE_DATABASE_PATH=playstore_reviews.db
     PLAYSTORE_HOURS_BACK=6

     # Trustpilot Configuration
     TRUSTPILOT_COMPANY_NAME=your_company_name
     TRUSTPILOT_DATABASE_PATH=trustpilot_reviews.db
     TRUSTPILOT_HOURS_BACK=24
     TRUSTPILOT_RATING_THRESHOLD=3
     TRUSTPILOT_MAX_PAGES=3

     # Slack Configuration
     SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
     ```

5. **Run the Monitors**:
   - Execute the `run_monitors.sh` script to start monitoring:
     ```bash
     ./run_monitors.sh
     ```


---

## Scheduling with Cron

To automate the execution of the monitoring scripts, you can set up a cron job. This will allow the scripts to run at specified intervals without manual intervention.

### Steps to Set Up a Cron Job

1. **Open the Crontab Editor**:
   - Run the following command in your terminal to open the crontab editor:
     ```bash
     crontab -e
     ```

2. **Add a New Cron Job**:
   - Add the following line to schedule the `run_monitors.sh` script. This example schedules the script to run every day at midnight:
     ```bash
     0 0 * * * /bin/bash /path/to/your/project/run_monitors.sh
     ```
   - Replace `/path/to/your/project/` with the actual path to your project directory.

3. **Save and Exit**:
   - Save the changes and exit the editor. The cron job is now set up and will execute the script at the specified time.

### Cron Job Syntax

- The cron job syntax is as follows:
  ```
  * * * * * command_to_execute
  - - - - -
  | | | | |
  | | | | +---- Day of the week (0 - 7) (Sunday is both 0 and 7)
  | | | +------ Month (1 - 12)
  | | +-------- Day of the month (1 - 31)
  | +---------- Hour (0 - 23)
  +------------ Minute (0 - 59)
  ```

- Adjust the timing as needed to fit your monitoring schedule.

### Logging

- Ensure that the `run_monitors.sh` script logs output to a file, such as `cron_monitor.log`, to keep track of the cron job's execution and any potential errors.

---

This section provides clear instructions on how to set up a cron job for the project, including an example and explanation of the cron syntax. Adjust the timing and paths as necessary for your specific use case.

## Logging

- Logs are stored in `cron_monitor.log` and `main_monitor.log` for cron and main monitor activities, respectively.

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.

## License

This project is licensed under the MIT License.

---
