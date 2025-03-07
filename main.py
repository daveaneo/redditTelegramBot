import schedule
import time
import json
from modules.reddit_bot import RedditBot
from modules.openai_bot import OpenAIBot
from modules.cache_manager import CacheManager
from dotenv import load_dotenv
import os
import logging

# Set up basic logging with timestamp and log level.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file.
load_dotenv()


def load_config():
    """
    Load configuration settings from config.json.

    Returns:
        dict: The loaded configuration dictionary.
    """
    with open("config.json", "r") as f:
        return json.load(f)


# Initialize our modules.
reddit_bot = RedditBot()
# openai_bot uses a prompt template file; update the path as needed.
openai_bot = OpenAIBot(
    review_prompt_path="modules/prompts/review_post_prompt.txt",
    sentiment_prompt_path="modules/prompts/sentiment_analysis_prompt.txt",
    summarization_prompt_path="modules/prompts/summarization_prompt.txt"
)

config = load_config()  # Load the config from config.json.
system_config = config.get("system", {})
cache_manager = CacheManager(
    cache_file=system_config.get("cache_file", "cache.json"),
    expiration_time=system_config.get("cache_expiration_seconds", 172800)
)


def run_reddit_checks():
    """
    Runs checks for both report and general Reddit users by calling the unified run() method.

    The run() method on reddit_bot internally calls check_reports() and check_general().
    """
    config = load_config()
    reddit_config = config.get("platforms", {}).get("reddit", {})
    system_config = config.get("system", {})

    reports_list = reddit_config.get("reports", [])
    general_list = reddit_config.get("general", [])

    # Use the unified run() method which processes both report and general posts.
    reddit_bot.run(reports_list, general_list, openai_bot, cache_manager, system_config)


def cleanup_cache():
    """
    Runs cache cleanup to remove posts older than the configured expiration time.
    """
    logging.info("Running cache cleanup...")
    cache_manager.cleanup()


# Schedule the checks every minute and cache cleanup every hour.
schedule.every(1).minutes.do(run_reddit_checks)
schedule.every(1).hours.do(cleanup_cache)

logging.info("Bot running... Press Ctrl+C to exit.")
try:
    # Initial run
    run_reddit_checks()
    while True:
        schedule.run_pending()
        time.sleep(1)
except KeyboardInterrupt:
    logging.info("Bot stopped by user.")
