# nasa-space-apps-spherex
Interactive visualization and time-lapse tool for NASA SPHEREx data. Built with Python and Streamlit for the NASA Space Apps Challenge 2026.

## Live data

The app queries IRSA's SIA2 service for SPHEREx Level-2 Spectral Image MEFs in
the DR1 and QR3 wide-survey collections. Deep-field collections are optional.
It downloads spatial cutouts and reads the `IMAGE`, `FLAGS`, `VARIANCE`, and
`WCS-WAVE` FITS extensions. This requires an internet connection; the app does
not bundle observations.

## Method and limits

- Custom-coordinate searches keep the cutout and aperture at one fixed
  coordinate; a moving source can leave that aperture over time.
- The Barnard's Star preset keeps the cutout centered at the Gaia EDR3
  J2016.0 reference position and moves the aperture and red cross to the
  proper-motion-predicted position for each observation MJD. The cross is a
  prediction, not a measured centroid or a confirmed detection. This single
  star-motion preset is not a general ephemeris service.
- Aperture-mean surface brightness is measured within 2 pixels, with a local
  background ring from 8 to 20 pixels (reduced for small cutouts).
- Uncertainty is the larger of the variance-derived aperture uncertainty and
  the local-background scatter estimate.
- Image flag values `0`, `2`, and `2097152` are accepted following IRSA's
  SPHEREx source-discovery example; other values are excluded. The aperture's
  remaining flagged-pixel fraction is a quality proxy, not a confirmed
  contaminant count. The band score is
  `max(0, median S/N) * (1 - median flagged fraction)`.
- Wavelength is interpolated from `WCS-WAVE` for visualization. The spectrum
  combines observations from different epochs and is an aperture-mean
  surface-brightness display, not a simultaneous calibrated source spectrum.
  Variable or moving sources need independent scientific validation.
- Results are candidates for investigation, never certain identifications.

## Data references

- SPHEREx DR1 Spectral Images, DOI [10.26131/IRSA678](https://doi.org/10.26131/IRSA678):
  [IRSA DR1 overview](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html).
- SPHEREx QR3 Spectral Images, DOI [10.26131/IRSA662](https://doi.org/10.26131/IRSA662):
  [IRSA Quick Release overview](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_qr.html).
- [SPHEREx Archive User Guide](https://irsa.ipac.caltech.edu/spherex-archive-documentation/):
  [SIA2 and cutout access](https://irsa.ipac.caltech.edu/spherex-archive-documentation/spherex-data-access/)
  and [FITS product details](https://irsa.ipac.caltech.edu/spherex-archive-documentation/spherex-data-products/).
- [IRSA SIA2 documentation](https://irsa.ipac.caltech.edu/ibe/sia.html) and
  [Astroquery IRSA documentation](https://docs.astropy.org/projects/astroquery/en/latest/ipac/irsa/irsa.html).
- [IRSA's SPHEREx source-discovery tutorial](https://caltech-ipac.github.io/irsa-tutorials/spherex-source-discovery-tool-demo/),
  including its image-flag masking example.
- [Astropy FITS and WCS documentation](https://docs.astropy.org/en/stable/io/fits/).
- Barnard's Star coordinates, proper motion, parallax, and radial velocity from
  [SIMBAD/Sesame](https://cds.unistra.fr/cgi-bin/nph-sesame/-ox/S?Barnard%27s%20Star);
  the Gaia EDR3 catalog reference epoch is J2016.0
  ([ESA Gaia EDR3](https://www.cosmos.esa.int/web/gaia/early-data-release-3)).

SPHEREx acknowledgement requested by IRSA: “This publication makes use of
data products from the Spectro-Photometer for the History of the Universe,
Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of
the Jet Propulsion Laboratory and the California Institute of Technology,
and is funded by the National Aeronautics and Space Administration.”

## AI use disclosure

Generative AI assisted with software implementation and reference checking.
The team is responsible for reviewing the code and validating scientific
interpretations. No generated or simulated observations are substituted for
SPHEREx archive data.
