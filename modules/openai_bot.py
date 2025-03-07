import os
import time
import logging
from typing import Any, Optional, List, Dict
from openai import OpenAI  # Assumes your OpenAI library provides this class


class OpenAIBot:
    """
    A bot that interfaces with OpenAI's API using external prompt templates and function calling.

    This class loads three prompt templates from files:
      - A review post prompt,
      - A sentiment analysis prompt,
      - And a summarization prompt.

    For the review and sentiment methods, we use OpenAI's function calling feature to force
    the output into a specific JSON format.
    """

    def __init__(
            self,
            review_prompt_path: str,
            sentiment_prompt_path: str,
            summarization_prompt_path: str
    ) -> None:
        """
        Initializes the OpenAIBot by loading prompt templates from files.

        Args:
            review_prompt_path (str): Path to the review post prompt template.
            sentiment_prompt_path (str): Path to the sentiment analysis prompt template.
            summarization_prompt_path (str): Path to the summarization prompt template.
        """
        self.api_key: str = os.getenv("OPENAI_API_KEY", "")
        if not self.api_key:
            logging.warning("OPENAI_API_KEY not set. Please set it in .env or the environment.")
        self.client = OpenAI(api_key=self.api_key)

        try:
            with open(review_prompt_path, "r", encoding="utf-8") as file:
                self.review_prompt_template: str = file.read()
        except Exception as e:
            logging.error(f"Error loading review prompt file '{review_prompt_path}': {e}")
            self.review_prompt_template = ""

        try:
            with open(sentiment_prompt_path, "r", encoding="utf-8") as file:
                self.sentiment_prompt_template: str = file.read()
        except Exception as e:
            logging.error(f"Error loading sentiment prompt file '{sentiment_prompt_path}': {e}")
            self.sentiment_prompt_template = ""

        try:
            with open(summarization_prompt_path, "r", encoding="utf-8") as file:
                self.summarization_prompt_template: str = file.read()
        except Exception as e:
            logging.error(f"Error loading summarization prompt file '{summarization_prompt_path}': {e}")
            self.summarization_prompt_template = ""

    def generate_response(
        self,
        prompt: str,
        max_tokens: int = 50,
        temperature: float = 0.7,
        model: str = "gpt-4o-mini",
        functions: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generate a response from OpenAI's model using the provided prompt and optional function calling.

        Args:
            prompt (str): The prompt to send to the model.
            max_tokens (int): Maximum number of tokens for the response.
            temperature (float): Sampling temperature.
            model (str): The model name to use. Ensure your API key is permitted for this model.
            functions (Optional[List[Dict[str, Any]]]): A list of function specifications to force structured output.

        Returns:
            str: The generated response text (or the function call arguments if functions are provided),
                 or "ERROR" if an error occurs.
        """
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                functions=functions,
                function_call="auto" if functions else None
            )
            message = chat_completion.choices[0].message
            if functions and hasattr(message, "function_call") and message.function_call:
                # Use dot notation to access the arguments attribute
                response = message.function_call.arguments
            else:
                response = message.content
            time.sleep(1)  # Sleep to manage rate limits.
            return response.strip()
        except Exception as e:
            logging.error(f"Error during OpenAI API call: {e}")
            return "ERROR"


    def review_post(self, post_content: str) -> str:
        """
        Reviews a post by formatting the review prompt with the post content and generating a response.
        Forces output into a JSON structure with keys 'is_significant' (boolean) and 'explanation' (string).

        Args:
            post_content (str): The content of the post to review.

        Returns:
            str: The JSON response from the model.
        """
        prompt: str = self.review_prompt_template.format(content=post_content)
        review_function = [{
            "name": "review_post",
            "description": "Return a JSON object indicating if the post is significant along with an explanation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "is_significant": {
                        "type": "boolean",
                        "description": "True if the post is market-moving, false otherwise."
                    },
                    "explanation": {
                        "type": "string",
                        "description": "A brief explanation of the decision."
                    }
                },
                "required": ["is_significant", "explanation"]
            }
        }]
        return self.generate_response(prompt, max_tokens=100, temperature=0.5, model="gpt-4o-mini",
                                      functions=review_function)

    def analyze_sentiment(self, post_content: str, character_limit: int) -> str:
        """
        Generates a sentiment analysis focusing on bullish sentiment with a specified character limit.
        Forces output into a JSON structure with a single key "sentiment" that is an integer between 0 and 100.

        Args:
            post_content (str): The text to analyze.
            character_limit (int): The maximum character length for the response.

        Returns:
            str: The JSON response from the model.
        """
        prompt: str = self.sentiment_prompt_template.format(character_limit=character_limit, content=post_content)
        sentiment_function = [{
            "name": "analyze_sentiment",
            "description": "Return a JSON object with a sentiment rating between 0 and 100, along with the market direction (bullish, bearish, or neutral).",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentiment": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Sentiment rating from 0 (no significant sentiment) to 100 (extremely strong sentiment)."
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["bullish", "bearish", "neutral"],
                        "description": "The overall market direction conveyed in the text: bullish (positive opportunity), bearish (negative outlook), or neutral (not significant)."
                    }
                },
                "required": ["sentiment", "direction"]
            }
        }]

        return self.generate_response(prompt, max_tokens=character_limit, temperature=0.7, model="gpt-4o-mini",
                                      functions=sentiment_function)

    def summarize_text(self, post_content: str, character_limit: int) -> str:
        """
        Summarizes the provided text in exactly the given character limit.
        This method does not force a JSON structure, as free text is acceptable.

        Args:
            post_content (str): The text to summarize.
            character_limit (int): The maximum character length for the summary.

        Returns:
            str: The summary response.
        """
        prompt: str = self.summarization_prompt_template.format(character_limit=character_limit, content=post_content)
        return self.generate_response(prompt, max_tokens=character_limit, temperature=0.7, model="gpt-4o-mini")
