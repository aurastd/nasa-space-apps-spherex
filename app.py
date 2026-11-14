"""Interface Streamlit d'Evarinya (responsabilité de Junior).

Les accès aux données passent exclusivement par le module evarinya.
"""

import matplotlib.pyplot as plt
import streamlit as st

import evarinya


def _show_spectrum(spectrum: evarinya.Spectrum) -> None:
	"""Trace le spectre normalisé par le module de données."""
	figure, axis = plt.subplots(figsize=(8, 3.5))
	axis.plot(spectrum["wavelength_um"], spectrum["flux"], color="#6c63ff")

	uncertainty = spectrum.get("uncertainty")
	if uncertainty is not None:
		axis.fill_between(
			spectrum["wavelength_um"],
			spectrum["flux"] - uncertainty,
			spectrum["flux"] + uncertainty,
			alpha=0.2,
			color="#6c63ff",
		)

	axis.set(xlabel="Longueur d'onde (µm)", ylabel="Flux", title="Spectre SPHEREx")
	axis.grid(alpha=0.2)
	st.pyplot(figure, clear_figure=True)
	plt.close(figure)


st.set_page_config(page_title="Evarinya | SPHEREx", page_icon="✨", layout="wide")
st.title("Evarinya — explorer le ciel avec SPHEREx ✨")
st.write("Explorez les observations autour d'une position céleste et comparez-les dans le temps.")

with st.sidebar.form("search_form"):
	st.subheader("Position céleste")
	ra = st.number_input("Ascension droite (°)", min_value=0.0, max_value=360.0, value=269.45)
	dec = st.number_input("Déclinaison (°)", min_value=-90.0, max_value=90.0, value=4.69)
	fov = st.number_input("Champ de vue (°)", min_value=0.001, value=0.1, format="%.3f")
	submitted = st.form_submit_button("Rechercher", type="primary")

if submitted:
	try:
		frames = evarinya.get_frames(ra, dec, fov)
		available_bands = evarinya.get_all_bands()
		rankings = evarinya.rank_bandpasses(frames)

		if not frames:
			st.info("Aucune vignette trouvée pour cette position.")
		else:
			st.caption("Bandes disponibles : " + ", ".join(available_bands))
			if rankings:
				best_band = rankings[0]
				st.success(evarinya.explain_choice(best_band))

			st.subheader("Time-lapse — observations disponibles")
			for frame in frames:
				st.image(
					frame["image"],
					caption=f"{frame['observation_time']} · bande {frame['band']}",
					use_container_width=True,
				)

			# TODO(Junior) : connecter la sélection/clic sur une source dans
			# le time-lapse. Le composant interactif devra fournir (ra, dec).
			selected_point: tuple[float, float] | None = None
			if selected_point is not None:
				spectrum = evarinya.get_spectrum(*selected_point)
				_show_spectrum(spectrum)
				st.warning(
					"Suggestion indicative : candidat à examiner, pas une identification."
				)
	except NotImplementedError as error:
		st.info(f"Le squelette de l'interface est prêt ; le module de données reste à implémenter. {error}")
	except Exception as error:  # À remplacer par des erreurs applicatives ciblées.
		st.error(f"La recherche a échoué : {error}")
else:
	st.info("Saisissez des coordonnées puis lancez une recherche.")