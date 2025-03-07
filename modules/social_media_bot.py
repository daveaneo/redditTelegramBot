from abc import ABC, abstractmethod
import time
import logging
import os
import requests
import json
from typing import Any, Dict, List


class SocialMediaBot(ABC):
    """
    Abstract base class for social media bots that process significant messages and send them to Telegram.

    Provides common functionality such as formatting post times, processing significant messages,
    and sending Telegram messages. Defines the interface for `check_reports()`, `check_general()`,
    and `process_other_sources()` which must be implemented by subclasses.
    """

    def _format_post_time(self, submission: Any) -> str:
        """
        Converts a submission's timestamp to a human-readable UTC string.

        Args:
            submission (Any): The submission object from the social platform.

        Returns:
            str: The formatted UTC time.
        """
        return time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(submission.created_utc))

    def process_significant_message(
            self,
            label: str,
            user: str,
            submission: Any,
            openai_bot: Any,
            system_config: Dict[str, Any]
    ) -> None:
        """
        Processes a significant post by performing follow-up analyses and sending messages to Telegram.

        Args:
            label (str): A label for the post (e.g., "Report" or "General post (significant)").
            user (str): The username associated with the post.
            submission (Any): The submission object.
            openai_bot (Any): An instance of OpenAIBot for generating responses.
            system_config (Dict[str, Any]): System configuration parameters.
        """
        post_time = self._format_post_time(submission)
        original_message = f"{label} from {user} at {post_time}:\n{submission.url}"
        logging.info(original_message)

        # Fetch sentiment
        sentiment = openai_bot.analyze_sentiment(
            submission.selftext,
            system_config.get("sentiment_char_limit", 100)
        )

        # Fetch summary
        summary = openai_bot.summarize_text(
            submission.selftext,
            system_config.get("summary_char_limit", 100)
        )

        # Call send_telegram_message with sentiment and summary
        self.send_telegram_message(original_message, sentiment, summary, system_config)


    def send_telegram_message(self, original_message, sentiment_data, summary, system_config):
        """
        Sends messages to Telegram as a threaded conversation.

        - The original post is sent first.
        - The sentiment score is shown with appropriate emojis (🔥 for bullish, ❄️ for bearish).
        - The direction (bullish/bearish) is included.
        - The summary follows below.

        Parameters:
            original_message (str): The initial Reddit post message.
            sentiment_data (str | dict): JSON string or dictionary containing sentiment score & direction.
            summary (str): The summary text.
            system_config (dict): Configuration settings.
        """

        if not system_config.get("telegram_enabled", True):
            logging.info("Telegram notifications are disabled.")
            return

        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        TELEGRAM_CHAT_ID = system_config.get("telegram_chat_id", "")
        send_message_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        # Send the original post message
        original_payload = {"chat_id": TELEGRAM_CHAT_ID, "text": original_message}
        response = requests.post(send_message_url, json=original_payload)

        if response.status_code != 200:
            logging.error(f"Telegram API error: {response.status_code} - {response.text}")
            return

        # Get the message_id of the original post for threading replies
        message_data = response.json()
        message_id = message_data.get("result", {}).get("message_id")

        if not message_id:
            logging.error("Failed to retrieve message_id for threading replies.")
            return

        # Convert sentiment score to appropriate emojis
        try:
            if isinstance(sentiment_data, str):
                sentiment_data = json.loads(sentiment_data)  # Convert string to dictionary

            if isinstance(sentiment_data, dict) and "sentiment" in sentiment_data and "direction" in sentiment_data:
                sentiment_score = int(sentiment_data["sentiment"])
                direction = sentiment_data["direction"].lower()

                if direction == "bullish":
                    sentiment_emoji = "🔥" * (sentiment_score // 10)
                elif direction == "bearish":
                    sentiment_emoji = "❄️" * (sentiment_score // 10)
                else:
                    sentiment_emoji = "❓"

                sentiment_reply = f"{sentiment_emoji} ({sentiment_score}/100) - {direction.capitalize()}"
            else:
                raise ValueError("Invalid sentiment format")

        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            sentiment_reply = "❓ (Error processing sentiment)"
            logging.error(f"Invalid sentiment data received: {sentiment_data} | Error: {e}")

        # Combined reply message
        combined_reply = f"{sentiment_reply}\n\n{summary}"

        # Send reply
        reply_payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": combined_reply,
            "reply_to_message_id": message_id
        }

        try:
            response = requests.post(send_message_url, json=reply_payload)
            if response.status_code != 200:
                logging.error(f"Telegram API error: {response.status_code} - {response.text}")
            else:
                logging.info("Telegram reply sent successfully.")
        except Exception as e:
            logging.error(f"Error sending Telegram reply: {e}")

    @abstractmethod
    def check_reports(self, reports_list: List[str], openai_bot: Any, cache_manager: Any, system_config: Dict[str, Any]) -> None:
        """Processes posts from 'reports' users."""
        raise NotImplementedError("Subclasses must implement check_reports()")

    @abstractmethod
    def check_general(self, general_list: List[str], openai_bot: Any, cache_manager: Any, system_config: Dict[str, Any]) -> None:
        """Processes posts from 'general' users."""
        raise NotImplementedError("Subclasses must implement check_general()")

    @abstractmethod
    def process_other_sources(self, sources: Dict[str, Any], openai_bot: Any, cache_manager: Any, system_config: Dict[str, Any]) -> None:
        """
        Processes additional sources not covered by reports or general categories.

        Args:
            sources (Dict[str, Any]): A dictionary of additional sources (e.g., subreddits for Reddit).
            openai_bot (Any): Instance of OpenAIBot.
            cache_manager (Any): Instance of CacheManager.
            system_config (Dict[str, Any]): System configuration parameters.
        """

    def run(self, sources: Dict[str, Any], openai_bot: Any, cache_manager: Any, system_config: Dict[str, Any]) -> None:
        """
        Runs checks for reports, general posts, and additional sources.

        Args:
            sources (Dict[str, Any]): Dictionary containing 'reports', 'general', and other source types.
            openai_bot (Any): Instance of OpenAIBot.
            cache_manager (Any): Instance of CacheManager.
            system_config (Dict[str, Any]): System configuration parameters.
        """
        logging.info(f"Running checks for some platform")
        reports_list = sources.get("reports", [])
        general_list = sources.get("general", [])
        other_sources = {k: v for k, v in sources.items() if k not in ["reports", "general"]}

        self.check_reports(reports_list, openai_bot, cache_manager, system_config)
        self.check_general(general_list, openai_bot, cache_manager, system_config)
        self.process_other_sources(other_sources, openai_bot, cache_manager, system_config)

        logging.info(f"Checks finished for that platform")
