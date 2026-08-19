import unittest
from threading import Barrier
from unittest.mock import patch

from assets.api_calls import extraction_api


class ExtractionDashboardTests(unittest.TestCase):
    def setUp(self):
        extraction_api.invalidate_dashboard_cache()

    def tearDown(self):
        extraction_api.invalidate_dashboard_cache()

    def test_dashboard_requests_run_concurrently_and_are_cached(self):
        barrier = Barrier(4, timeout=2)

        def result(value):
            def load():
                barrier.wait()
                return value

            return load

        with (
            patch.object(extraction_api, "get_big_numbers", side_effect=result({"total": 1})) as big_numbers,
            patch.object(extraction_api, "get_priority_documents", side_effect=result(["priority"])) as priority,
            patch.object(extraction_api, "get_all_documents", side_effect=result(["all"])) as all_documents,
            patch.object(extraction_api, "get_pending_documents", side_effect=result(["pending"])) as pending,
        ):
            first = extraction_api.get_extraction_dashboard()
            first["all_documents"].append("local mutation")
            second = extraction_api.get_extraction_dashboard()

        self.assertEqual(
            second,
            {
                "kpis": {"total": 1},
                "priority_documents": ["priority"],
                "all_documents": ["all"],
                "pending_documents": ["pending"],
            },
        )
        for request_mock in (big_numbers, priority, all_documents, pending):
            request_mock.assert_called_once_with()

    def test_cache_can_be_invalidated(self):
        cached = {
            "kpis": {},
            "priority_documents": [],
            "all_documents": [],
            "pending_documents": [],
        }

        with patch.object(extraction_api, "get_big_numbers", return_value={}) as big_numbers:
            with (
                patch.object(extraction_api, "get_priority_documents", return_value=[]),
                patch.object(extraction_api, "get_all_documents", return_value=[]),
                patch.object(extraction_api, "get_pending_documents", return_value=[]),
            ):
                self.assertEqual(extraction_api.get_extraction_dashboard(), cached)
                extraction_api.invalidate_dashboard_cache()
                self.assertEqual(extraction_api.get_extraction_dashboard(), cached)

        self.assertEqual(big_numbers.call_count, 2)


if __name__ == "__main__":
    unittest.main()
