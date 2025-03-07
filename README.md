# Reddit Influencer Bot

This Python bot continuously monitors Reddit for new posts from specified users and influencers. It leverages OpenAI's GPT-4 model to analyze posts and identify significant or market-moving content. Upon detecting significant posts, the bot sends notifications via a configured webhook (e.g., Telegram or Discord).

## Project Structure

```
reddit-influencer-bot/
├── .env
├── config.json
├── main.py
├── social_media_bot.py
└── modules/
    ├── reddit_bot.py
    ├── openai_bot.py
    ├── cache_manager.py
    └── prompts/
        ├── review_post_prompt.txt
        ├── sentiment_analysis_prompt.txt
        └── summarization_prompt.txt
```

## Installation

1. **Clone the repository:**

```bash
git clone https://github.com/yourusername/reddit-influencer-bot.git
```

2. **Navigate to the project directory:**

```bash
cd reddit-influencer-bot
```

3. **Install dependencies:**

```bash
pip install python-dotenv schedule praw openai requests
```

4. **Configure environment variables** (create `.env` file):

```env
# Reddit credentials
REDDIT_CLIENT="your_reddit_client_id"
REDDIT_SECRET="your_reddit_secret"
REDDIT_USERNAME="your_reddit_username"
REDDIT_PASSWORD="your_reddit_password"
REDDIT_USER_AGENT="RedditScraperBot/0.1 by your_username"

# OpenAI API key
OPENAI_API_KEY="your_openai_api_key"

# Telegram credentials
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
```

## Configuration (`config.json`)

Update the `config.json` file with your settings:

```json
{
  "platforms": {
    "reddit": {
      "reports": ["example_user1", "example_user2"],
      "general": ["example_influencer1", "example_influencer2"],
      "subreddits": ["example_subreddit"]
    },
    "twitter": {
      "reports": [],
      "general": []
    }
  },
  "system": {
    "sentiment_char_limit": 100,
    "summary_char_limit": 100,
    "telegram_enabled": true,
    "telegram_chat_id": "your_chat_id"
  }
}
```

## Usage

Run the bot:

```bash
python main.py
```

The bot will run continuously, checking for new posts every minute and cleaning up cached data hourly.

## How It Works

- **Monitoring:**
  - Checks Reddit for new posts from specified users and influencers.
  - Directly forwards "report" posts.
  - Analyzes general posts for market-moving significance using OpenAI GPT.

- **Analysis:**
  - Sentiment analysis (0–100 bullish rating).
  - Summarizes posts succinctly.

- **Notifications:**
  - Sends significant findings via Telegram or other configured webhooks.
  - Logs all activities for troubleshooting and auditing purposes.

## Dependencies

- `python-dotenv`
- `schedule`
- `praw`
- `openai`
- `requests`

## License

MIT License
