from __future__ import annotations

import os
from typing import Any

import requests

from tools._shared import TIMEOUT, err


GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"


def github_search(
    query: str = "",
    sort: str = "best_match",
    language: str = "",
    max_results: int = 5,
) -> dict[str, Any]:
    try:
        max_results = max(1, min(int(max_results or 5), 10))
        sort = sort if sort in {"stars", "forks", "updated", "best_match"} else "best_match"

        q = query
        if language:
            q += f" language:{language}"

        params: dict[str, Any] = {
            "q": q,
            "per_page": max_results,
            "order": "desc",
        }
        if sort != "best_match":
            params["sort"] = sort

        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = requests.get(
            GITHUB_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        items = []
        for repo in data.get("items", [])[:max_results]:
            items.append({
                "title": repo.get("full_name", ""),
                "url": repo.get("html_url", ""),
                "source": "github.com",
                "summary": repo.get("description") or "",
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "language": repo.get("language"),
                "updated_at": repo.get("updated_at"),
                "topics": repo.get("topics", []),
            })

        return {
            "tool": "github_search",
            "query": query,
            "sort": sort,
            "language": language,
            "total_count": data.get("total_count", 0),
            "items": items,
        }
    except Exception as exc:
        return err("github_search", exc)
