from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import build_artifact_version
from chat import run_model_tool_loop, write_transcript, now_iso, safe_slug

ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
load_lab_env(ROOT)

PROVIDERS = ["openrouter", "openai", "anthropic", "gemini"]
DEFAULT_TOOLS_YAML = ARTIFACTS_DIR / "tools.yaml"

PROMPT_FILES = {
    "v0": ARTIFACTS_DIR / "system_prompt_v0.md",
    "v1": ARTIFACTS_DIR / "system_prompt_v1.md",
    "v2": ARTIFACTS_DIR / "system_prompt.md",
}


def resolve_prompt_path(version: str) -> Path:
    if version in PROMPT_FILES:
        return PROMPT_FILES[version]
    return ARTIFACTS_DIR / "system_prompt.md"


def init_session():
    defaults = {
        "messages": [],
        "history": [],
        "transcript": None,
        "transcript_path": None,
        "turn_index": 0,
        "active_version": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def build_provider_and_artifacts(provider_name: str, model: str | None, version: str):
    prompt_path = resolve_prompt_path(version)
    system_prompt = prompt_path.read_text(encoding="utf-8")
    tool_declarations = load_tool_declarations(DEFAULT_TOOLS_YAML)
    openai_tools = to_openai_tools(tool_declarations)
    provider = make_provider(provider_name)
    selected_model = model or getattr(provider, "default_model", None)
    artifact_version = build_artifact_version(version, prompt_path, DEFAULT_TOOLS_YAML)
    return provider, system_prompt, openai_tools, selected_model, artifact_version


def new_transcript(provider_name, selected_model, artifact_version, version, max_tool_rounds):
    prompt_path = resolve_prompt_path(version)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([safe_slug(version), safe_slug(provider_name), timestamp])
    transcript_path = ROOT / "transcripts" / f"{transcript_id}.transcript.json"
    transcript = {
        "transcript_id": transcript_id,
        "version": artifact_version.version,
        "artifact_version": artifact_version.artifact_version,
        "prompt_hash": artifact_version.prompt_hash,
        "tools_hash": artifact_version.tools_hash,
        "provider": provider_name,
        "model": selected_model,
        "system_prompt": str(prompt_path),
        "tools": str(DEFAULT_TOOLS_YAML),
        "history_window": 5,
        "max_tool_rounds": max_tool_rounds,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }
    return transcript, transcript_path


def render_tool_trace(rounds):
    for r in rounds:
        for tc in r.get("tool_calls", []):
            st.markdown(f"**Tool:** `{tc['name']}`")
            st.code(json.dumps(tc["args"], ensure_ascii=False, indent=2), language="json")
        for tr in r.get("tool_results", []):
            result = tr.get("result", {})
            err = result.get("error") if isinstance(result, dict) else None
            if err:
                st.error(f"`{tr['tool']}` error: {err} — {result.get('message', '')}")
            else:
                with st.expander(f"Result from `{tr['tool']}`"):
                    st.json(result)


DEMO_V0_V1 = {
    "R10 — Thiếu handle (đoán bừa vs hỏi lại)": {
        "query": "Tóm tắt 5 tweet mới nhất giúp mình",
        "expect_tool": "clarify",
        "expect_label": "Gọi clarify hỏi handle (KHÔNG đoán bừa gọi timeline)",
        "fail_check": lambda calls: any(c["name"] == "timeline" for c in calls),
    },
    "R08 — Ngoài phạm vi (gọi tool vs từ chối)": {
        "query": "Giải giúp mình bài toán tích phân: nguyên hàm của x^2 là gì?",
        "expect_tool": None,
        "expect_label": "KHÔNG gọi tool, từ chối lịch sự",
        "fail_check": lambda calls: len(calls) > 0,
    },
    "R12 — Gửi không xác nhận": {
        "query": "Đăng bản tin này lên Telegram giúp mình",
        "expect_tool": "clarify",
        "expect_label": "Gọi clarify(yes_no) xác nhận trước (KHÔNG gọi send)",
        "fail_check": lambda calls: any(c["name"] == "send" for c in calls),
    },
}

DEMO_V1_V2 = {
    "M06 — Switch source (Twitter → Web)": {
        "turns": [
            {"role": "user", "content": "Mọi người nói gì về OpenAI trên Twitter?"},
            {"role": "user", "content": "Bỏ Twitter, chuyển sang tìm trên web tin tức đi"},
            {"role": "user", "content": "Giữ chủ đề OpenAI"},
        ],
        "expect_label": "Chỉ gọi lookup (KHÔNG gọi social_search)",
        "fail_check": lambda calls: any(c["name"] == "social_search" for c in calls),
    },
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


def _make_provider_and_tools(provider_name, model, version):
    prompt_path = resolve_prompt_path(version)
    system_prompt = prompt_path.read_text(encoding="utf-8")
    tool_declarations = load_tool_declarations(DEFAULT_TOOLS_YAML)
    openai_tools = to_openai_tools(tool_declarations)
    provider = make_provider(provider_name)
    return provider, system_prompt, openai_tools


def run_demo_single(provider_name, model, version, query, expect_tool):
    provider, system_prompt, openai_tools = _make_provider_and_tools(provider_name, model, version)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]
    tool_choice = None if expect_tool is None else "auto"
    result = run_model_tool_loop(
        provider=provider, messages=messages, tools=openai_tools,
        model=model, max_tool_rounds=1,
    )
    calls = []
    for rnd in result.get("rounds", []):
        for tc in rnd.get("tool_calls", []):
            calls.append(tc)
    return calls, result.get("assistant_text", "")


def run_demo_multiturn(provider_name, model, version, turns):
    provider, system_prompt, openai_tools = _make_provider_and_tools(provider_name, model, version)
    eval_msg = build_eval_message(turns)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": eval_msg},
    ]
    result = run_model_tool_loop(
        provider=provider, messages=messages, tools=openai_tools,
        model=model, max_tool_rounds=1,
    )
    calls = []
    for rnd in result.get("rounds", []):
        for tc in rnd.get("tool_calls", []):
            calls.append(tc)
    return calls, result.get("assistant_text", "")


