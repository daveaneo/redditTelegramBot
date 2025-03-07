import json
import os
import time
import logging

class CacheManager:
    """A cache manager to store, back up, and manage processed message IDs.

    This class loads and saves a JSON file containing message IDs with timestamps.
    It provides methods to check if a message is cached, add new messages, print the cache,
    delete and reset the cache, and clean up old entries.
    """
    def __init__(self, cache_file: str, expiration_time: int) -> None:
        """Initializes the CacheManager.

        Args:
            cache_file (str): The path to the cache JSON file.
            expiration_time (int): The time in seconds after which a cache entry expires.
        """
        self.cache_file: str = cache_file
        self.expiration_time: int = expiration_time
        self.cache: dict = {}
        self.load_cache()

    def load_cache(self) -> None:
        """Loads the cache from the specified JSON file.

        If the file does not exist or an error occurs during loading, an empty cache is initialized.
        """
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception as e:
                logging.error(f"Error loading cache: {e}")
                self.cache = {}
        else:
            self.cache = {}

    def save_cache(self) -> None:
        """Saves the current in-memory cache to the JSON file.

        Overwrites any existing cache file.
        """
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f)
        except Exception as e:
            logging.error(f"Error saving cache: {e}")

    def is_cached(self, message_id: str) -> bool:
        """Checks if a message is in the cache and is less than 24 hours old.

        Args:
            message_id (str): The unique identifier of the message.

        Returns:
            bool: True if the message is in the cache and was added less than 24 hours ago; otherwise, False.
        """
        if message_id in self.cache:
            # Check if the message is within the past 24 hours (24*3600 seconds)
            if time.time() - self.cache[message_id] < 24 * 3600:
                return True
        return False

    def add(self, message_id: str) -> None:
        """Adds a message ID to the cache with the current timestamp.

        Args:
            message_id (str): The unique identifier of the message.
        """
        self.cache[message_id] = time.time()
        self.save_cache()

    def print_cache(self) -> None:
        """Prints the current cache to the terminal."""
        print(self.cache)

    def delete_and_reset(self) -> None:
        """Deletes the in-memory cache and removes the cache file from disk.

        Resets the cache dictionary and attempts to delete the cache JSON file.
        """
        self.cache = {}  # Reset in-memory cache
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
                logging.info("Cache file removed successfully.")
            except Exception as e:
                logging.error(f"Error deleting cache file: {e}")

    def cleanup(self) -> None:
        """Removes cache entries older than the configured expiration time.

        Iterates over cached entries and deletes those whose timestamp is older than expiration_time.
        """
        current_time: float = time.time()
        removed: list = []
        for msg_id, timestamp in list(self.cache.items()):
            if current_time - timestamp > self.expiration_time:
                removed.append(msg_id)
                del self.cache[msg_id]
        if removed:
            logging.info(f"Cleaned up messages: {removed}")
            self.save_cache()
