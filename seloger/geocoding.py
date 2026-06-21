"""Résolution d'un lieu (texte) vers son code INSEE SeLoger.

Utilise l'autocomplétion publique du groupe SeLoger
(``autocomplete.svc.groupe-seloger.com``), qui ne nécessite PAS le cookie Datadome.
Le champ utile pour la recherche est ``Params.ci`` (code INSEE format SeLoger,
ex. Paris = ``750056`` = département 2 chiffres + commune 4 chiffres).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from .config import DEFAULT_USER_AGENT

AUTOCOMPLETE_URL = (
    "https://autocomplete.svc.groupe-seloger.com/api/v3.0/auto/complete/fra/63/10/8/SeLoger"
)


@dataclass(slots=True)
class Place:
    """Une suggestion de lieu.

    Attributes:
        type: "Departement", "Group", "Ville", "Quartier"…
        display: libellé lisible (ex. "Paris 16ème (75016, 75116)").
        insee_code: code INSEE SeLoger (``Params.ci``), à passer à
            ``SearchQuery.insee_codes`` ; ``None`` pour un département.
        zips: codes postaux associés.
        lat / lng: coordonnées (si fournies).
    """

    type: str
    display: str
    insee_code: int | None
    zips: list[str]
    lat: float | None = None
    lng: float | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Place":
        params = d.get("Params") or {}
        meta = d.get("Meta") or {}
        ci = params.get("ci")
        lat = params.get("Latitude")
        lng = params.get("Longitude")
        return cls(
            type=d.get("Type", ""),
            display=d.get("Display", ""),
            insee_code=int(ci) if ci else None,
            zips=list(meta.get("Zips") or []),
            lat=float(lat) if lat else None,
            lng=float(lng) if lng else None,
        )


def geocode(
    text: str,
    *,
    limit: int = 10,
    client: httpx.Client | None = None,
    timeout: float = 15.0,
) -> list[Place]:
    """Retourne les lieux correspondant à ``text`` (villes, arrondissements…).

    Ne garde que les suggestions disposant d'un code INSEE (exploitable par la
    recherche). Passe un ``client`` httpx pour réutiliser une connexion.
    """
    owns_client = client is None
    client = client or httpx.Client(
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "*/*",
            "Origin": "https://www.seloger.com",
            "Referer": "https://www.seloger.com/",
        },
        timeout=timeout,
    )
    try:
        resp = client.get(AUTOCOMPLETE_URL, params={"text": text})
        resp.raise_for_status()
        places = (resp.json() or {}).get("Places") or []
        results = [Place.from_dict(p) for p in places]
        return [p for p in results if p.insee_code is not None][:limit]
    finally:
        if owns_client:
            client.close()


def resolve_insee(text: str, **kwargs) -> int | None:
    """Raccourci : code INSEE de la meilleure correspondance pour ``text``."""
    places = geocode(text, **kwargs)
    return places[0].insee_code if places else None
