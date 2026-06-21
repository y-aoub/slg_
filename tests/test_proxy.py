"""Tests de la configuration proxy (style lbc)."""

from __future__ import annotations

import pytest

from seloger.config import ScraperConfig
from seloger.proxy import Proxy


def test_proxy_url_with_auth():
    p = Proxy(host="1.2.3.4", port=8080, username="u", password="p")
    assert p.url == "http://u:p@1.2.3.4:8080"


def test_proxy_url_without_auth():
    assert Proxy(host="1.2.3.4", port="8080").url == "http://1.2.3.4:8080"


def test_proxy_from_url_roundtrip():
    p = Proxy.from_url("http://u:p@host:3128")
    assert (p.host, p.port, p.username, p.password) == ("host", 3128, "u", "p")
    assert Proxy.from_url("host:3128").url == "http://host:3128"


def test_proxy_from_url_invalid():
    with pytest.raises(ValueError):
        Proxy.from_url("not-a-proxy")


def test_config_proxy_url_accepts_instance_and_string():
    assert ScraperConfig(proxy=Proxy("h", 80)).proxy_url() == "http://h:80"
    assert ScraperConfig(proxy="http://h:80").proxy_url() == "http://h:80"
    assert ScraperConfig(proxy=None).proxy_url() is None


def test_config_proxy_from_env(monkeypatch):
    monkeypatch.setenv("SELOGER_PROXY", "http://envhost:9999")
    assert ScraperConfig().proxy_url() == "http://envhost:9999"
