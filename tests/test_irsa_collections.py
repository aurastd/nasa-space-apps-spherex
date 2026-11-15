import unittest
import warnings
from unittest.mock import patch

from astropy.table import Table
from astroquery.ipac.irsa import Irsa

from utils import spherex_data as sx


class IrsaCollectionTests(unittest.TestCase):
    def test_live_collections_exclude_deep_and_calibration_and_sort_newest_first(self):
        listing = Table({
            "collection": [
                "spherex_qr2",
                "spherex_deep",
                "spherex_dr1",
                "spherex_qr3",
                "spherex_dr1_cal",
            ],
        })
        with patch.object(Irsa, "list_collections", return_value=listing):
            collections = sx._wide_collections()

        self.assertEqual(collections, ["spherex_dr1", "spherex_qr3", "spherex_qr2"])

    def test_query_continues_after_collection_failure_and_keeps_newest_duplicate(self):
        listing = Table({"collection": ["spherex_qr3", "spherex_dr1", "spherex_qr2"]})

        def query_sia(pos, collection):
            if collection == "spherex_qr2":
                raise RuntimeError("collection unavailable")
            return Table({
                "access_url": [f"https://irsa.example/{1}/level2_{collection}.fits"],
                "t_min": [60000.0],
                "energy_bandpassname": ["D1"],
            })

        with patch.object(Irsa, "list_collections", return_value=listing), \
                patch.object(Irsa, "query_sia", side_effect=query_sia), \
                warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            rows = sx._sia_query(sx.Target(150.0, 2.0), 1.0)

        self.assertEqual(len(rows), 1)
        self.assertIn("spherex_dr1", rows[0]["url"])
        self.assertTrue(any("continuing with successful collections" in str(w.message) for w in caught))

    def test_raises_a_useful_error_when_every_collection_fails(self):
        listing = Table({"collection": ["spherex_dr1", "spherex_qr3"]})
        with patch.object(Irsa, "list_collections", return_value=listing), \
                patch.object(Irsa, "query_sia", side_effect=RuntimeError("502 Proxy Error")):
            with self.assertRaisesRegex(RuntimeError, "spherex_dr1.*502 Proxy Error.*spherex_qr3"):
                sx._sia_query(sx.Target(150.0, 2.0), 1.0)

    def test_does_not_report_no_coverage_if_another_collection_failed(self):
        listing = Table({"collection": ["spherex_dr1", "spherex_qr3"]})
        empty_result = Table({
            "access_url": [],
            "t_min": [],
            "energy_bandpassname": [],
        })

        def query_sia(pos, collection):
            if collection == "spherex_dr1":
                return empty_result
            raise RuntimeError("502 Proxy Error")

        with patch.object(Irsa, "list_collections", return_value=listing), \
                patch.object(Irsa, "query_sia", side_effect=query_sia):
            with self.assertRaisesRegex(RuntimeError, "returned no exposures.*spherex_qr3.*502 Proxy Error"):
                sx._sia_query(sx.Target(150.0, 2.0), 1.0)

    def test_uses_fallback_collections_when_listing_fails(self):
        with patch.object(Irsa, "list_collections", side_effect=RuntimeError("TAP unavailable")):
            with self.assertWarnsRegex(RuntimeWarning, "TAP unavailable"):
                collections = sx._wide_collections()

        self.assertEqual(collections, sx.COLLECTIONS)


if __name__ == "__main__":
    unittest.main()
