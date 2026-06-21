"""Extraction et parsing de l'état SSR de SeLoger.

La page ``list.htm`` embarque tout l'état initial dans :

    <script>window["initialData"] = JSON.parse("<chaîne JSON doublement encodée>")</script>

On récupère le littéral chaîne passé à ``JSON.parse`` (qui est lui-même une chaîne
JSON valide), puis on le décode deux fois pour obtenir l'objet.
"""

from __future__ import annotations

import json
import re

from .exceptions import ParseError
from .models import Listing, Pagination, SearchPage

# Capture le littéral chaîne (guillemets inclus) passé à JSON.parse, en gérant
# correctement les échappements internes (\" \\ \uXXXX …).
_INITIAL_DATA_RE = re.compile(
    r'window\["initialData"\]\s*=\s*JSON\.parse\(("(?:\\.|[^"\\])*")\)'
)

# Cartes réellement exploitables (les pubs ont cardType "native", "ad", etc.).
_REAL_CARD_TYPE = "classified"


def extract_initial_data(html: str) -> dict:
    """Extrait et décode l'objet ``initialData`` depuis le HTML SSR.

    Raises:
        ParseError: si le motif n'est pas trouvé ou que le JSON est invalide.
    """
    match = _INITIAL_DATA_RE.search(html)
    if not match:
        raise ParseError(
            'Motif window["initialData"] introuvable : page de challenge Datadome, '
            "structure modifiée, ou réponse non-HTML."
        )
    try:
        inner_json = json.loads(match.group(1))  # littéral JS -> texte JSON
        return json.loads(inner_json)            # texte JSON -> objet
    except json.JSONDecodeError as exc:  # pragma: no cover - défensif
        raise ParseError(f"Échec du décodage de initialData : {exc}") from exc


def iter_raw_cards(data: dict) -> list[dict]:
    """Renvoie les cartes réelles (hors pubs) de ``data.cards.list``."""
    cards = (data.get("cards") or {}).get("list") or []
    return [
        c
        for c in cards
        if isinstance(c.get("id"), int) and c.get("cardType") == _REAL_CARD_TYPE
    ]


def parse_listings(data: dict) -> list[Listing]:
    """Parse toutes les annonces réelles d'un objet ``initialData``."""
    return [Listing.from_card(c) for c in iter_raw_cards(data)]


def parse_pagination(data: dict) -> Pagination:
    nav = (data.get("navigation") or {}).get("pagination") or {}
    return Pagination(
        page=int(nav.get("page", 1)),
        results_per_page=int(nav.get("resultsPerPage", 0)),
        max_results=int(nav.get("maxResults", 0)),
    )


def parse_search_page(html: str) -> SearchPage:
    """Parse un HTML ``list.htm`` complet en :class:`SearchPage`."""
    data = extract_initial_data(html)
    counts = (data.get("navigation") or {}).get("counts") or {}
    aggs = counts.get("aggregations") or {}
    return SearchPage(
        listings=parse_listings(data),
        total_count=int(counts.get("count", 0)),
        pagination=parse_pagination(data),
        private_seller_count=aggs.get("privateSeller"),
        professional_seller_count=aggs.get("professionalSeller"),
    )
