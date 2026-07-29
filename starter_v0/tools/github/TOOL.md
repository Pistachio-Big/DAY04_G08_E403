---
name: github
track: bonus
kind: live_api
provider: GitHub Search API
requires_env: []
inputs: [query, sort, language, max_results]
outputs: [title, url, source, summary, stars, forks, language, updated_at, topics]
side_effect: false
requires_confirmation: false
---

Search GitHub repositories by keyword, language, and sort order.
Uses the public GitHub Search API (no auth required, optional GITHUB_TOKEN for higher rate limits).
