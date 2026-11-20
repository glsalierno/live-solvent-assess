import json
import unittest
from unittest.mock import patch

import requests

from packages.doss_core import pubchem


def response(status, payload=None, retry_after=None):
    reply = requests.Response()
    reply.status_code = status
    reply._content = json.dumps(payload or {}).encode()
    if retry_after is not None:
        reply.headers["Retry-After"] = retry_after
    return reply


class PubChemThrottleTests(unittest.TestCase):
    def setUp(self):
        pubchem._cache.clear()
        pubchem._next_request_at = 0
        pubchem._cooldown_until = 0

    def tearDown(self):
        pubchem._cache.clear()
        pubchem._next_request_at = 0
        pubchem._cooldown_until = 0

    def test_each_network_call_is_paced(self):
        with (
            patch.object(pubchem.time, "monotonic", return_value=100),
            patch.object(pubchem.time, "sleep") as sleep,
        ):
            pubchem._throttle()
            pubchem._throttle()
            self.assertAlmostEqual(sleep.call_args.args[0], 0.35)

    def test_cache_hit_does_not_call_network_and_uses_explicit_timeout(self):
        with patch.object(requests, "get", return_value=response(200, {"IdentifierList": {"CID": [180]}})) as get:
            self.assertEqual(pubchem.get_cid_by_cas("67-64-1"), 180)
            self.assertEqual(pubchem.get_cid_by_cas("67-64-1"), 180)
            get.assert_called_once()
            self.assertEqual(get.call_args.kwargs["timeout"], (5.0, 30.0))

    def test_429_and_503_are_retried_with_jitter_and_retry_after(self):
        with (
            patch.object(pubchem, "_throttle"),
            patch.object(pubchem.random, "uniform", return_value=0.25),
            patch.object(pubchem.time, "sleep") as sleep,
            patch.object(requests, "get", side_effect=[
                response(429), response(503, retry_after="4"), response(200, {"IdentifierList": {"CID": [180]}}),
            ]) as get,
        ):
            self.assertEqual(pubchem.get_cid_by_cas("67-64-1"), 180)
            self.assertEqual(get.call_count, 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1.25, 4])

    def test_exhausted_retry_is_typed_and_not_cached(self):
        with (
            patch.object(pubchem, "_throttle"),
            patch.object(pubchem.time, "sleep"),
            patch.object(requests, "get", return_value=response(503)) as get,
        ):
            with self.assertRaises(pubchem.PubChemThrottledError):
                pubchem.get_cid_by_cas("67-64-1")
            self.assertEqual(get.call_count, 4)
            self.assertEqual(len(pubchem._cache), 0)

    def test_retry_after_larger_than_wait_budget_stops_network_calls(self):
        with patch.object(requests, "get", return_value=response(429, retry_after="90")) as get:
            with self.assertRaises(pubchem.PubChemThrottledError) as first:
                pubchem.get_cid_by_cas("67-64-1")
            self.assertEqual(first.exception.retry_after, 90)
            with self.assertRaises(pubchem.PubChemThrottledError):
                pubchem.get_cid_by_cas("64-17-5")
            get.assert_called_once()

    def test_not_found_is_distinct_from_access_denied(self):
        with (
            patch.object(pubchem, "_throttle"),
            patch.object(requests, "get", side_effect=[response(404), response(403)]) as get,
        ):
            self.assertIsNone(pubchem.get_cid_by_cas("67-64-1"))
            with self.assertRaisesRegex(pubchem.PubChemError, "HTTP 403"):
                pubchem.get_cid_by_cas("67-64-1")
            self.assertEqual(get.call_count, 2)

    def test_view_throttle_preserves_partial_identity_and_shows_warning(self):
        with (
            patch.object(pubchem, "get_cid_by_cas", return_value=180),
            patch.object(pubchem, "get_compound_properties", return_value={"Title": "Acetone"}),
            patch.object(pubchem, "get_compound_view_data", side_effect=pubchem.PubChemThrottledError("fixture")),
        ):
            result = pubchem.fetch_compound_data("67-64-1")
            self.assertEqual(result["name"], "Acetone")
            self.assertEqual(result["ghs_hazards"], [])
            self.assertIn("rate-limiting extended data", result["view_warning"])
