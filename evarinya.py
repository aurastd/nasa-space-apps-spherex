"""Recherche et traitement des données SPHEREx (responsabilité de Diane).

Ce module est l'unique frontière entre l'interface et IRSA. Il doit convertir
les réponses de l'archive en structures stables documentées ci-dessous.
"""

from __future__ import annotations

from typing import TypedDict

import numpy as np


class Frame(TypedDict):
    """Vignette normalisée destinée à l'interface."""

    image: np.ndarray
    observation_time: str
    band: str


class BandScore(TypedDict):
    """Mesures et rang d'une bande ; les métriques sont à définir sur DR1/QR3."""

    band: str
    snr: float
    contamination: float
    score: float


class Spectrum(TypedDict):
    """Spectre normalisé, sur des axes compatibles entre les observations."""

    wavelength_um: np.ndarray
    flux: np.ndarray
    uncertainty: np.ndarray | None


def get_frames(ra: float, dec: float, fov: float) -> list[Frame]:
    """Recherche et récupère les vignettes autour de la cible.

    Args:
        ra: Ascension droite en degrés, dans [0, 360].
        dec: Déclinaison en degrés, dans [-90, 90].
        fov: Largeur du champ de vue en degrés.

    Returns:
        Images triées par date, avec une date et une bande par image.

    TODO(Diane): interroger IRSA (DR1 et QR3), gérer les erreurs réseau,
    normaliser les métadonnées et privilégier le cache local pour la démo.
    """
    raise NotImplementedError("get_frames doit être implémentée avec Astroquery/IRSA")


def get_all_bands() -> list[str]:
    """Retourne les bandes disponibles dans les collections prises en charge.

    TODO(Diane): déterminer la liste à partir des produits DR1/QR3 plutôt
    que de supposer un nombre ou un nom de bande fixe.
    """
    raise NotImplementedError("get_all_bands doit être implémentée")


def rank_bandpasses(frames: list[Frame]) -> list[BandScore]:
    """Classe les bandes par qualité, en tenant compte du bruit et des artefacts.

    Le score doit documenter explicitement la convention de contamination et
    la stratégie de calcul du rapport signal/bruit. Le premier élément est le
    meilleur candidat ; une liste vide signifie qu'aucune bande n'est exploitable.

    TODO(Diane): vérifier les champs de qualité officiellement documentés
    dans les produits SPHEREx sélectionnés avant de calculer les métriques.
    """
    raise NotImplementedError("rank_bandpasses doit être implémentée")


def explain_choice(best_band: BandScore) -> str:
    """Produit une explication courte, fondée sur les métriques du classement.

    TODO(Diane): expliquer le compromis S/B-contamination avec des seuils
    et un vocabulaire compréhensible ; ne pas présenter le résultat comme certain.
    """
    raise NotImplementedError("explain_choice doit être implémentée")


def get_spectrum(ra: float, dec: float) -> Spectrum:
    """Extrait le spectre à la position sélectionnée.

    TODO(Diane): définir l'appariement spatial, la gestion des observations
    multi-époques, les unités et la propagation des incertitudes.
    """
    raise NotImplementedError("get_spectrum doit être implémentée")