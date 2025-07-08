from abc import ABC, abstractmethod
import time
import logging
import os
import requests
import json
from typing import Any, Dict, List, Optional


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
            system_config: Dict[str, Any],
            social_score: Optional[str] = None
    ) -> None:
        """
        Processes a significant post and sends a neatly formatted message to Telegram.

        Args:
            label (str): A label for the post (e.g., "Report").
            user (str): The username associated with the post.
            submission (Any): The submission object from the source platform.
            openai_bot (Any): An instance of OpenAIBot for generating responses.
            system_config (Dict[str, Any]): System configuration parameters.
            social_score (Optional[str]): A formatted string for the social score
                                          (e.g., "2,500 karma" or "1.2M followers").
                                          This line is omitted if not provided.
        """
        post_time = self._format_post_time(submission)

        # --- Build the new, neatly formatted message ---
        message_parts = []
        message_parts.append(f"<b>Source:</b> {label}")
        message_parts.append(f"<b>User:</b> {user}")

        # Conditionally add the social score only if it exists
        if social_score:
            message_parts.append(f"<b>Social Score:</b> {social_score}")

        message_parts.append(f"<b>Time:</b> {post_time}")

        # MODIFIED: Use submission.shortlink to get a direct, permanent URL to the post.
        # This fixes the issue of linking to an image gallery instead of the post itself.
        link_html = f"<a href='{submission.shortlink}'>View Original Post</a>"
        message_parts.append(f"\n{link_html}")  # Add a newline for spacing

        original_message = "\n".join(message_parts)
        # --- End of message building ---

        logging.info(f"Formatted message created:\n{original_message}")

        # Fetch sentiment and summary (no changes here)
        sentiment = openai_bot.analyze_sentiment(
            submission.selftext,
            system_config.get("sentiment_char_limit", 100)
        )
        summary = openai_bot.summarize_text(
            submission.selftext,
            system_config.get("summary_char_limit", 500) # The config value is changed
        )

        # Call send_telegram_message with the newly formatted original_message
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
        Sends a single, consolidated message to a Telegram chat.

        The message is structured as follows:
        - A line of emojis (🔥 for bullish, ❄️ for bearish) representing the sentiment.
        - Two empty lines for spacing.
        - The original post message (which should be pre-formatted with any HTML).
        - The summary of the post.

        Parameters:
            original_message (str): The pre-formatted initial post message, including any HTML links.
            sentiment_data (str | dict): JSON string or dictionary with sentiment score & direction.
            summary (str): The summary text.
            system_config (dict): Configuration settings.
        """
        if not system_config.get("telegram_enabled", True):
            logging.info("Telegram notifications are disabled.")
            return

        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        TELEGRAM_CHAT_ID = system_config.get("telegram_chat_id", "")

        if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
            logging.error("Telegram bot token or chat ID is not configured. Message not sent.")
            return

        send_message_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        # --- Process sentiment into the emoji-only header ---
        sentiment_header = "❓"  # Default in case of error
        try:
            if isinstance(sentiment_data, str):
                sentiment_data = json.loads(sentiment_data)

            if isinstance(sentiment_data, dict) and "sentiment" in sentiment_data and "direction" in sentiment_data:
                sentiment_score = int(sentiment_data["sentiment"])
                direction = sentiment_data["direction"].lower()
                emoji_count = max(1, sentiment_score // 10)  # Ensure at least one emoji

                if direction == "bullish":
                    sentiment_header = "🔥" * emoji_count
                elif direction == "bearish":
                    sentiment_header = "❄️" * emoji_count
            else:
                # Silently use default if format is invalid, as logging will capture it
                pass

        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            logging.error(f"Could not process sentiment data: {sentiment_data} | Error: {e}")

        # --- Combine all parts into a single message ---
        full_message_text = f"{sentiment_header}\n\n{original_message}\n\n{summary}"

        # --- Prepare and send the API request ---
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": full_message_text,
            "parse_mode": "HTML"  # CRITICAL: This tells Telegram to render the <a> tag
        }

        try:
            response = requests.post(send_message_url, json=payload)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
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