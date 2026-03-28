
import unittest
import pandas as pd
from generate_report import detect_anomalies, detect_concerning_trends

class TestInsightDetectors(unittest.TestCase):
    def setUp(self):
        # Mocking data for testing
        self.week_labels = ["L2W", "L1W", "L0W"]
        self.dimensions = ["COUNTRY", "CITY", "ZONE"]
        self.metric_col = "METRIC"
        self.mock_df = pd.DataFrame({
            "COUNTRY": ["CO", "MX", "BR"],
            "CITY": ["Bogota", "CDMX", "Sao Paulo"],
            "ZONE": ["A", "B", "C"],
            "METRIC": ["Lead Penetration", "Perfect Orders", "Lead Penetration"],
            "L2W": [0.5, 0.8, 0.9],
            "L1W": [0.5, 0.7, 0.8],
            "L0W": [0.7, 0.6, 0.7] # A: +40% (Anomaly), B: -14% (Anomaly), C: Decline streak AND -12.5% WoW (Anomaly)
        })

    def test_detect_anomalies(self):
        """Test WoW anomaly detection (threshold 0.10)."""
        anomalies = detect_anomalies(self.mock_df, self.week_labels, self.dimensions, self.metric_col, threshold=0.10)
        # Expected: A, B, and C are all anomalies (>10% change)
        self.assertEqual(len(anomalies), 3)
        zones = set(anomalies["ZONE"])
        self.assertIn("A", zones)
        self.assertIn("B", zones)
        self.assertIn("C", zones)

    def test_detect_trends(self):
        """Test detection of consecutive declines."""
        trends = detect_concerning_trends(self.mock_df, self.week_labels, self.dimensions, self.metric_col, consecutive_weeks=2)
        # Expected: B (0.8->0.7->0.6) and C (0.9->0.8->0.7)
        self.assertEqual(len(trends), 2)
        zones = set(trends["ZONE"])
        self.assertIn("B", zones)
        self.assertIn("C", zones)

    # ── Edge Case Tests ─────────────────────────────────────────────

    def test_detect_anomalies_zero_division(self):
        """Verify that zero in prev week is handled (no crash, filtered out)."""
        df_zero = pd.DataFrame({
            "COUNTRY": ["CO"], "CITY": ["Bogota"], "ZONE": ["Z"],
            "METRIC": ["Orders"], "L1W": [0], "L0W": [10]
        })
        # L1W is 0 -> wow_change is NaN -> abs_change is NaN -> NaN > 0.1 is False
        anomalies = detect_anomalies(df_zero, ["L1W", "L0W"], self.dimensions, self.metric_col)
        self.assertEqual(len(anomalies), 0)  # Correctly filtered out

    def test_detect_trends_empty_data(self):
        """Verify that empty dataframe doesn't cause crash in trend detection."""
        empty_df = pd.DataFrame(columns=["COUNTRY", "CITY", "ZONE", "METRIC", "L2W", "L1W", "L0W"])
        trends = detect_concerning_trends(empty_df, self.week_labels, self.dimensions, self.metric_col)
        self.assertTrue(trends.empty)

if __name__ == "__main__":
    unittest.main()
