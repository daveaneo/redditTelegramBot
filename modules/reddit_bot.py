import praw
import os
import logging
from typing import Any, Dict, List
from modules.social_media_bot import SocialMediaBot


class RedditBot(SocialMediaBot):
    """A Reddit bot that processes report and general posts and sends significant messages to Telegram."""

    def __init__(self) -> None:
        """Initializes the Reddit bot using PRAW with credentials from environment variables."""
        self.client = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT'),
            client_secret=os.getenv('REDDIT_SECRET'),
            username=os.getenv('REDDIT_USERNAME'),
            password=os.getenv('REDDIT_PASSWORD'),
            user_agent=os.getenv('REDDIT_USER_AGENT')
        )
        # Track processed posts to avoid duplicate processing.
        self.processed_posts = set()

    def check_reports(
            self,
            reports_list: List[str],
            openai_bot: Any,
            cache_manager: Any,
            system_config: Dict[str, Any]
    ) -> None:
        """
        Processes posts from 'reports' users.

        Posts are forwarded directly with follow-up analyses.

        Args:
            reports_list (List[str]): List of Reddit usernames for reports.
            openai_bot (Any): Instance of OpenAIBot.
            cache_manager (Any): Instance of CacheManager.
            system_config (Dict[str, Any]): System configuration parameters.
        """
        for user in reports_list:
            try:
                for submission in self.client.redditor(user).submissions.new(limit=1):
                    logging.debug(f"Processing submission: {submission.id}")
                    if not cache_manager.is_cached(submission.id):
                        cache_manager.add(submission.id)
                        self.process_significant_message("Report", user, submission, openai_bot, system_config)
                    else:
                        logging.debug(f"Report post {submission.id} already processed. Skipping.")
            except Exception as e:
                logging.error(f"Error processing report from {user}: {e}")

    def check_general(
            self,
            general_list: List[str],
            openai_bot: Any,
            cache_manager: Any,
            system_config: Dict[str, Any]
    ) -> None:
        """
        Processes posts from 'general' users.

        Posts are analyzed for significance and forwarded if deemed significant.

        Args:
            general_list (List[str]): List of Reddit usernames for general posts.
            openai_bot (Any): Instance of OpenAIBot.
            cache_manager (Any): Instance of CacheManager.
            system_config (Dict[str, Any]): System configuration parameters.
        """
        for user in general_list:
            try:
                for submission in self.client.redditor(user).submissions.new(limit=1):
                    if not cache_manager.is_cached(submission.id):
                        cache_manager.add(submission.id)
                        # Analyze post for significance.
                        significance = openai_bot.review_post(submission.selftext)
                        if "YES" in significance.upper():
                            self.process_significant_message("General post (significant)", user, submission, openai_bot,
                                                             system_config)
                        else:
                            logging.debug(f"General post {submission.id} from {user} deemed not significant.")
                    else:
                        logging.debug(f"General post {submission.id} already processed. Skipping.")
            except Exception as e:
                logging.error(f"Error processing general post from {user}: {e}")
