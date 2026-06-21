# SeLoger — rétro-ingénierie de l'API (notes)

> Capturé le 2026-06-21 via chrome-devtools MCP sur une session Chrome Windows loggée
> (passe Datadome). Recherche de référence : **location à Paris** (`projects=1`, `types=1,2`,
> `natures=1,2,4`, `inseeCodes=[750056]`) → 5 931 annonces.

## Architecture côté SeLoger

SPA "agatha" rendu **côté serveur (SSR)**. La page `list.htm` renvoie un HTML qui embarque
tout l'état initial (annonces incluses) dans :

```html
<script>window["initialData"] = JSON.parse("{...JSON doublement encodé...}")</script>
```

`window.getState()` / `window.initialData` exposent ce même objet, de clés :
`display, cards, navigation, SEO, tracking, adverts, bookmarks, failure, engine`.

## Sources de données

### 1. Listings → SSR de `list.htm` (méthode retenue)
- `GET https://www.seloger.com/list.htm?<querystring>&LISTING-LISTpg=<page>`
- Le tableau d'annonces est dans `initialData.cards.list`.
- **Pagination** : param `LISTING-LISTpg=N` (navigation/re-SSR complète). 25 résultats utiles/page,
  **plafond `maxResults = 2500`** (≈100 pages) — au-delà il faut affiner les filtres.
- `cards.list` mélange de vraies annonces et de cartes pub : filtrer sur `typeof id === 'number'`
  (les pubs ont `id` string type `"native1"`). Cf. champ `cardType`.

Extraction Python (double décodage) :
```python
import re, json
rx = r'window\["initialData"\]\s*=\s*JSON\.parse\(("(?:\\.|[^"\\])*")\)'
m = re.search(rx, html)
data = json.loads(json.loads(m.group(1)))   # str JS -> texte JSON -> objet
cards = [c for c in data["cards"]["list"] if isinstance(c.get("id"), int)]
```

### 2. Comptage → API JSON directe (`christie/count`)
- `POST https://www.seloger.com/search-bff/christie/count`
- Body (sous-ensemble du `christieModel`) :
  ```json
  {"enterprise":false,"projects":[1],"types":[2,1],
   "places":[{"inseeCodes":[750056]}],"textCriteria":[],"mandatoryCommodities":false}
  ```
- Réponse : `{"nb":5931,"nbgeoloc":0,"aggregations":{"privateSeller":759,"professionalSeller":5172}}`

### 3. Endpoints connus (`initialData.engine.API`)
| clé | chemin |
|---|---|
| christie | `/search-bff/christie` |
| count | `/search-bff/christie/count` |
| searchFull | `/search-bff/christie/search-full` — **404 côté navigateur (server-side only)** |
| serialize | `/search-bff/christie/2.0/serialize` |
| addressAutocomplete | `/search-bff/api/geocoding/search?limit=4&countryCode=fr&caller=SeLoger` |
| locationAutocomplete | `https://autocomplete.svc.groupe-seloger.com/api/v3.0/auto/complete/fra/63/10/8/SeLoger` |
| externalData | `/search-bff/api/externaldata` |

> `search-full` renvoie 404 en fetch navigateur → on ne peut PAS récupérer les listings par
> API JSON directe. D'où le choix du SSR pour les annonces.

## Le `christieModel` (modèle de recherche complet)
Champs (tous nullable) : `from, size, projects, agencyIds, types, propertySubTypes, natures,
places[], searchAreas, isochronePoints, proximities, geoloc, geoPrecision, pointOfInterests,
geoZone, price, sqrMeterPrice, groundSurface, surface, bedrooms, rooms, bedroom, room, sort[],
floor, floors[], mandatoryCommodities, lastFloor, hearth, guardian, view, ...`

Correspondance querystring (`list.htm`) :
- `projects` : 1=location, 2=achat (vérifier 5=achat? À confirmer)
- `types` : 1=appartement, 2=maison (idtypebien)
- `natures` : 1,2,4 (neuf/ancien/viager… à confirmer)
- `places` : `[{"inseeCodes":[750056]}]` (Paris = INSEE 75056 ; codes INSEE, pas code postal)
- `enterprise` : 0/1
- `LISTING-LISTpg` : page

`places` accepte aussi `postalCodes`, `cities`, `divisions`, `districts`, etc.

### Filtres vérifiés (live, contre `christie/count` + SSR)
| filtre | querystring `list.htm` | body `christie` | exemple Paris loc. (5931 → ) |
|---|---|---|---|
| prix | `price=min/max` (`NaN` si borne vide) | `"price":{"min","max"}` | `price=NaN/1500` → 2305 |
| surface | `surface=min/max` | `"surface":{"min","max"}` | `surface=50/200` → 2557 |
| pièces | `rooms=3,4,5` | `"rooms":[3,4,5]` | `rooms=3,4,5` → 2284 |
| chambres | `bedrooms=2,3,4,5` | `"bedrooms":[2,3,4,5]` | → 2284 |

- **pièces / chambres = LISTES, pas des ranges** : `{"min":3}` renvoie **HTTP 400**.
- La valeur **5 est un palier ouvert (« 5 et plus »)** : `rooms:[5]` == `rooms:[5,6,7,…]`.
  Un minimum N se traduit donc par `[N, …, 5]`.
- Formats ignorés silencieusement (à NE PAS utiliser) : `price:{from,to}`, `priceMin/priceMax`,
  `surface:{from,to}`.

## Schéma d'une annonce (`cards.list[i]`)
40 champs : `id, cardType, publicationId, highlightingLevel, businessUnit, photosQty, photos[],
title, estateType, estateTypeId, transactionTypeId, nature, pricing, contact, tags[], isExclusive,
cityLabel, districtLabel, zipCode, description, videoURL, virtualVisitURL, housingBatch,
classifiedURL, rooms, surface, optionalCriteria, missingOptionalCriteria, transport, earlyAccess,
forcedIntermediary, isNew, epc, partnerLinkType, leaseTypeId, deskCount, bedroomCount, position`

- `pricing` : objet (contient `rawPrice`, …)
- `position` : coordonnées GPS (lat/lng)
- `epc` : DPE
- `classifiedURL` : URL de l'annonce (peut pointer vers bellesdemeures.com / logic-immo)
- `contact` : agence/vendeur

## Auth / anti-bot (Datadome)
- Cookie **`datadome`** (≈128 chars) requis sur toutes les requêtes.
- Header **`x-datadome-clientid`** sur les appels API == **valeur du cookie `datadome`** (1 seul secret).
- Headers attendus : `Origin: https://www.seloger.com`, `Referer: https://www.seloger.com/list.htm...`,
  `User-Agent` cohérent Windows Chrome, `content-type: application/json` (POST count).
- Le cookie expire / tourne → le scraper doit pouvoir l'injecter/rafraîchir (depuis la session
  navigateur via le MCP). Sans cookie valide → challenge Datadome (`dd.seloger.com/js/`).

## Fichiers de recherche (`.research/`)
- `list-page1.html` — fixture HTML brute (1.1 Mo) pour dev offline du parser
- `state-cards-engine.json`, `engine-api-and-card.json`, `searchfull-confirmed.json`,
  `raw-get-validation.json` — captures intermédiaires
