import unittest

from src.storage.database import _format_sheet


class FakeSpreadsheet:
    def __init__(self):
        self.body = None

    def batch_update(self, body):
        self.body = body


class FakeWorksheet:
    def __init__(self):
        self.row_count = 2000
        self.id = 123
        self.spreadsheet = FakeSpreadsheet()
        self.formatted_range = None
        self.cell_format = None

    def format(self, cell_range, cell_format):
        self.formatted_range = cell_range
        self.cell_format = cell_format


class SheetFormattingTest(unittest.TestCase):
    def test_rows_are_compact_and_text_is_clipped(self):
        sheet = FakeWorksheet()
        _format_sheet(sheet)

        self.assertEqual(sheet.formatted_range, "A1:R2000")
        self.assertEqual(sheet.cell_format["wrapStrategy"], "CLIP")
        requests = sheet.spreadsheet.body["requests"]
        self.assertEqual(requests[0]["updateDimensionProperties"]["properties"]["pixelSize"], 28)
        self.assertEqual(requests[1]["updateDimensionProperties"]["properties"]["pixelSize"], 24)


if __name__ == "__main__":
    unittest.main()
