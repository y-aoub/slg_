"""Modèles de données des annonces SeLoger.

Le parsing est *défensif* : les champs absents/incohérents donnent ``None`` plutôt
que de lever une exception, car le schéma SeLoger varie selon le type de carte et
la business unit (SeLoger, BellesDemeures, Logic-Immo…).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import PHOTO_CDN


def _to_int(value: Any) -> int | None:
    """Convertit en int en tolérant les chaînes ('7 980', '281 m²'…)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        # NB: str.isdigit() est vrai pour '²' (exposant) — on se limite à l'ASCII.
        digits = "".join(ch for ch in value if ch in "0123456789")
        return int(digits) if digits else None
    return None


@dataclass(slots=True)
class Pricing:
    raw_price: int | None = None          # prix brut (loyer CC ou prix de vente)
    display_price: str | None = None      # ex. "7 980 €"
    square_meter_price: str | None = None  # ex. "28 €"
    price_note: str | None = None         # ex. "cc" (charges comprises)
    is_lifetime: bool = False             # viager

    @classmethod
    def from_dict(cls, d: dict | None) -> "Pricing":
        d = d or {}
        return cls(
            raw_price=_to_int(d.get("rawPrice")),
            display_price=d.get("price"),
            square_meter_price=d.get("squareMeterPrice"),
            price_note=d.get("priceNote"),
            is_lifetime=bool(d.get("lifetime", False)),
        )


@dataclass(slots=True)
class Contact:
    agency_id: int | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    is_private_seller: bool = False
    agency_page: str | None = None

    @classmethod
    def from_dict(cls, d: dict | None) -> "Contact":
        d = d or {}
        return cls(
            agency_id=_to_int(d.get("agencyId")),
            name=d.get("contactName"),
            phone=d.get("phoneNumber"),
            email=d.get("email"),
            is_private_seller=bool(d.get("isPrivateSeller", False)),
            agency_page=d.get("agencyPage"),
        )


@dataclass(slots=True)
class Position:
    lat: float | None = None
    lng: float | None = None

    @classmethod
    def from_value(cls, value: Any) -> "Position | None":
        # SeLoger renvoie ``0`` quand la géoloc est absente, sinon un objet.
        if not isinstance(value, dict):
            return None
        lat = value.get("lat") or value.get("latitude")
        lng = value.get("lng") or value.get("longitude")
        if lat is None and lng is None:
            return None
        return cls(lat=lat, lng=lng)


@dataclass(slots=True)
class Listing:
    """Une annonce immobilière SeLoger normalisée."""

    id: int
    title: str | None = None
    estate_type: str | None = None        # libellé ("Appartement")
    estate_type_id: int | None = None
    transaction_type_id: int | None = None  # 1=location, 2=vente
    nature: int | None = None
    pricing: Pricing = field(default_factory=Pricing)
    contact: Contact = field(default_factory=Contact)
    city: str | None = None
    district: str | None = None
    zip_code: str | None = None
    rooms: int | None = None
    bedrooms: int | None = None
    surface: int | None = None            # m²
    epc: str | None = None                # DPE (lettre A–G)
    description: str | None = None
    url: str | None = None                # classifiedURL
    photo_paths: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    position: Position | None = None
    is_new: bool = False
    is_exclusive: bool = False
    business_unit: str | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_card(cls, card: dict) -> "Listing":
        """Construit une :class:`Listing` depuis une carte ``cards.list[i]``."""
        return cls(
            id=int(card["id"]),
            title=card.get("title"),
            estate_type=card.get("estateType"),
            estate_type_id=_to_int(card.get("estateTypeId")),
            transaction_type_id=_to_int(card.get("transactionTypeId")),
            nature=_to_int(card.get("nature")),
            pricing=Pricing.from_dict(card.get("pricing")),
            contact=Contact.from_dict(card.get("contact")),
            city=card.get("cityLabel"),
            district=card.get("districtLabel"),
            zip_code=card.get("zipCode"),
            rooms=_to_int(card.get("rooms")),
            bedrooms=_to_int(card.get("bedroomCount")),
            surface=_to_int(card.get("surface")),
            epc=card.get("epc"),
            description=card.get("description"),
            url=card.get("classifiedURL"),
            photo_paths=list(card.get("photos") or []),
            tags=list(card.get("tags") or []),
            position=Position.from_value(card.get("position")),
            is_new=bool(card.get("isNew", False)),
            is_exclusive=bool(card.get("isExclusive", False)),
            business_unit=card.get("businessUnit"),
            raw=card,
        )

    def photo_urls(self, width: int = 800) -> list[str]:
        """URLs CDN absolues des photos (largeur ``width`` px).

        Les chemins bruts sont du type ``/0/x/g/e/<hash>.jpg`` ; le template
        ``v.seloger.com/s/width/<W>`` est *best-effort* (déduit du logo agence).
        """
        return [f"{PHOTO_CDN}/s/width/{width}{p}" for p in self.photo_paths]

    def to_dict(self, *, include_raw: bool = False) -> dict:
        """Représentation sérialisable JSON (sans la carte brute par défaut)."""
        return {
            "id": self.id,
            "title": self.title,
            "estate_type": self.estate_type,
            "transaction_type_id": self.transaction_type_id,
            "price": self.pricing.raw_price,
            "price_display": self.pricing.display_price,
            "price_note": self.pricing.price_note,
            "square_meter_price": self.pricing.square_meter_price,
            "surface": self.surface,
            "rooms": self.rooms,
            "bedrooms": self.bedrooms,
            "epc": self.epc,
            "city": self.city,
            "district": self.district,
            "zip_code": self.zip_code,
            "lat": self.position.lat if self.position else None,
            "lng": self.position.lng if self.position else None,
            "contact_name": self.contact.name,
            "contact_phone": self.contact.phone,
            "is_private_seller": self.contact.is_private_seller,
            "is_new": self.is_new,
            "is_exclusive": self.is_exclusive,
            "url": self.url,
            "photos": self.photo_urls(),
            "tags": self.tags,
            **({"raw": self.raw} if include_raw else {}),
        }


@dataclass(slots=True)
class Pagination:
    page: int
    results_per_page: int
    max_results: int


@dataclass(slots=True)
class SearchPage:
    """Résultat d'une page de recherche."""

    listings: list[Listing]
    total_count: int
    pagination: Pagination
    private_seller_count: int | None = None
    professional_seller_count: int | None = None
