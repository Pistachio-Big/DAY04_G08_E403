---
name: wiki_summary
track: team_new
kind: live_api
provider: Wikipedia REST API
requires_env: []
inputs: [query, lang]
outputs: [items]
side_effect: false
---
# wiki_summary

Looks up a quick encyclopedic definition/summary of a concept, person, or
entity from Wikipedia's public REST API (no API key required). Falls back
from `vi` to `en` if the Vietnamese article does not exist.

Use this for "what is X" / "who is X" background/definition questions.
Do NOT use it for today's news (use `lookup`), for a specific page the user
gave a URL for (use `fetch`), or for social posts (use `timeline`/`social_search`).
