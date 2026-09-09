import unittest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

from storage import JsonStorage, SupabaseStorage


class StorageDoubleClaimTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app_dir = self.temp_dir.name
        
        # Setup initial invoices for JsonStorage
        self.invoices_file = os.path.join(self.app_dir, "payment_invoices.json")
        initial_invoices = {
            "inv_1": {
                "invoice_id": "inv_1",
                "settlement_id": "settlement_abc"
            },
            "inv_2": {
                "invoice_id": "inv_2",
                "split": {
                    "legs": [
                        {"settlement_id": "settlement_def"}
                    ]
                }
            }
        }
        with open(self.invoices_file, "w") as f:
            json.dump(initial_invoices, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_json_storage_is_settlement_id_claimed(self):
        storage = JsonStorage(
            ledger_path=os.path.join(self.app_dir, "ledger.json"),
            reports_path=os.path.join(self.app_dir, "reports.json"),
            invoices_path=self.invoices_file,
            creators_path=os.path.join(self.app_dir, "creators.json"),
            provider_controls_path=os.path.join(self.app_dir, "controls.json")
        )
        
        # Test existing root settlement_id
        self.assertTrue(storage.is_settlement_id_claimed("settlement_abc"))
        
        # Test existing split leg settlement_id
        self.assertTrue(storage.is_settlement_id_claimed("settlement_def"))
        
        # Test non-existent
        self.assertFalse(storage.is_settlement_id_claimed("settlement_new"))
        
        # Test exclude invoice
        self.assertFalse(storage.is_settlement_id_claimed("settlement_abc", exclude_invoice_id="inv_1"))

    @patch("storage.SupabaseStorage._request")
    def test_supabase_storage_is_settlement_id_claimed(self, mock_request):
        storage = SupabaseStorage(url="http://fake", service_role_key="fake")
        
        # Simulate returning a row from qma_payment_events
        mock_request.return_value = [{"invoice_id": "inv_1"}]
        
        self.assertTrue(storage.is_settlement_id_claimed("settlement_abc"))
        
        # If we exclude inv_1, it should return False
        self.assertFalse(storage.is_settlement_id_claimed("settlement_abc", exclude_invoice_id="inv_1"))
        
        # Simulate no rows found
        mock_request.return_value = []
        self.assertFalse(storage.is_settlement_id_claimed("settlement_new"))

        # Verify correct params were used (limit 1)
        mock_request.assert_called_with(
            "GET",
            "qma_payment_events",
            params={
                "select": "invoice_id",
                "settlement_id": "eq.settlement_new",
                "limit": "1"
            }
        )


if __name__ == "__main__":
    unittest.main()
