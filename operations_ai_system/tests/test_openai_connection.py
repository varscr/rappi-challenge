
import os
import unittest
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class TestOpenAIConnection(unittest.TestCase):
    def test_api_key_validity(self):
        """Verify that the OpenAI API key is set and can make a simple request."""
        api_key = os.getenv("OPENAI_API_KEY")
        self.assertIsNotNone(api_key, "OPENAI_API_KEY is not set in .env")
        
        client = OpenAI(api_key=api_key)
        try:
            # Make a minimal request to verify the key
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Say 'Connection Successful'"}],
                max_tokens=10
            )
            content = response.choices[0].message.content.strip()
            print(f"\nOpenAI Response: {content}")
            self.assertIn("Connection Successful", content)
        except Exception as e:
            self.fail(f"OpenAI API call failed: {e}")

if __name__ == "__main__":
    unittest.main()
