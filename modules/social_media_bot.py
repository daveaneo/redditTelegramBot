from abc import ABC, abstractmethod
import time
import logging
import os
import requests
from typing import Any, Dict, List


class SocialMediaBot(ABC):
    """
    Abstract base class for social media bots that process significant messages and send them to Telegram.

    Provides common functionality such as formatting post times, processing significant messages,
    and sending Telegram messages. Also defines the interface for `check_reports()` and `check_general()`
    which must be implemented by subclasses.
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

        sentiment = openai_bot.analyze_sentiment(
            submission.selftext,
            system_config.get("sentiment_char_limit", 100)
        )
        summary = openai_bot.summarize_text(
            submission.selftext,
            system_config.get("summary_char_limit", 100)
        )
        sentiment_reply = f"Sentiment: {sentiment}"
        summary_reply = f"Summary: {summary}"

        self.send_telegram_message(original_message, sentiment_reply, summary_reply, system_config)

    def send_telegram_message(
            self,
            original_message: str,
            sentiment_reply: str,
            summary_reply: str,
            system_config: Dict[str, Any]
    ) -> None:
        """
        Sends messages to Telegram using settings in system_config.

        Args:
            original_message (str): The original post message.
            sentiment_reply (str): The sentiment analysis reply.
            summary_reply (str): The summary reply.
            system_config (Dict[str, Any]): System configuration including Telegram settings.
        """
        print(original_message)
        print(sentiment_reply)
        print(summary_reply)

        if not system_config.get("telegram_enabled", True):
            logging.info("Telegram notifications are disabled in the system configuration.")
            return

        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        TELEGRAM_CHAT_ID = system_config.get("telegram_chat_id", "")
        send_message_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        payloads = [
            {"chat_id": TELEGRAM_CHAT_ID, "text": original_message},
            {"chat_id": TELEGRAM_CHAT_ID, "text": sentiment_reply},
            {"chat_id": TELEGRAM_CHAT_ID, "text": summary_reply}
        ]

        for payload in payloads:
            try:
                response = requests.post(send_message_url, json=payload)
                if response.status_code != 200:
                    logging.error(f"Telegram API error: {response.status_code} - {response.text}")
                else:
                    logging.info("Telegram message sent successfully.")
            except Exception as e:
                logging.error(f"Error sending Telegram message: {e}")

    @abstractmethod
    def check_reports(
            self,
            reports_list: List[str],
            openai_bot: Any,
            cache_manager: Any,
            system_config: Dict[str, Any]
    ) -> None:
        """
        Processes posts from 'reports' users.

        Must be implemented by subclasses.

        Args:
            reports_list (List[str]): List of report user names.
            openai_bot (Any): Instance of OpenAIBot.
            cache_manager (Any): Instance of CacheManager.
            system_config (Dict[str, Any]): System configuration parameters.
        """
        raise NotImplementedError("Subclasses must implement check_reports()")

    @abstractmethod
    def check_general(
            self,
            general_list: List[str],
            openai_bot: Any,
            cache_manager: Any,
            system_config: Dict[str, Any]
    ) -> None:
        """
        Processes posts from 'general' users.

        Must be implemented by subclasses.

        Args:
            general_list (List[str]): List of general user names.
            openai_bot (Any): Instance of OpenAIBot.
            cache_manager (Any): Instance of CacheManager.
            system_config (Dict[str, Any]): System configuration parameters.
        """
        raise NotImplementedError("Subclasses must implement check_general()")

    def run(
            self,
            reports_list: List[str],
            general_list: List[str],
            openai_bot: Any,
            cache_manager: Any,
            system_config: Dict[str, Any]
    ) -> None:
        """
        Runs both check_reports and check_general, simplifying usage in main.py.

        Args:
            reports_list (List[str]): List of report user names.
            general_list (List[str]): List of general user names.
            openai_bot (Any): Instance of OpenAIBot.
            cache_manager (Any): Instance of CacheManager.
            system_config (Dict[str, Any]): System configuration parameters.
        """
        self.check_reports(reports_list, openai_bot, cache_manager, system_config)
        self.check_general(general_list, openai_bot, cache_manager, system_config)
