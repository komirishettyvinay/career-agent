import unittest

from src.fetchers import greenhouse, smartrecruiters, workday


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.requested_urls = []

    def get(self, url, **kwargs):
        self.requested_urls.append(url)
        return FakeResponse(self.payload)


class FetcherDetailsTest(unittest.TestCase):
    def test_greenhouse_detail_content(self):
        session = FakeSession({"content": "<p>Build data pipelines with Python.</p>"})
        result = greenhouse._get_description(session, "example", {"id": 42})
        self.assertEqual(result, "Build data pipelines with Python.")
        self.assertTrue(session.requested_urls[0].endswith("/example/jobs/42"))

    def test_smartrecruiters_detail_sections(self):
        session = FakeSession({
            "jobAd": {"sections": {
                "jobDescription": {"title": "Role", "text": "<p>Build pipelines.</p>"},
                "qualifications": {"title": "Skills", "text": "<p>Python and SQL.</p>"},
            }}
        })
        result = smartrecruiters._get_description(session, "Example", "abc")
        self.assertIn("Build pipelines", result)
        self.assertIn("Python and SQL", result)

    def test_workday_detail_description(self):
        session = FakeSession({
            "jobPostingInfo": {"jobDescription": "<p>Own the data platform.</p>"}
        })
        result = workday._get_description(
            session, "tenant", "Careers", 3, "/job/Toronto/123"
        )
        self.assertEqual(result, "Own the data platform.")
        self.assertIn("/wday/cxs/tenant/Careers/job/Toronto/123", session.requested_urls[0])


if __name__ == "__main__":
    unittest.main()
