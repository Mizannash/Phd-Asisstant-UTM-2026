import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "D:\\PhD_Assistant_UTM\\src")))
# Actually, since it will be copied to tests/:
sys.path.insert(0, r"D:\PhD_Assistant_UTM\src")

from scout import run_scout_pipeline

class TestBackoffFloatBug(unittest.TestCase):

    @patch("scout.Crew")
    @patch("time.sleep")
    def test_scout_callback_receives_int(self, mock_sleep, mock_crew_class):
        # Setup mock crew to fail with 503 error
        mock_crew_instance = MagicMock()
        mock_crew_class.return_value = mock_crew_instance
        
        # We want it to fail once with a 503 error, then succeed
        mock_crew_instance.kickoff.side_effect = [
            Exception("503 Service Unavailable"),
            "Success"
        ]
        
        # We need a callback to verify it receives an int
        callback_called_with_types = []
        
        def mock_callback(wait_time, attempt, max_retries):
            callback_called_with_types.append(type(wait_time))
            
        try:
            run_scout_pipeline(on_rate_limit_callback=mock_callback, force_run=True)
        except Exception:
            pass # Ignore other errors if it fails later
            
        # Verify the callback was called with an int!
        self.assertTrue(len(callback_called_with_types) > 0, "Callback was never called")
        self.assertEqual(callback_called_with_types[0], int, f"Callback received {callback_called_with_types[0]}, expected int")

if __name__ == "__main__":
    unittest.main()
