"""
Demo script: chạy case M06 với v1 và v2 prompt, so sánh kết quả.
Usage:  python demo_compare.py --provider openrouter
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from env_loader import load_lab_env
from agent import ResearchAgent
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools

ROOT = Path(__file__).parent
load_lab_env(ROOT)

TOOLS_YAML = ROOT / "artifacts" / "tools.yaml"

PROMPTS = {
    "v1": ROOT / "artifacts" / "system_prompt_v1.md",
    "v2": ROOT / "artifacts" / "system_prompt.md",
}

M06 = {
    "turns": [
        {"role": "user", "content": "Mọi người nói gì về OpenAI trên Twitter?"},
        {"role": "user", "content": "Bỏ Twitter, chuyển sang tìm trên web tin tức đi"},
        {"role": "user", "content": "Giữ chủ đề OpenAI"},
    ],
    "expect": "lookup only (NOT social_search)",
}


def build_eval_message(turns):
    previous = turns[:-1]
    latest = turns[-1]["content"]
    previous_text = "\n".join(
        f"- Earlier {t['role']} turn {i+1}: {t['content']}"
        for i, t in enumerate(previous)
    )
    return (
        "Conversation context for a multi-turn eval.\n"
        "Use earlier turns only as context. Do not answer earlier turns and do not call tools for them.\n\n"
        f"{previous_text}\n\n"
        f"Latest user turn to answer now: {latest}"
    )


def run_case(provider, prompt_path, tools, model):
    system_prompt = prompt_path.read_text(encoding="utf-8")
    agent = ResearchAgent(provider, system_prompt=system_prompt, tools=tools, model=model)
    message = build_eval_message(M06["turns"])
    run = agent.run([{"role": "user", "content": message}], tool_choice="required")
    return [{"name": c.name, "args": c.args} for c in run.tool_calls]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="openrouter")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    provider = make_provider(args.provider)
    declarations = load_tool_declarations(TOOLS_YAML)
    tools = to_openai_tools(declarations)

    print("=" * 60)
    print("DEMO: M06_switch_tool — v1 vs v2")
    print("=" * 60)
    print()
    for t in M06["turns"]:
        print(f"  User: {t['content']}")
    print(f"\n  Expected: {M06['expect']}")
    print()

    for ver, path in PROMPTS.items():
        print(f"--- {ver} ({path.name}) ---")
        calls = run_case(provider, path, tools, args.model)
        tool_names = [c["name"] for c in calls]
        passed = tool_names == ["lookup"]
        status = "PASS" if passed else "FAIL"
        print(f"  Tool calls: {tool_names}")
        for c in calls:
            print(f"    {c['name']}({json.dumps(c['args'], ensure_ascii=False)})")
        print(f"  Result: {status}")
        print()

    print("=" * 60)


if __name__ == "__main__":
    main()
