"""Tests de l'orchestration asynchrone (sans réseau, via monkeypatch)."""

from __future__ import annotations

import asyncio
import json

import httpx

from seloger import AsyncSelogerClient, AsyncSelogerScraper, ScraperConfig
from seloger.detail import ListingDetail
from seloger.exceptions import ListingUnavailable

from .test_detail import CLASSIFIED, _make_detail_html


def _detail_html(legacy_id: str) -> str:
    c = json.loads(json.dumps(CLASSIFIED))
    c["metadata"]["legacyId"] = legacy_id
    return _make_detail_html(c)


def test_aget_details_parallel_and_skips_failures():
    async def run():
        async with AsyncSelogerScraper(ScraperConfig(concurrency=4)) as s:
            calls: list[str] = []

            async def fake_get(url: str) -> str:
                calls.append(url)
                if "bad" in url:
                    raise RuntimeError("boom")   # ex. annonce site sœur
                return _detail_html(url.rsplit("/", 1)[-1])

            s._client.aget_detail_html = fake_get
            details = await s.aget_details([
                "https://x/111", "https://x/bad", "https://x/222",
            ])
            return details, calls

    details, calls = asyncio.run(run())
    assert len(calls) == 3                       # les 3 ont été tentées
    assert all(isinstance(d, ListingDetail) for d in details)
    assert {d.legacy_id for d in details} == {111, 222}   # le "bad" est ignoré


def test_aget_listing_parses():
    async def run():
        async with AsyncSelogerScraper() as s:
            async def fake_get(url: str) -> str:
                return _make_detail_html(CLASSIFIED)
            s._client.aget_detail_html = fake_get
            return await s.aget_listing("https://x/211815093.htm")

    detail = asyncio.run(run())
    assert detail.legacy_id == 211815093
    assert detail.url.endswith("211815093.htm")
    assert len(detail.photos) == 2


def test_410_raises_listing_unavailable():
    """Une annonce supprimée (HTTP 410) lève ListingUnavailable (pas une erreur brute)."""
    async def run():
        client = AsyncSelogerClient(ScraperConfig())
        client._client = httpx.AsyncClient(
            base_url="https://www.seloger.com",
            transport=httpx.MockTransport(lambda req: httpx.Response(410, text="Annonce supprimée")),
        )
        try:
            await client.aget_detail_html("/annonces/x/238055841.htm")
            return "no-exception"
        except ListingUnavailable:
            return "unavailable"
        finally:
            await client.aclose()

    assert asyncio.run(run()) == "unavailable"
