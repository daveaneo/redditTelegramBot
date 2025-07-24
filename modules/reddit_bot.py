# FILE: reddit_bot.py

import praw
import prawcore # IMPORT THIS
import os
import logging
import json
import time
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
            config: Dict[str, Any]
    ) -> None:
        """
        Processes posts from 'reports' users within the last week.

        Args:
            reports_list (List[str]): List of Reddit usernames for reports.
            openai_bot (Any): Instance of OpenAIBot.
            cache_manager (Any): Instance of CacheManager.
            config (Dict[str, Any]): System configuration parameters.
        """
        # Extract system_config from the full config object

        print("\nCONFIG---------")
        print(config)

        system_config = config.get("system", {})
        one_week_ago = int(time.time()) - (7 * 24 * 60 * 60)

        for user in reports_list:
            try:
                for submission in self.client.redditor(user).submissions.new(limit=25):
                    if submission.created_utc >= one_week_ago:
                        if not cache_manager.is_cached(submission.id):
                            cache_manager.add(submission.id)
                            social_score = f'{submission.author.link_karma:,} karma'
                            self.process_significant_message("Reddit: report", user, submission, openai_bot, system_config, social_score)
                        else:
                            logging.debug(f"Report post {submission.id} already processed. Skipping.")
            except prawcore.exceptions.NotFound:
                logging.warning(f"Reddit user '{user}' not found. Skipping.")
            except Exception as e:
                logging.error(f"Error processing report from {user}: {e}")

    def check_general(
            self,
            general_list: List[str],
            openai_bot: Any,
            cache_manager: Any,
            config: Dict[str, Any]
    ) -> None:
        """Processes posts from 'general' users."""
        # Extract system_config from the full config object
        system_config = config.get("system", {})
        one_week_ago = int(time.time()) - (7 * 24 * 60 * 60)

        for user in general_list:
            try:
                for submission in self.client.redditor(user).submissions.new(limit=25):
                    if submission.created_utc >= one_week_ago:
                        if not cache_manager.is_cached(submission.id):
                            cache_manager.add(submission.id)
                            significance_json = openai_bot.review_post(submission.selftext)
                            try:
                                significance_data = json.loads(significance_json)
                                is_significant = significance_data.get("is_significant", False)
                            except (json.JSONDecodeError, TypeError):
                                is_significant = False
                                logging.error(f"Could not parse significance JSON: {significance_json}")

                            social_score = f'{submission.author.link_karma:,} karma'

                            if is_significant:
                                self.process_significant_message(
                                    "Reddit: general", user, submission, openai_bot, system_config, social_score
                                )
                            else:
                                logging.debug(f"General post {submission.id} from {user} deemed not significant.")
                        else:
                            logging.debug(f"General post {submission.id} already processed. Skipping.")
            except prawcore.exceptions.NotFound:
                logging.warning(f"Reddit user '{user}' not found. Skipping.")
            except Exception as e:
                logging.error(f"Error processing general post from {user}: {e}")

    def process_other_sources(
            self,
            sources: Dict[str, Any],
            openai_bot: Any,
            cache_manager: Any,
            # CHANGE THIS: from system_config to config
            config: Dict[str, Any]
    ) -> None:
        """
        Processes additional sources...
        """
        for subreddit_name in sources.get("subreddits", {}):
            # Pass the full config object down
            self.check_subreddit_posts(subreddit_name, openai_bot, cache_manager, config)

    def check_subreddit_posts(
            self,
            subreddit: str,
            openai_bot: Any,
            cache_manager: Any,
            # CHANGE THIS: from system_config to config
            config: Dict[str, Any]
    ) -> None:
        """
        Processes posts from a specific subreddit...
        """
        # CORRECTED: Get the system config from the full config object
        system_config = config.get("system", {})

        # CORRECTED: Get the subreddit config from the full config object
        subreddit_config = config.get("platforms", {}).get("reddit", {}).get("subreddits", {}).get(subreddit, {})

        # Now these lines will correctly load your values (2000 and 50)
        target_flair = subreddit_config.get("target_flair", "DD")
        min_karma = subreddit_config.get("min_karma", 1000)
        sentiment_threshold = subreddit_config.get("sentiment_threshold", 50)

        logging.info(f"Checking subreddit: {subreddit} for flair: '{target_flair}' with min_karma: {min_karma}")

        try:
            query = f"flair:'{target_flair}'"
            submissions = self.client.subreddit(subreddit).search(query, sort="new", time_filter="week", limit=25)

            for submission in submissions:
                if not cache_manager.is_cached(submission.id):
                    # (The rest of the logic is correct)
                    if submission.link_flair_text and submission.link_flair_text.lower() == target_flair.lower():
                        author = submission.author
                        if author and author.link_karma >= min_karma:  # This check will now use 2000
                            sentiment_analysis = openai_bot.analyze_sentiment(submission.selftext, 100)
                            sentiment_score = self._extract_sentiment_score(sentiment_analysis)

                            social_score = f'{author.link_karma:,} karma'

                            if sentiment_score >= sentiment_threshold:
                                cache_manager.add(submission.id)
                                self.process_significant_message(
                                    f"Reddit: {subreddit}", author.name,
                                    submission, openai_bot, system_config, social_score
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