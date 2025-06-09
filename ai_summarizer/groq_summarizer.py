import os
import httpx
import logging

logger = logging.getLogger(__name__)

class GroqSummarizer:
    def __init__(self):
        self.api_key = os.getenv("GROK_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        if not self.api_key:
            logger.warning("GROK_API_KEY environment variable not set.")

    async def summarize(self, diff_text: str) -> str:
        if not self.api_key:
            return "Error: GROK_API_KEY not set."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = [
    {
        "role": "system",
        "content": "You are an expert AI assistant that generates detailed, insightful summaries of GitHub Pull Request diffs. Provide clear explanations, highlight key changes, files affected, and the purpose of the PR."
    },
    {
        "role": "user",
        "content": f"Summarize the following GitHub PR diff in detail:\n{diff_text}"
    }
]

        payload = {
            "model": "llama3-70b-8192",
            "messages": messages,
            "temperature": 0.3
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.base_url, headers=headers, json=payload)
                response.raise_for_status()

                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response content: {response.text}")

                result = response.json()
                summary = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                if not summary:
                    logger.error("No summary content found in the response.")
                    return "Error: No summary content received from API."

                return summary

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error occurred: {http_err} - Response: {http_err.response.text}")
            return f"Error: HTTP error occurred - {http_err}"
        except Exception as err:
            logger.error(f"Unexpected error: {err}")
            return f"Error: Unexpected error occurred - {err}"
