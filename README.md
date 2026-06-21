# seloger-scraper

Scraper Python pour les annonces immobilières [SeLoger](https://www.seloger.com/).

Récupère les annonces (prix, surface, pièces, DPE, contact, géoloc, photos…) et le
nombre de résultats d'une recherche, en s'appuyant sur :

- le **rendu serveur (SSR)** de `list.htm` pour les annonces (l'état complet est
  embarqué dans la page) ;
- l'**API interne `christie/count`** pour le comptage rapide ;
- l'**autocomplétion** du groupe SeLoger pour résoudre un lieu en code INSEE.

> Détails de la rétro-ingénierie : voir [`RESEARCH.md`](RESEARCH.md).

## Installation

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .          # + httpx
# dev : pip install -e ".[dev]" puis pytest
```

## Le cookie Datadome (indispensable)

SeLoger est protégé par **Datadome**. Chaque requête doit porter un cookie
`datadome` valide (≈128 caractères), qui sert aussi de header `x-datadome-clientid`
sur les appels API. Récupère-le depuis une session navigateur **loggée et non
bloquée** (console : `document.cookie`), puis fournis-le :

```bash
export SELOGER_DATADOME='collé-ici'
```

Le cookie **tourne / expire** : en cas de blocage le scraper lève `DatadomeBlocked`
— il faut alors le rafraîchir. (Le geocoding, lui, ne nécessite pas ce cookie.)

## Proxy (optionnel)

Comme dans [`lbc`](https://github.com/y-aoub/lbc_), un proxy HTTP se configure via une
dataclass `Proxy` (ou une URL, ou l'env `SELOGER_PROXY`) :

```python
from seloger import ScraperConfig, Proxy

config = ScraperConfig(proxy=Proxy(host="1.2.3.4", port=8080, username="u", password="p"))
# équivalent : ScraperConfig(proxy="http://u:p@1.2.3.4:8080")
```

> ⚠️ Datadome lie le cookie à la session/IP d'origine : router le trafic via un proxy
> d'une autre IP peut invalider le cookie. Utilise un proxy cohérent avec la session
> qui a généré le cookie.

## Utilisation — Python

```python
from seloger import SelogerScraper, ScraperConfig, SearchQuery, Range, resolve_insee
from seloger.enums import ProjectType, EstateType

query = SearchQuery(
    project=ProjectType.RENT,                 # location (BUY = achat)
    estate_types=[EstateType.APARTMENT],
    insee_codes=[resolve_insee("Paris 11")],  # 750111
    price=Range(max=2000),
)

with SelogerScraper(ScraperConfig()) as scraper:   # lit SELOGER_DATADOME (+ SELOGER_PROXY)
    print(scraper.count(query))                     # ex. 1 234

    for listing in scraper.iter_listings(query, max_pages=3):
        print(listing.id, listing.city, listing.pricing.display_price,
              listing.surface, "m²", listing.rooms, "pièces")
```

## Utilisation — CLI

```bash
# Résoudre un lieu -> code(s) INSEE
seloger geocode "Bordeaux"

# Compter les annonces (API christie, 1 requête)
seloger count --place Lyon --rent

# Récupérer les annonces (SSR, paginé) — format déduit de l'extension
seloger search --place "Paris 11" --rent --types appartement \
    --price-max 2000 --rooms-min 2 --max-pages 3 -o annonces.csv

# …ou JSON / NDJSON explicite
seloger search --place Lyon --rent --format ndjson -o annonces.ndjson
```

(`seloger` = `python -m seloger.cli`. Options : `--insee`, `--buy`, `--enterprise`,
`--surface-min/max`, `--rooms-min`, `--format {json,ndjson,csv}`, `--proxy URL`, `--raw`, `-v`.
Les filtres prix/surface/pièces/chambres sont vérifiés en live ; `--rooms-min 5`
signifie « 5 pièces et plus ».)

## Architecture

| Module | Rôle |
|---|---|
| `config.py` | `ScraperConfig` (cookie Datadome, UA, délais, retries) |
| `enums.py` | codes `ProjectType`, `EstateType`, `Nature`, `SortField` |
| `query.py` | `SearchQuery` → querystring `list.htm` **et** body `christie/count` |
| `geocoding.py` | lieu (texte) → `Place` (code INSEE) via l'autocomplétion |
| `client.py` | client `httpx` : Datadome, retries, throttling, détection de blocage |
| `parser.py` | extraction de `window["initialData"]` → `SearchPage` |
| `models.py` | `Listing` / `Pricing` / `Contact` / `Position` (parsing défensif) |
| `scraper.py` | API haut niveau : `count()`, `search_page()`, `iter_listings()` |
| `cli.py` | interface ligne de commande |

## Limites connues

- **Plafond de 2 500 résultats** par recherche (imposé par SeLoger). Au-delà,
  affine les filtres (arrondissement, prix, surface) — un avertissement est loggé.
- L'endpoint `christie/search-full` renvoie 404 hors serveur : les annonces passent
  donc par le SSR (1 requête HTML par page de 25).
- Filtres prix / surface / pièces : marqués *best-effort* (vérifier le mapping exact
  des paramètres dans `query.py`).
- Soyez **respectueux** : délais entre requêtes (réglables via `min_delay`/`max_delay`),
  usage raisonnable, conformité aux CGU de SeLoger.

## Tests

```bash
pytest -q          # parser, query, models (sans réseau)
```

## Licence

MIT.
