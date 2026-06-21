"""Exceptions du scraper SeLoger."""

from __future__ import annotations


class SelogerError(Exception):
    """Erreur de base pour toutes les erreurs du scraper."""


class DatadomeBlocked(SelogerError):
    """Levée quand Datadome bloque la requête (challenge / 403).

    Indique que le cookie ``datadome`` est invalide, expiré, ou que le
    comportement a été jugé robotique. Il faut rafraîchir le cookie depuis
    une session navigateur (cf. ``ScraperConfig.datadome_cookie``).
    """


class ParseError(SelogerError):
    """Le HTML SSR ne contenait pas l'état attendu (``window["initialData"]``)."""


class ListingUnavailable(SelogerError):
    """L'annonce n'existe plus / est introuvable (HTTP 404 ou 410 « supprimée »).

    Ces annonces apparaissent encore dans l'index de recherche mais leur page de
    détail renvoie 410 (« Annonce supprimée »). Il n'y a pas de détail à récupérer.
    """


class RateLimited(SelogerError):
    """Le serveur a répondu 429 (trop de requêtes)."""
