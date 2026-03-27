
import unittest
import pandas as pd
from unittest.mock import MagicMock, patch
from src.query_engine import QueryEngine, QueryResult

class TestQueryEngine(unittest.TestCase):
    @patch("src.query_engine.get_schema_summary")
    def setUp(self, mock_summary):
        # Mocking data for testing
        mock_summary.return_value = "Mocked Schema Context"
        
        self.mock_metrics_df = pd.DataFrame({
            "COUNTRY": ["CO", "CO", "MX", "MX"],
            "CITY": ["Bogota", "Bogota", "CDMX", "CDMX"],
            "ZONE": ["Chapinero", "Usaquen", "Roma", "Condesa"],
            "ZONE_TYPE": ["Wealthy", "Non Wealthy", "Wealthy", "Non Wealthy"],
            "ZONE_PRIORITIZATION": ["High Priority", "Prioritized", "High Priority", "Prioritized"],
            "METRIC": ["Lead Penetration"] * 4,
            "L1W": [0.5, 0.6, 0.7, 0.8],
            "L0W": [0.55, 0.65, 0.75, 0.85]
        })
        
        self.mock_orders_df = pd.DataFrame({
            "COUNTRY": ["CO", "CO", "MX", "MX"],
            "CITY": ["Bogota", "Bogota", "CDMX", "CDMX"],
            "ZONE": ["Chapinero", "Usaquen", "Roma", "Condesa"],
            "METRIC": ["Orders"] * 4,
            "L1W": [100, 200, 300, 400],
            "L0W": [110, 220, 330, 440]
        })
        
        self.week_labels = ["L1W", "L0W"]
        self.mock_llm = MagicMock()
        self.engine = QueryEngine(self.mock_llm, self.mock_metrics_df, self.mock_orders_df, self.week_labels)

    def test_filter_rank_executor(self):
        """Test top N zones by a metric."""
        intent = {
            "query_type": "filter_rank",
            "metric": "Lead Penetration",
            "top_n": 2,
            "sort_order": "desc",
            "weeks": 1
        }
        
        result = self.engine._execute_filter_rank(intent)
        self.assertEqual(len(result.df), 2)
        self.assertEqual(result.df.iloc[0]["ZONE"], "Condesa")  # Highest value (0.85)
        self.assertEqual(result.df.iloc[0]["Lead Penetration"], 0.85)

    def test_compare_executor(self):
        """Test comparing metric between groups."""
        intent = {
            "query_type": "compare",
            "metric": "Lead Penetration",
            "group_by": "ZONE_TYPE",
            "country": "CO",
            "weeks": 1
        }
        
        result = self.engine._execute_compare(intent)
        self.assertEqual(len(result.df), 2)
        # Colombia: Wealthy (0.55), Non Wealthy (0.65)
        wealthy_val = result.df[result.df["ZONE_TYPE"] == "Wealthy"]["Lead Penetration"].values[0]
        self.assertEqual(wealthy_val, 0.55)

    def test_order_growth_executor(self):
        """Test order growth calculation."""
        intent = {
            "query_type": "order_growth",
            "weeks": 2
        }
        
        result = self.engine._execute_order_growth(intent)
        # Roma: (330-300)/300 = 10%
        roma_growth = result.df[result.df["ZONE"] == "Roma"]["growth_pct"].values[0]
        self.assertEqual(roma_growth, 10.0)

    # ── Edge Case Tests ─────────────────────────────────────────────

    def test_fuzzy_match_metric(self):
        """Test that approximate metric names are resolved correctly."""
        # User asks for "lead penetracion" (typo)
        resolved = self.engine._fuzzy_match_metric("lead penetracion")
        self.assertEqual(resolved, "Lead Penetration")
        
        # User asks for something completely unrelated
        resolved = self.engine._fuzzy_match_metric("random stuff")
        self.assertEqual(resolved, "random stuff")

    def test_execute_filter_rank_no_results(self):
        """Test that filtering for a non-existent country returns empty DF."""
        intent = {
            "query_type": "filter_rank",
            "metric": "Lead Penetration",
            "country": "AR",  # Not in mock data
            "top_n": 5
        }
        result = self.engine._execute_filter_rank(intent)
        self.assertTrue(result.df.empty)

    def test_week_columns_overflow(self):
        """Test that asking for more weeks than available returns all available."""
        # Data only has 2 weeks, asking for 10
        week_cols = self.engine._week_columns(10)
        self.assertEqual(len(week_cols), 2)
        self.assertEqual(week_cols, ["L1W", "L0W"])

if __name__ == "__main__":
    unittest.main()
