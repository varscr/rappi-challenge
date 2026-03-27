
import unittest
from src.llm_client import LLMClient
from src.data_loader import load_all
from src.query_engine import QueryEngine

class TestLLMIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load real data and initialize real LLMClient once for all tests."""
        cls.df_metrics, cls.df_orders, cls.week_labels = load_all()
        cls.llm = LLMClient()
        cls.engine = QueryEngine(cls.llm, cls.df_metrics, cls.df_orders, cls.week_labels)

    def test_intent_parsing_live(self):
        """Verify that the real LLM can parse a standard question correctly."""
        question = "What are the top 5 zones with highest Lead Penetration?"
        intent = self.engine._parse_intent(question)
        
        self.assertEqual(intent["query_type"], "filter_rank")
        self.assertEqual(intent["metric"], "Lead Penetration")
        self.assertEqual(intent["top_n"], 5)
        self.assertEqual(intent["sort_order"], "desc")

    def test_narration_live(self):
        """Verify that the real LLM can narrate a small result set."""
        question = "Top zones by Lead Penetration"
        # Mocking a small result dataframe
        mock_res_df = self.df_metrics[self.df_metrics["METRIC"] == "Lead Penetration"].head(3)
        
        # Format the narrator prompt manually to test the narrate() method
        prompt = f"User asked: {question}\nQuery result:\n{mock_res_df.to_string()}"
        narration = self.llm.narrate(prompt)
        
        self.assertIsInstance(narration, str)
        self.assertTrue(len(narration) > 10)
        print(f"\nLive Narration: {narration}")

    def test_followup_suggestions_live(self):
        """Verify that the real LLM can suggest follow-up questions."""
        question = "How is Lead Penetration in Colombia?"
        intent = {"query_type": "aggregate", "metric": "Lead Penetration"}
        
        # Test the suggest() method via the engine
        suggestions = self.engine._suggest(question, intent)
        
        self.assertIsInstance(suggestions, list)
        self.assertEqual(len(suggestions), 2)
        for s in suggestions:
            self.assertIsInstance(s, str)
        print(f"\nLive Suggestions: {suggestions}")

if __name__ == "__main__":
    unittest.main()
