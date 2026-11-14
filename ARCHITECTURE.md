# Architecture

Ce projet est un outil Streamlit de visualisation temporelle des images
spectrales SPHEREx.

- `app.py` interroge IRSA SIA2, télécharge des vignettes FITS Level 2,
  mesure le rapport signal/bruit et affiche les observations.
- `utils/spherex_loader.py` est un ancien squelette; l'application actuelle
  utilise directement l'API Astroquery dans `app.py`.

L'application nécessite une connexion réseau pour interroger IRSA. Les
longueurs d'onde affichées sont interpolées depuis l'extension `WCS-WAVE` et
sont destinées à la visualisation. Le score de bande utilise la fraction des
pixels d'ouverture ayant un indicateur FLAGS non nul comme indicateur qualité
conservateur; cette fraction n'est pas une mesure d'une source contaminante.