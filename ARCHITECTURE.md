# Architecture

Evarínya's Streamlit interface is in `utils/app.py`.

- `utils/spherex_data.py` handles IRSA queries, SPHEREx downloads, processing, caching, and frame construction.
- `utils/presets.py` defines the example targets used by the app.
- `utils/prefetch.py` optionally downloads preset data for offline use.
- `tests/` covers data-query behavior and image candidate selection.