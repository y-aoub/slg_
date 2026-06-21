"""Interface en ligne de commande du scraper SeLoger.

Exemples :

    # nombre d'annonces de location à Lyon
    seloger count --place Lyon --rent

    # récupérer 3 pages d'appartements à louer à Paris 11 → JSON
    seloger search --place "Paris 11" --rent --types appartement --max-pages 3 -o out.json

    # résoudre un lieu en code INSEE
    seloger geocode "Bordeaux"

Le cookie Datadome est lu dans ``--datadome`` ou la variable ``SELOGER_DATADOME``.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys

from .config import ScraperConfig
from .enums import EstateType, ProjectType
from .exceptions import SelogerError
from .export import serialize
from .geocoding import geocode
from .query import Range, SearchQuery
from .scraper import SelogerScraper

_ESTATE_ALIASES = {
    "appartement": EstateType.APARTMENT,
    "appart": EstateType.APARTMENT,
    "maison": EstateType.HOUSE,
}


def _build_query(args: argparse.Namespace) -> SearchQuery:
    insee = list(args.insee or [])
    for place_name in args.place or []:
        matches = geocode(place_name, limit=1)
        if not matches:
            raise SelogerError(f"Lieu introuvable : {place_name!r}")
        insee.append(matches[0].insee_code)
        logging.info("Lieu %r → %s (%s)", place_name, matches[0].insee_code, matches[0].display)
    if not insee:
        raise SelogerError("Préciser au moins un lieu via --place ou --insee.")

    types = (
        [_ESTATE_ALIASES[t] for t in args.types]
        if args.types
        else [EstateType.APARTMENT, EstateType.HOUSE]
    )
    return SearchQuery(
        project=ProjectType.RENT if args.rent else ProjectType.BUY,
        estate_types=types,
        insee_codes=insee,
        enterprise=args.enterprise,
        price=Range(args.price_min, args.price_max),
        surface=Range(args.surface_min, args.surface_max),
        rooms_min=args.rooms_min,
    )


def _config(args: argparse.Namespace) -> ScraperConfig:
    kwargs = {}
    if args.datadome:
        kwargs["datadome_cookie"] = args.datadome
    if args.proxy:
        kwargs["proxy"] = args.proxy
    return ScraperConfig(**kwargs)


def cmd_geocode(args: argparse.Namespace) -> int:
    places = geocode(args.text)
    print(json.dumps([dataclasses.asdict(p) for p in places], ensure_ascii=False, indent=2))
    return 0


def cmd_count(args: argparse.Namespace) -> int:
    query = _build_query(args)
    with SelogerScraper(_config(args)) as scraper:
        print(json.dumps(scraper.count_breakdown(query), ensure_ascii=False, indent=2))
    return 0


def _resolve_format(args: argparse.Namespace) -> str:
    if args.format:
        return args.format
    if args.output and "." in args.output:
        ext = args.output.rsplit(".", 1)[-1].lower()
        if ext in ("json", "ndjson", "csv"):
            return ext
    return "json"


def cmd_search(args: argparse.Namespace) -> int:
    query = _build_query(args)
    with SelogerScraper(_config(args)) as scraper:
        listings = list(scraper.iter_listings(query, max_pages=args.max_pages))
    text = serialize(listings, _resolve_format(args), include_raw=args.raw)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print(f"{len(listings)} annonces écrites dans {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


def _add_search_filters(p: argparse.ArgumentParser) -> None:
    p.add_argument("--place", action="append", metavar="NOM", help="lieu (répétable)")
    p.add_argument("--insee", action="append", type=int, metavar="CODE", help="code INSEE (répétable)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--rent", action="store_true", help="location (défaut)")
    g.add_argument("--buy", dest="rent", action="store_false", help="achat")
    p.set_defaults(rent=True)
    p.add_argument("--types", action="append", choices=sorted(_ESTATE_ALIASES), help="type de bien (répétable)")
    p.add_argument("--enterprise", action="store_true", help="annonces pro uniquement")
    p.add_argument("--price-min", type=int)
    p.add_argument("--price-max", type=int)
    p.add_argument("--surface-min", type=int)
    p.add_argument("--surface-max", type=int)
    p.add_argument("--rooms-min", type=int)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seloger", description="Scraper d'annonces SeLoger.")
    parser.add_argument("--datadome", help="cookie Datadome (sinon env SELOGER_DATADOME)")
    parser.add_argument(
        "--proxy",
        help="proxy HTTP, ex. http://user:pass@host:port (sinon env SELOGER_PROXY)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    pg = sub.add_parser("geocode", help="résoudre un lieu en code INSEE")
    pg.add_argument("text")
    pg.set_defaults(func=cmd_geocode)

    pc = sub.add_parser("count", help="compter les annonces (API christie)")
    _add_search_filters(pc)
    pc.set_defaults(func=cmd_count)

    ps = sub.add_parser("search", help="récupérer les annonces (SSR)")
    _add_search_filters(ps)
    ps.add_argument("--max-pages", type=int, default=None, help="limite de pages")
    ps.add_argument("--raw", action="store_true", help="inclure la carte brute (JSON)")
    ps.add_argument("--format", choices=["json", "ndjson", "csv"], help="format (sinon déduit de -o)")
    ps.add_argument("-o", "--output", help="fichier de sortie (extension = format)")
    ps.set_defaults(func=cmd_search)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.func(args)
    except SelogerError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
