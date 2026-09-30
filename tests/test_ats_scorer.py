import unittest
from unittest.mock import patch

from src.analyzer import ats_scorer


class AtsScorerTest(unittest.TestCase):
    @patch.object(ats_scorer.time, "sleep")
    @patch.object(ats_scorer, "update_ats")
    @patch.object(ats_scorer, "_score_one")
    @patch.object(ats_scorer, "get_unscored_jobs")
    @patch.object(ats_scorer, "get_resume_text")
    def test_only_complete_descriptions_are_scored(
        self, get_resume, get_jobs, score_one, update_ats, _sleep
    ):
        get_resume.return_value = "resume " * 200
        get_jobs.return_value = [
            {"job_hash": "short", "description": "title only", "company": "A", "title": "DE"},
            {
                "job_hash": "ready",
                "description": "Complete job description. " * 30,
                "company": "B",
                "title": "Data Engineer",
                "source": "greenhouse",
                "_sheet_tab": "today",
            },
        ]
        score_one.return_value = ({
            "ats_score": 80,
            "fit_tier": "Strong",
            "skills_required": ["Python"],
            "matched_keywords": ["Python"],
            "missing_keywords": [],
            "summary": "Strong fit",
        }, 100)

        with patch.object(ats_scorer, "_get_client"):
            ats_scorer.score_pending_jobs()

        score_one.assert_called_once()
        self.assertIn("Complete job description", score_one.call_args.args[1])
        update_ats.assert_called_once()
        self.assertEqual(update_ats.call_args.kwargs["job_hash"], "ready")

    @patch.object(ats_scorer, "get_unscored_jobs")
    @patch.object(ats_scorer, "get_resume_text", return_value="")
    def test_missing_resume_aborts_before_reading_jobs(self, _resume, get_jobs):
        with self.assertRaisesRegex(RuntimeError, "readable resume"):
            ats_scorer.score_pending_jobs()
        get_jobs.assert_not_called()

    def test_decommissioned_model_error_fails_pipeline(self):
        error = Exception("The model has been decommissioned")
        self.assertTrue(ats_scorer._is_fatal_api_error(error))

    @patch.object(ats_scorer.time, "sleep")
    @patch.object(ats_scorer, "update_ats")
    @patch.object(ats_scorer, "_score_one", side_effect=ValueError("bad JSON"))
    @patch.object(ats_scorer, "_get_client")
    @patch.object(ats_scorer, "get_unscored_jobs")
    @patch.object(ats_scorer, "get_resume_text")
    def test_all_scoring_failures_fail_pipeline(
        self, get_resume, get_jobs, _get_client, _score_one, _update_ats, _sleep
    ):
        get_resume.return_value = "resume " * 200
        get_jobs.return_value = [{
            "job_hash": "broken",
            "description": "Complete job description. " * 30,
            "company": "A",
            "title": "Data Engineer",
        }]

        with self.assertRaisesRegex(RuntimeError, "failed for all 1"):
            ats_scorer.score_pending_jobs()


if __name__ == "__main__":
    unittest.main()