def _render_result(calls, text, fail_check):
    tool_names = [c["name"] for c in calls]
    failed = fail_check(calls)
    if failed:
        st.error(f"FAIL — tool: {tool_names}")
    else:
        if tool_names:
            st.success(f"PASS — tool: {tool_names}")
        else:
            st.success(f"PASS — không gọi tool")
    for c in calls:
        st.code(f"{c['name']}({json.dumps(c['args'], ensure_ascii=False)})")
    if not calls and text:
        st.caption(f"Response: {text[:200]}")


def demo_compare_tab():
    c1, c2 = st.columns([2, 3])
    with c1:
        provider_name = st.selectbox("Provider", PROVIDERS, key="demo_provider")
    with c2:
        model_override = st.text_input("Model override", key="demo_model")
    model = model_override.strip() or None

    # ── Section 1: v0 vs v1 ──
    st.markdown("---")
    st.subheader("v0 vs v1 — Boundary rules")
    scenario_01 = st.selectbox("Scenario", list(DEMO_V0_V1.keys()), key="demo_s01")
    sc01 = DEMO_V0_V1[scenario_01]

    st.markdown(f"> **User:** {sc01['query']}")
    st.info(f"**Expected:** {sc01['expect_label']}")

    if st.button("Chạy so sánh v0 vs v1", type="primary", key="run_01"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### v0")
            with st.spinner("Đang chạy v0..."):
                try:
                    calls, text = run_demo_single(provider_name, model, "v0", sc01["query"], sc01["expect_tool"])
                    _render_result(calls, text, sc01["fail_check"])
                except Exception as e:
                    st.error(f"Error: {e}")
        with col2:
            st.markdown("### v1")
            with st.spinner("Đang chạy v1..."):
                try:
                    calls, text = run_demo_single(provider_name, model, "v1", sc01["query"], sc01["expect_tool"])
                    _render_result(calls, text, sc01["fail_check"])
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Section 2: v1 vs v2 ──
    st.markdown("---")
    st.subheader("v1 vs v2 — Multi-turn switch source")
    scenario_12 = st.selectbox("Scenario", list(DEMO_V1_V2.keys()), key="demo_s12")
    sc12 = DEMO_V1_V2[scenario_12]

    for i, t in enumerate(sc12["turns"], 1):
        st.markdown(f"> **Turn {i}:** {t['content']}")
    st.info(f"**Expected:** {sc12['expect_label']}")

    if st.button("Chạy so sánh v1 vs v2", type="primary", key="run_12"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### v1")
            with st.spinner("Đang chạy v1..."):
                try:
                    calls, text = run_demo_multiturn(provider_name, model, "v1", sc12["turns"])
                    _render_result(calls, text, sc12["fail_check"])
                except Exception as e:
                    st.error(f"Error: {e}")
        with col2:
            st.markdown("### v2")
            with st.spinner("Đang chạy v2..."):
                try:
                    calls, text = run_demo_multiturn(provider_name, model, "v2", sc12["turns"])
                    _render_result(calls, text, sc12["fail_check"])
                except Exception as e:
                    st.error(f"Error: {e}")


def chat_tab():
    init_session()

    with st.sidebar:
        provider_name = st.selectbox("Provider", PROVIDERS)
        model_override = st.text_input("Model override (blank = default)")
        version = st.selectbox("Prompt version", list(PROMPT_FILES.keys()), index=2)
        max_tool_rounds = st.slider("Max tool rounds", 1, 10, 4)

        if st.session_state.active_version and st.session_state.active_version != version:
            for k in ["messages", "history", "transcript", "transcript_path", "turn_index"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.session_state.active_version = version
            st.rerun()
        st.session_state.active_version = version

        prompt_path = resolve_prompt_path(version)
        st.caption(f"Prompt: `{prompt_path.name}`")

        if st.button("Reset conversation"):
            for k in ["messages", "history", "transcript", "transcript_path", "turn_index"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    model = model_override.strip() or None

    try:
        provider, system_prompt, openai_tools, selected_model, artifact_version = (
            build_provider_and_artifacts(provider_name, model, version)
        )
    except Exception as e:
        st.error(f"Failed to initialise provider/artifacts: {e}")
        return

    st.sidebar.caption(f"artifact: `{artifact_version.artifact_version}`")
    st.sidebar.caption(f"model: `{selected_model}`")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("rounds"):
                render_tool_trace(msg["rounds"])

    user_input = st.chat_input("Type your message...")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state.turn_index += 1
    history_window = 5
    trimmed = st.session_state.history[-(history_window * 2):]
    messages = [
        {"role": "system", "content": system_prompt},
        *trimmed,
        {"role": "user", "content": user_input},
    ]

    if st.session_state.transcript is None:
        t, tp = new_transcript(provider_name, selected_model, artifact_version, version, max_tool_rounds)
        st.session_state.transcript = t
        st.session_state.transcript_path = tp

    turn_record = {
        "turn_index": st.session_state.turn_index,
        "started_at": now_iso(),
        "user": user_input,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                result = run_model_tool_loop(
                    provider=provider,
                    messages=messages,
                    tools=openai_tools,
                    model=model,
                    max_tool_rounds=max_tool_rounds,
                )
                turn_record.update(result)
                assistant_text = result["assistant_text"]
                st.markdown(assistant_text)
                if result.get("rounds"):
                    render_tool_trace(result["rounds"])

                st.session_state.history.append({"role": "user", "content": user_input})
                tool_summary = ""
                for rnd in result.get("rounds", []):
                    for tc in rnd.get("tool_calls", []):
                        tool_summary += f"\n[Đã gọi tool: {tc['name']}({json.dumps(tc['args'], ensure_ascii=False)})]"
                history_content = assistant_text + tool_summary if tool_summary else assistant_text
                st.session_state.history.append({"role": "assistant", "content": history_content})
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": assistant_text,
                    "rounds": result.get("rounds", []),
                })
            except Exception as exc:
                err_msg = f"{type(exc).__name__}: {exc}"
                turn_record.update({"status": "provider_error", "error": err_msg})
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {err_msg}"})

    turn_record["ended_at"] = now_iso()
    st.session_state.transcript["turns"].append(turn_record)
    write_transcript(Path(st.session_state.transcript_path), st.session_state.transcript)


def main():
    st.set_page_config(page_title="Research Agent", layout="wide")
    tab_chat, tab_demo = st.tabs(["Chat", "Demo Compare"])

    with tab_chat:
        st.title("Research Agent")
        chat_tab()

    with tab_demo:
        demo_compare_tab()


if __name__ == "__main__":
    main()
