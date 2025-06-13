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


    def send_heartbeat_message(self, system_config):
        """
        Sends a daily 'Bot is still running' message to a specific Telegram user.

        Args:
            system_config (dict): Configuration settings.
        """
        if not system_config.get("telegram_enabled", True):
            logging.info("Telegram notifications are disabled.")
            return

        print(system_config)

        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        TELEGRAM_CHAT_ID = system_config.get("telegram_heartbeat_recipient", "")

        if not TELEGRAM_CHAT_ID:
            logging.warning("No heartbeat recipient specified in config.")
            return

        send_message_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        # Format timestamp for logging
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())

        # Heartbeat message
        heartbeat_message = f"✅ Bot is still running. Last check-in: {timestamp}"

        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": heartbeat_message}

        try:
            response = requests.post(send_message_url, json=payload)
            if response.status_code != 200:
                logging.error(f"Telegram API error: {response.status_code} - {response.text}")
            else:
                logging.info("✅ Heartbeat message sent successfully.")
        except Exception as e:
            logging.error(f"Error sending heartbeat message: {e}")

    def send_telegram_message(self, original_message, sentiment_data, summary, system_config):
        """
        Sends a single, formatted message to a Telegram chat.

        The message is structured as follows:
        - A line of emojis (🔥 for bullish, ❄️ for bearish) representing the sentiment.
        - Two empty lines for spacing.
        - The original post message.
        - The summary of the post.

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

        if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
            logging.error("Telegram bot token or chat ID is not configured.")
            return

        send_message_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        # --- Process sentiment into the new emoji-only format ---
        sentiment_header = ""
        try:
            if isinstance(sentiment_data, str):
                sentiment_data = json.loads(sentiment_data)

            if isinstance(sentiment_data, dict) and "sentiment" in sentiment_data and "direction" in sentiment_data:
                sentiment_score = int(sentiment_data["sentiment"])
                direction = sentiment_data["direction"].lower()

                # Determine the number of emojis based on the score (1 emoji per 10 points)
                emoji_count = max(1, sentiment_score // 10)

                if direction == "bullish":
                    sentiment_header = "🔥" * emoji_count
                elif direction == "bearish":
                    sentiment_header = "❄️" * emoji_count
                else:
                    sentiment_header = "❓"  # Fallback for unknown direction
            else:
                raise ValueError("Invalid sentiment format")

        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            sentiment_header = "❓"
            logging.error(f"Could not process sentiment data: {sentiment_data} | Error: {e}")

        # --- Combine all parts into a single message ---
        # Format: {Sentiment Emojis}\n\n{Original Post}\n\n{Summary}
        full_message_text = f"{sentiment_header}\n\n{original_message}\n\n{summary}"

        # --- Send the single, combined message ---
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": full_message_text,
            "parse_mode": "Markdown"  # Optional: use 'HTML' or 'Markdown' if your text needs it
        }

        try:
            response = requests.post(send_message_url, json=payload)
            response.raise_for_status()  # This will raise an HTTPError for bad responses (4xx or 5xx)
            logging.info("Telegram message sent successfully.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error sending Telegram message: {e}")
            if e.response:
                logging.error(f"Telegram API error details: {e.response.text}")


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
