import unittest
from unittest.mock import patch

from src.storage import database


class FakeWorksheet:
    def __init__(self):
        self.title = "old-tab"
        self.updates = []
        self.appended = []

    def batch_update(self, updates, value_input_option=None):
        self.updates.extend(updates)

    def col_values(self, column):
        return ["job_hash"]

    def append_rows(self, rows, value_input_option=None):
        self.appended.extend(rows)


class FakeSpreadsheet:
    def __init__(self, worksheet):
        self.worksheet = worksheet

    def worksheets(self):
        return [self.worksheet]

    def values_batch_get(self, ranges):
        return {
            "valueRanges": [
                {"values": [["existing-hash"]]},
                {"values": []},
            ]
        }


class DatabaseDedupTest(unittest.TestCase):
    def setUp(self):
        database._known_hashes = None
        database._known_jobs = {}

    def test_duplicate_with_new_description_is_backfilled_and_reset(self):
        ws = FakeWorksheet()
        spreadsheet = FakeSpreadsheet(ws)
        job = {
            "job_hash": "existing-hash",
            "description": "Detailed responsibilities and qualifications. " * 20,
        }
        with patch.object(database, "_get_sheet", return_value=ws), patch.object(
            database, "_get_spreadsheet", return_value=spreadsheet
        ):
            inserted = database.insert_jobs_batch([job])

        self.assertEqual(inserted, 0)
        self.assertEqual(len(ws.updates), 3)
        self.assertEqual(ws.updates[0]["range"], "Q2")
        self.assertEqual(ws.updates[1]["range"], "G2:L2")
        self.assertEqual(ws.updates[2]["range"], "R2")


if __name__ == "__main__":
    unittest.main()
