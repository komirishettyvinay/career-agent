import unittest

from src.fetchers._descriptions import (
    description_from_page,
    html_to_text,
    lever_description,
)


class DescriptionHelpersTest(unittest.TestCase):
    def test_html_to_text_preserves_readable_breaks(self):
        text = html_to_text("<h2>Requirements</h2><ul><li>Python</li><li>SQL</li></ul>")
        self.assertIn("Requirements", text)
        self.assertIn("Python", text)
        self.assertIn("SQL", text)
        self.assertNotIn("<li>", text)

    def test_lever_current_fields_are_combined(self):
        posting = {
            "openingPlain": "Build reliable data products.",
            "descriptionPlain": "Own production pipelines.",
            "lists": [{"text": "Requirements", "content": "<li>Python</li><li>SQL</li>"}],
            "additionalPlain": "Canadian remote role.",
        }
        text = lever_description(posting)
        for expected in ("data products", "pipelines", "Python", "SQL", "Canadian"):
            self.assertIn(expected, text)

    def test_json_ld_job_description_is_extracted(self):
        page = """
        <html><script type="application/ld+json">
        {"@context":"https://schema.org","@type":"JobPosting",
         "description":"<p>Design ETL pipelines with Python and SQL.</p>"}
        </script></html>
        """
        self.assertEqual(
            description_from_page(page),
            "Design ETL pipelines with Python and SQL.",
        )


if __name__ == "__main__":
    unittest.main()
