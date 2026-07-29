from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from chat import (
    now_iso,
    run_model_tool_loop,
    safe_slug,
    trim_history,
    write_transcript,
)
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version

ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
load_lab_env(ROOT)

st.set_page_config(page_title="Day04 Research Agent", page_icon="🔎", layout="wide")


def init_transcript(version: str, provider_name: str, model: str, artifact_version) -> dict:
    transcript_id = "_".join([safe_slug(version), safe_slug(provider_name), datetime.now().strftime("%Y%m%dT%H%M%S%f")])
    return {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact_version),
        "provider": provider_name,
        "model": model,
        "system_prompt": str(ARTIFACTS_DIR / "system_prompt.md"),
        "tools": str(ARTIFACTS_DIR / "tools.yaml"),
        "history_window": 5,
        "max_tool_rounds": 4,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }


with st.sidebar:
    st.header("Cấu hình")
    provider_name = st.selectbox("Provider", ["openrouter", "openai", "anthropic", "gemini"], index=0)
    model = st.text_input("Model (bỏ trống để dùng default)", value="nvidia/nemotron-3-super-120b-a12b:free")
    version_label = st.text_input("Version label", value="v3", help="Nhãn version đang demo, ví dụ v0, v1, v2, v3.")
    max_tool_rounds = st.number_input("Max tool rounds / turn", min_value=1, max_value=8, value=4)
    history_window = st.number_input("History window (số cặp user/assistant giữ lại)", min_value=0, max_value=20, value=5)

    if st.button("Bắt đầu / Reset hội thoại", type="primary"):
        for key in ("history", "transcript", "transcript_path", "provider_obj", "artifact_version"):
            st.session_state.pop(key, None)

    if "provider_obj" not in st.session_state:
        try:
            st.session_state.provider_obj = make_provider(provider_name)
            st.session_state.artifact_version = build_artifact_version(
                version_label, ARTIFACTS_DIR / "system_prompt.md", ARTIFACTS_DIR / "tools.yaml"
            )
            selected_model = model or getattr(st.session_state.provider_obj, "default_model", None)
            st.session_state.transcript = init_transcript(version_label, provider_name, selected_model, st.session_state.artifact_version)
            st.session_state.transcript_path = TRANSCRIPTS_DIR / f"{st.session_state.transcript['transcript_id']}.transcript.json"
            st.session_state.history = []
        except Exception as exc:
            st.error(f"Không khởi tạo được provider: {exc}")
            st.stop()

    av = st.session_state.artifact_version
    st.divider()
    st.subheader("Artifact version đang chạy")
    st.code(av.artifact_version, language=None)
    st.caption(f"prompt_hash: {av.prompt_hash[:16]}...")
    st.caption(f"tools_hash: {av.tools_hash[:16]}...")
    st.caption(f"transcript: {st.session_state.transcript_path.name}")

st.title("🔎 Day04 Research Agent")
st.caption("Request/response cuối cùng + trace từng tool call, gắn với artifact_version/transcript đang chạy.")

if "history_turns" not in st.session_state:
    st.session_state.history_turns = []

for turn in st.session_state.history_turns:
    with st.chat_message("user"):
        st.write(turn["user"])
    with st.chat_message("assistant"):
        st.write(turn["assistant_text"])
        if turn["rounds"]:
            with st.expander(f"Tool trace ({len(turn['rounds'])} round(s)) — status: {turn['status']}"):
                for round_record in turn["rounds"]:
                    st.markdown(f"**Round {round_record['round']}**")
                    if round_record["tool_calls"]:
                        for call, result in zip(round_record["tool_calls"], round_record["tool_results"]):
                            st.markdown(f"- `{call['name']}({json.dumps(call['args'], ensure_ascii=False)})`")
                            st.json(result.get("result", {}), expanded=False)
                    else:
                        st.markdown("_(no tool call, direct answer)_")

user_text = st.chat_input("Nhập yêu cầu...")
if user_text:
    st.session_state.history_turns.append({"user": user_text, "assistant_text": "", "rounds": [], "status": "running"})
    with st.chat_message("user"):
        st.write(user_text)

    system_prompt = (ARTIFACTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
    tool_declarations = load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")
    openai_tools = to_openai_tools(tool_declarations)

    messages = [
        {"role": "system", "content": system_prompt},
        *trim_history(st.session_state.history, history_window),
        {"role": "user", "content": user_text},
    ]

    turn_index = len(st.session_state.transcript["turns"]) + 1
    turn_record = {
        "turn_index": turn_index,
        "started_at": now_iso(),
        "user": user_text,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }

    with st.chat_message("assistant"):
        with st.spinner("Đang gọi model + tool..."):
            try:
                result = run_model_tool_loop(
                    provider=st.session_state.provider_obj,
                    messages=messages,
                    tools=openai_tools,
                    model=model or None,
                    max_tool_rounds=int(max_tool_rounds),
                )
                turn_record.update(result)
                assistant_text = result["assistant_text"]
                st.session_state.history.append({"role": "user", "content": user_text})
                st.session_state.history.append({"role": "assistant", "content": assistant_text})
            except Exception as exc:
                assistant_text = f"ERROR: {type(exc).__name__}: {exc}"
                turn_record.update({"status": "provider_error", "error": assistant_text})

        st.write(assistant_text)
        if turn_record["rounds"]:
            with st.expander(f"Tool trace ({len(turn_record['rounds'])} round(s)) — status: {turn_record['status']}", expanded=True):
                for round_record in turn_record["rounds"]:
                    st.markdown(f"**Round {round_record['round']}**")
                    if round_record["tool_calls"]:
                        for call, tres in zip(round_record["tool_calls"], round_record["tool_results"]):
                            st.markdown(f"- `{call['name']}({json.dumps(call['args'], ensure_ascii=False)})`")
                            st.json(tres.get("result", {}), expanded=False)
                    else:
                        st.markdown("_(no tool call, direct answer)_")

    turn_record["ended_at"] = now_iso()
    st.session_state.transcript["turns"].append(turn_record)
    write_transcript(st.session_state.transcript_path, st.session_state.transcript)

    st.session_state.history_turns[-1] = {
        "user": user_text,
        "assistant_text": turn_record.get("assistant_text") or "",
        "rounds": turn_record["rounds"],
        "status": turn_record["status"],
    }
    st.rerun()
