from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import requests

from tools._shared import TIMEOUT, err


def _wiki_user_agent() -> str:
    return os.getenv("ARXIV_USER_AGENT", "AI20k-Day04-Research-Agent/1.0 (educational lab; contact: local)")


def get_wiki_summary(query: str = "", lang: str = "vi") -> dict[str, Any]:
    try:
        lang = lang if lang in {"vi", "en"} else "vi"
        title = " ".join((query or "").split())
        if not title:
            raise RuntimeError("query is required")
        response = requests.get(
            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
            headers={"User-Agent": _wiki_user_agent(), "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        if response.status_code == 404 and lang == "vi":
            response = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
                headers={"User-Agent": _wiki_user_agent(), "Accept": "application/json"},
                timeout=TIMEOUT,
            )
            lang = "en"
        response.raise_for_status()
        data = response.json()
        page_url = (data.get("content_urls") or {}).get("desktop", {}).get("page", "")
        item = {
            "title": data.get("title", title),
            "url": page_url,
            "source": f"{lang}.wikipedia.org",
            "summary": data.get("extract", ""),
        }
        return {"tool": "get_wiki_summary", "query": query, "lang": lang, "items": [item]}
    except Exception as exc:
        return err("get_wiki_summary", exc)
