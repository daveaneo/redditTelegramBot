import praw
import os
import logging
import json
from typing import Any, Dict, List
from modules.social_media_bot import SocialMediaBot


class RedditBot(SocialMediaBot):
    """A Reddit bot that processes report posts, general posts, and subreddit posts and sends significant messages to Telegram."""

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
                            self.process_significant_message(
                                "General post (significant)", user, submission, openai_bot, system_config
                            )
                        else:
                            logging.debug(f"General post {submission.id} from {user} deemed not significant.")
                    else:
                        logging.debug(f"General post {submission.id} already processed. Skipping.")
            except Exception as e:
                logging.error(f"Error processing general post from {user}: {e}")

    def process_other_sources(
            self,
            sources: Dict[str, Any],
            openai_bot: Any,
            cache_manager: Any,
            system_config: Dict[str, Any]
    ) -> None:
        """
        Processes additional sources beyond 'reports' and 'general' users.

        Args:
            sources (Dict[str, Any]): A dictionary containing additional sources (e.g., subreddits).
            openai_bot (Any): Instance of OpenAIBot.
            cache_manager (Any): Instance of CacheManager.
            system_config (Dict[str, Any]): System configuration parameters.
        """
        for subreddit_name in sources.get("subreddits", {}):
            self.check_subreddit_posts(subreddit_name, openai_bot, cache_manager, system_config)

    def check_subreddit_posts(
            self,
            subreddit: str,
            openai_bot: Any,
            cache_manager: Any,
            system_config: Dict[str, Any]
    ) -> None:
        """
        Processes posts from a specific subreddit that contain a target flair (e.g., "DD").
        Filters posts based on author karma and sentiment analysis.

        Args:
            subreddit (str): The subreddit name to scan.
            openai_bot (Any): Instance of OpenAIBot.
            cache_manager (Any): Instance of CacheManager.
            system_config (Dict[str, Any]): System configuration parameters.
        """
        subreddit_config = system_config.get("platforms", {}).get("reddit", {}).get("subreddits", {}).get(subreddit, {})

        target_flair = subreddit_config.get("target_flair", "DD")
        min_karma = subreddit_config.get("min_karma", 1000)
        sentiment_threshold = subreddit_config.get("sentiment_threshold", 50)

        logging.info(f"Checking subreddit: {subreddit} for flair: {target_flair}")

        try:
            query = f"flair:'{target_flair}'"
            submissions = self.client.subreddit(subreddit).search(query, sort="new", time_filter="week", limit=25)

            for submission in submissions:
                if not cache_manager.is_cached(submission.id):
                    if submission.link_flair_text and submission.link_flair_text.lower() == target_flair.lower():
                        author = submission.author
                        if author and author.link_karma >= min_karma:
                            sentiment_analysis = openai_bot.analyze_sentiment(submission.selftext, 100)
                            sentiment_score = self._extract_sentiment_score(sentiment_analysis)

                            if sentiment_score >= sentiment_threshold:
                                cache_manager.add(submission.id)
                                self.process_significant_message(
                                    f"{subreddit} post (Flair: {target_flair})", author.name,
                                    submission, openai_bot, system_config
                                )
                else:
                    logging.debug(f"Subreddit post {submission.id} already processed. Skipping.")

        except Exception as e:
            logging.error(f"Error processing subreddit {subreddit}: {e}")

    def _extract_sentiment_score(self, sentiment_data: str) -> int:
        """
        Extracts the sentiment score from OpenAI's JSON response.

        Args:
            sentiment_data (str): The sentiment response from OpenAI.

        Returns:
            int: The extracted sentiment score, or -1 if parsing fails.
        """

        try:
            sentiment_dict = json.loads(sentiment_data)
            return int(sentiment_dict.get("sentiment", -1))
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logging.error(f"Failed to parse sentiment data: {sentiment_data} | Error: {e}")
            return -1
