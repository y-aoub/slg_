"""Construction d'une requête de recherche SeLoger.

Une :class:`SearchQuery` se sérialise de deux façons :

* :meth:`to_querystring` — paramètres de ``list.htm`` (récupération SSR des annonces) ;
* :meth:`to_christie_body` — payload JSON de ``POST /search-bff/christie/count``.

Tous les paramètres ci-dessous ont été vérifiés en live contre ``christie/count``
et le SSR de ``list.htm`` (cf. RESEARCH.md) : ``projects``, ``types``, ``natures``,
``places (inseeCodes)``, ``enterprise``, ``price``, ``surface``, ``rooms``,
``bedrooms``, pagination.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import urlencode

from .enums import EstateType, Nature, ProjectType

# Le dernier "palier" de pièces/chambres est ouvert : 5 signifie « 5 et plus ».
# Un minimum se traduit donc par la liste [min, …, 5] (vérifié sur christie/count).
ROOM_PLUS_BUCKET = 5


def _min_to_buckets(minimum: int, cap: int = ROOM_PLUS_BUCKET) -> list[int]:
    """``3`` → ``[3, 4, 5]`` ; ``≥5`` → ``[5]`` (palier ouvert)."""
    return list(range(min(minimum, cap), cap + 1))


@dataclass(slots=True)
class Range:
    """Intervalle ``[min, max]`` ; les deux bornes sont optionnelles."""

    min: int | None = None
    max: int | None = None

    def to_dict(self) -> dict[str, int]:
        d: dict[str, int] = {}
        if self.min is not None:
            d["min"] = self.min
        if self.max is not None:
            d["max"] = self.max
        return d

    def to_qs(self) -> str:
        """Forme querystring SeLoger : ``min/max`` (NaN pour borne absente)."""
        lo = self.min if self.min is not None else "NaN"
        hi = self.max if self.max is not None else "NaN"
        return f"{lo}/{hi}"

    def is_empty(self) -> bool:
        return self.min is None and self.max is None


@dataclass(slots=True)
class SearchQuery:
    """Critères de recherche.

    Attributes:
        project: location ou achat (défaut : location).
        estate_types: types de biens recherchés (défaut : appartement + maison).
        natures: natures (défaut : ``[OLD, NEW, PROJECT]`` comme SeLoger).
        insee_codes: codes INSEE des communes/arrondissements (Paris = 75056).
        enterprise: recherche pro (``True``) ou particulier+pro (``False``).
        price: intervalle de prix (loyer CC ou prix de vente).
        surface: intervalle de surface en m².
        rooms_min: nombre de pièces minimum (5 = « 5 et plus »).
        bedrooms_min: nombre de chambres minimum (5 = « 5 et plus »).
    """

    project: ProjectType = ProjectType.RENT
    estate_types: list[EstateType] = field(
        default_factory=lambda: [EstateType.APARTMENT, EstateType.HOUSE]
    )
    natures: list[Nature] = field(
        default_factory=lambda: [Nature.OLD, Nature.NEW, Nature.PROJECT]
    )
    insee_codes: list[int] = field(default_factory=list)
    postal_codes: list[str] = field(default_factory=list)
    enterprise: bool = False
    price: Range = field(default_factory=Range)
    surface: Range = field(default_factory=Range)
    rooms_min: int | None = None
    bedrooms_min: int | None = None

    # ----- lieux ----------------------------------------------------------------

    def _places(self) -> list[dict]:
        """Construit le tableau ``places`` (inseeCodes et/ou postalCodes)."""
        place: dict = {}
        if self.insee_codes:
            place["inseeCodes"] = self.insee_codes
        if self.postal_codes:
            place["postalCodes"] = self.postal_codes
        return [place] if place else []

    # ----- sérialisation querystring (list.htm, SSR) ---------------------------

    def to_querystring(self, page: int = 1) -> str:
        """Construit la querystring de ``list.htm`` pour la page demandée."""
        places = self._places()
        params: list[tuple[str, str]] = [
            ("projects", str(int(self.project))),
            ("types", ",".join(str(int(t)) for t in self.estate_types)),
            ("natures", ",".join(str(int(n)) for n in self.natures)),
            ("places", json.dumps(places, separators=(",", ":"))),
            ("enterprise", "1" if self.enterprise else "0"),
            ("qsVersion", "1.0"),
        ]
        if not self.price.is_empty():
            params.append(("price", self.price.to_qs()))
        if not self.surface.is_empty():
            params.append(("surface", self.surface.to_qs()))
        if self.rooms_min is not None:
            params.append(("rooms", ",".join(map(str, _min_to_buckets(self.rooms_min)))))
        if self.bedrooms_min is not None:
            params.append(("bedrooms", ",".join(map(str, _min_to_buckets(self.bedrooms_min)))))
        if page > 1:
            params.append(("LISTING-LISTpg", str(page)))
        return urlencode(params, safe=",:[]{}\"/")

    # ----- sérialisation API christie (count) ----------------------------------

    def to_christie_body(self) -> dict:
        """Construit le payload JSON de ``POST /search-bff/christie/count``."""
        body: dict = {
            "enterprise": self.enterprise,
            "projects": [int(self.project)],
            "types": [int(t) for t in self.estate_types],
            "natures": [int(n) for n in self.natures],
            "places": self._places(),
            "textCriteria": [],
            "mandatoryCommodities": False,
        }
        if not self.price.is_empty():
            body["price"] = self.price.to_dict()
        if not self.surface.is_empty():
            body["surface"] = self.surface.to_dict()
        if self.rooms_min is not None:
            body["rooms"] = _min_to_buckets(self.rooms_min)
        if self.bedrooms_min is not None:
            body["bedrooms"] = _min_to_buckets(self.bedrooms_min)
        return body
