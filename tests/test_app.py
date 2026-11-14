import unittest

import numpy as np

from app import (
    _interpolate_wavelength,
    explain_choice,
    measure_frame,
    rank_bandpasses,
)


class MeasurementTests(unittest.TestCase):
    def _frame(self, band: str, bad_fraction: float = 0.0) -> dict:
        shape = (41, 41)
        yy, xx = np.ogrid[: shape[0], : shape[1]]
        radius = np.sqrt((xx - 20) ** 2 + (yy - 20) ** 2)
        aperture = radius <= 2
        image = np.zeros(shape, dtype=np.float32)
        image[aperture] = 1.0
        variance = np.full(shape, 0.01, dtype=np.float32)
        flags = np.zeros(shape, dtype=np.int32)
        aperture_pixels = np.argwhere(aperture)
        bad_count = round(len(aperture_pixels) * bad_fraction)
        for y, x in aperture_pixels[:bad_count]:
            flags[y, x] = 4
        measurement = measure_frame(image, variance, flags)
        return {
            "band": band,
            "snr": measurement["snr"],
            "flagged_fraction": measurement["flagged_fraction"],
        }

    def test_source_flag_is_accepted_and_bad_flags_reduce_score(self) -> None:
        source_flags = np.full((41, 41), 2097152, dtype=np.int32)
        image = np.zeros((41, 41), dtype=np.float32)
        variance = np.full((41, 41), 0.01, dtype=np.float32)
        measurement = measure_frame(image, variance, source_flags)
        self.assertEqual(measurement["flagged_fraction"], 0.0)

        clean = self._frame("SPHEREx-D1")
        flagged = self._frame("SPHEREx-D2", bad_fraction=0.5)
        ranking = rank_bandpasses([clean, flagged])
        self.assertEqual(ranking[0]["band"], "SPHEREx-D1")
        self.assertLess(ranking[1]["score"], ranking[0]["score"])

    def test_wavelength_lookup_bilinearly_interpolates(self) -> None:
        x_axis = np.array([0.0, 1.0])
        y_axis = np.array([0.0, 1.0])
        values = np.zeros((2, 2, 2))
        values[:, :, 0] = np.array([[0.0, 1.0], [2.0, 3.0]])
        values[:, :, 1] = 0.2
        wavelength, bandwidth = _interpolate_wavelength(
            x_axis, y_axis, values, 0.5, 0.25
        )
        self.assertAlmostEqual(wavelength, 1.0)
        self.assertAlmostEqual(bandwidth, 0.2)

    def test_band_explanation_describes_flags_as_a_proxy(self) -> None:
        result = explain_choice(
            {
                "band": "SPHEREx-D3",
                "snr": 4.2,
                "flagged_fraction": 0.1,
                "score": 3.78,
                "n_frames": 2,
            }
        )
        self.assertIn("quality proxy", result)
        self.assertIn("not a confirmed contaminant count", result)


if __name__ == "__main__":
    unittest.main()
