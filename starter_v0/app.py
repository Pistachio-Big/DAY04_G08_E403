from __future__ import annotations

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from chat import run_model_tool_loop, trim_history, write_transcript, now_iso, safe_slug
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version

ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"

load_lab_env(ROOT)


def get_secret_values() -> list[str]:
    secrets = []
    for k, v in os.environ.items():
        if any(term in k.upper() for term in ["KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH"]):
            if isinstance(v, str) and len(v) > 5:
                secrets.append(v)
    return list(set(secrets))


def redact_secrets(data: Any) -> Any:
    secrets = get_secret_values()
    if not secrets:
        return data

    def _redact_str(s: str) -> str:
        res = s
        for sec in secrets:
            if sec and sec in res:
                res = res.replace(sec, "[REDACTED]")
        return res

    if isinstance(data, str):
        return _redact_str(data)
    elif isinstance(data, dict):
        return {k: redact_secrets(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    return data


# Page setup
st.set_page_config(
    page_title="Research Agent UI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #4F46E5, #06B6D4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .version-badge {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 0.85rem;
        font-family: monospace;
        color: #38bdf8;
    }
    </style>
""", unsafe_allow_html=True)


# Sidebar Configuration
st.sidebar.title("⚙️ Agent Settings")

provider_name = st.sidebar.selectbox(
    "Provider",
    options=["openrouter", "openai", "anthropic", "gemini"],
    index=0,
)

model_input = st.sidebar.text_input(
    "Model (Optional)",
    value="",
    help="Leave empty to use the provider's default model.",
)
selected_model = model_input.strip() if model_input.strip() else None

version_label = st.sidebar.text_input("Artifact Version", value="v0")

history_window = st.sidebar.slider("History Window", min_value=1, max_value=20, value=5)
max_tool_rounds = st.sidebar.slider("Max Tool Rounds", min_value=1, max_value=10, value=4)

system_prompt_path = ARTIFACTS_DIR / "system_prompt.md"
tools_path = ARTIFACTS_DIR / "tools.yaml"

# Load artifacts
if not system_prompt_path.exists() or not tools_path.exists():
    st.error(f"Missing artifact files! Expected {system_prompt_path} and {tools_path}")
    st.stop()

system_prompt = system_prompt_path.read_text(encoding="utf-8")
tool_declarations = load_tool_declarations(tools_path)
openai_tools = to_openai_tools(tool_declarations)
artifact_version = build_artifact_version(version_label, system_prompt_path, tools_path)

# Display Version Info Sidebar
st.sidebar.divider()
st.sidebar.subheader("📌 Version & Artifacts")
st.sidebar.markdown(f"**Version Label:** `{artifact_version.artifact_version}`")
st.sidebar.markdown(f"**Prompt Hash:** `{artifact_version.prompt_hash[:10]}...`")
st.sidebar.markdown(f"**Tools Hash:** `{artifact_version.tools_hash[:10]}...`")

if st.sidebar.button("🧹 Clear Chat History"):
    st.session_state.history = []
    st.session_state.turns_display = []
    st.session_state.transcript = None
    st.rerun()

# Initialize Session State
if "history" not in st.session_state:
    st.session_state.history = []
if "turns_display" not in st.session_state:
    st.session_state.turns_display = []
if "transcript" not in st.session_state or st.session_state.transcript is None:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([
        safe_slug(version_label),
        safe_slug(provider_name),
        timestamp,
    ])
    transcript_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
    st.session_state.transcript_id = transcript_id
    st.session_state.transcript_path = str(transcript_path)
    st.session_state.transcript = {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact_version),
        "provider": provider_name,
        "model": selected_model,
        "system_prompt": str(system_prompt_path),
        "tools": str(tools_path),
        "history_window": history_window,
        "max_tool_rounds": max_tool_rounds,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }

# Main Interface
st.markdown('<div class="main-header">🤖 Research Agent Studio</div>', unsafe_allow_html=True)
st.markdown(f'<span class="version-badge">Version: {artifact_version.artifact_version} | Provider: {provider_name}</span>', unsafe_allow_html=True)
st.write("")

# Render Past Messages / Turns
for turn in st.session_state.turns_display:
    with st.chat_message("user"):
        st.write(turn["user"])

    with st.chat_message("assistant"):
        # Display rounds if any tool execution happened
        rounds = turn.get("rounds", [])
        if rounds:
            with st.expander(f"🔄 Execution Details ({len(rounds)} Round(s))", expanded=False):
                for r in rounds:
                    st.markdown(f"**Round {r.get('round')}**")
                    if r.get("assistant_text"):
                        st.markdown(f"*Assistant reasoning:* {r.get('assistant_text')}")
                    
                    tool_calls = r.get("tool_calls", [])
                    tool_results = r.get("tool_results", [])
                    for call, res in zip(tool_calls, tool_results):
                        st.markdown(f"🛠️ **Tool:** `{call.get('name')}`")
                        st.json(redact_secrets(call.get("args")), expanded=False)
                        st.markdown("**Result / Output:**")
                        st.json(redact_secrets(res.get("result")), expanded=False)
                    st.divider()

        # Display final response text
        assistant_text = turn.get("assistant_text")
        if assistant_text:
            st.markdown(assistant_text)
        elif turn.get("status") == "provider_error":
            st.error(turn.get("error"))

# User Chat Input
if prompt := st.chat_input("Enter your research request..."):
    # Display user input immediately
    with st.chat_message("user"):
        st.write(prompt)

    # Process turn
    messages = [
        {"role": "system", "content": system_prompt},
        *trim_history(st.session_state.history, history_window),
        {"role": "user", "content": prompt},
    ]

    turn_index = len(st.session_state.turns_display) + 1
    turn_record: dict[str, Any] = {
        "turn_index": turn_index,
        "started_at": now_iso(),
        "user": prompt,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }

    with st.chat_message("assistant"):
        with st.spinner("Thinking and executing tools..."):
            try:
                provider = make_provider(provider_name)
                result = run_model_tool_loop(
                    provider=provider,
                    messages=messages,
                    tools=openai_tools,
                    model=selected_model,
                    max_tool_rounds=max_tool_rounds,
                )
                turn_record.update(result)
                assistant_text = result.get("assistant_text", "")
                
                # Render rounds details
                rounds = result.get("rounds", [])
                if rounds:
                    with st.expander(f"🔄 Execution Details ({len(rounds)} Round(s))", expanded=True):
                        for r in rounds:
                            st.markdown(f"**Round {r.get('round')}**")
                            if r.get("assistant_text"):
                                st.markdown(f"*Assistant reasoning:* {r.get('assistant_text')}")
                            
                            tool_calls = r.get("tool_calls", [])
                            tool_results = r.get("tool_results", [])
                            for call, res in zip(tool_calls, tool_results):
                                st.markdown(f"🛠️ **Tool:** `{call.get('name')}`")
                                st.json(redact_secrets(call.get("args")), expanded=False)
                                st.markdown("**Result / Output:**")
                                st.json(redact_secrets(res.get("result")), expanded=False)
                            st.divider()

                st.markdown(assistant_text)

                # Update history
                st.session_state.history.append({"role": "user", "content": prompt})
                st.session_state.history.append({"role": "assistant", "content": assistant_text})

            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {str(exc)}"
                turn_record.update({
                    "status": "provider_error",
                    "error": error_msg,
                })
                st.error(f"Error: {error_msg}")

    turn_record["ended_at"] = now_iso()
    
    # Store turn for display
    st.session_state.turns_display.append(turn_record)

    # Save to transcript file without secrets
    redacted_turn_record = redact_secrets(turn_record)
    st.session_state.transcript["turns"].append(redacted_turn_record)
    write_transcript(Path(st.session_state.transcript_path), st.session_state.transcript)