"""Énumérations des codes utilisés par la recherche SeLoger.

Ces codes correspondent aux paramètres de la querystring de ``list.htm`` et
aux champs du ``christieModel`` (cf. RESEARCH.md). Les valeurs incertaines sont
annotées ; elles ont été déduites de l'observation et restent à confirmer.
"""

from __future__ import annotations

from enum import Enum, IntEnum


class ProjectType(IntEnum):
    """Type de projet (param ``projects``)."""

    RENT = 1  # location
    BUY = 2   # achat


class EstateType(IntEnum):
    """Type de bien (param ``types`` / ``estateTypeId``)."""

    APARTMENT = 1  # appartement
    HOUSE = 2      # maison
    # 3=parking, 4=terrain, 5=boutique/local, 6=bureau, 9=immeuble, 10=château,
    # 11=hôtel particulier, 13=loft, 14=programme neuf — à confirmer.


class Nature(IntEnum):
    """Nature du bien (param ``natures``).

    Valeurs déduites ; SeLoger envoie typiquement ``[1, 2, 4]`` par défaut.
    """

    OLD = 1       # ancien
    NEW = 2       # neuf
    VIAGER = 3    # viager
    PROJECT = 4   # projet de construction / programme


class SortField(str, Enum):
    """Champs de tri (``sort`` du christieModel).

    Le tri par défaut de SeLoger est la pertinence (``sort=[]``).
    """

    PRICE = "price"
    SURFACE = "surface"
    PUBLICATION_DATE = "pubDate"
    SQUARE_METER_PRICE = "sqrMeterPrice"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"
