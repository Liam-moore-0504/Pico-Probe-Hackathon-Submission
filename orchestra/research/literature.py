"""Allowlisted DOI and arXiv metadata clients with bounded requests."""

from __future__ import annotations

import re

import httpx
from defusedxml import ElementTree as ET


class LiteratureClient:
    def __init__(self):
        self.client = httpx.Client(
            timeout=httpx.Timeout(30, connect=10),
            transport=httpx.HTTPTransport(retries=2),
            follow_redirects=False,
        )

    def resolve_doi(self, doi: str) -> dict:
        normalized = doi.removeprefix("https://doi.org/").strip()
        if not re.fullmatch(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", normalized):
            raise ValueError("Invalid DOI")
        response = self.client.get(f"https://api.crossref.org/works/{normalized}", headers={"User-Agent": "PicoProbe/1.0 (mailto:research@picoprobe.com)"})
        response.raise_for_status()
        item = response.json()["message"]
        return {
            "source_type": "doi",
            "title": (item.get("title") or [normalized])[0],
            "authors": [" ".join(filter(None, [author.get("given"), author.get("family")])) for author in item.get("author", [])],
            "doi": normalized,
            "url": item.get("URL"),
            "metadata": {"publisher": item.get("publisher"), "type": item.get("type"), "issued": item.get("issued")},
            "reliability": 0.8,
        }

    def resolve_arxiv(self, arxiv_id: str) -> dict:
        normalized = arxiv_id.removeprefix("arXiv:").strip()
        if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?", normalized, re.I):
            raise ValueError("Invalid arXiv identifier")
        response = self.client.get(
            "https://export.arxiv.org/api/query",
            params={"id_list": normalized, "max_results": 1},
            headers={"User-Agent": "PicoProbe/1.0 (mailto:research@picoprobe.com)"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        namespace = {"a": "http://www.w3.org/2005/Atom"}
        entry = root.find("a:entry", namespace)
        if entry is None:
            raise ValueError("arXiv record not found")
        return {
            "source_type": "arxiv",
            "title": " ".join((entry.findtext("a:title", "", namespace)).split()),
            "authors": [author.findtext("a:name", "", namespace) for author in entry.findall("a:author", namespace)],
            "arxiv_id": normalized,
            "url": entry.findtext("a:id", "", namespace),
            "metadata": {
                "summary": " ".join(entry.findtext("a:summary", "", namespace).split()),
                "published": entry.findtext("a:published", "", namespace),
                "updated": entry.findtext("a:updated", "", namespace),
            },
            "reliability": 0.65,
        }
