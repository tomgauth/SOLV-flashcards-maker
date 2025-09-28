import os
import json
import random
from typing import List, Dict, Any

import streamlit as st

# ElevenLabs SDK
from elevenlabs.client import ElevenLabs

# Optional: load .env if present (local dev)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# ---------- Helpers ----------
ENV_API_KEY = "ELEVENLABS_API_KEY"

def get_api_key() -> str | None:
    # Priority: ENV -> session state -> user input (sidebar)
    key = os.getenv(ENV_API_KEY)
    if not key:
        key = st.session_state.get("api_key")
    return key


@st.cache_data(show_spinner=False)
def fetch_voices(api_key: str) -> List[Dict[str, str]]:
    """
    Returns a list of voices as dicts: {id, name, label}
    Handles both dict-like and dataclass-like SDK returns.
    """
    client = ElevenLabs(api_key=api_key)
    resp = client.voices.get_all()
    try:
        iterable = resp.voices  # new SDK style
    except AttributeError:
        iterable = resp  # defensive fallback

    voices = []
    for v in iterable:
        # dataclass-like attributes or dict fallback
        vid = getattr(v, "voice_id", None) or v.get("voice_id")
        name = getattr(v, "name", None) or v.get("name")
        labels = getattr(v, "labels", None) or v.get("labels", {}) or {}
        accent = labels.get("accent") if isinstance(labels, dict) else None
        display = f"{name}  ({vid[:6]}…)" if vid and name else str(v)
        if accent:
            display = f"{display} · {accent}"
        voices.append({"id": vid, "name": name, "label": display})
    # Sort by name for easier picking
    voices.sort(key=lambda x: (x["name"] or "").lower())
    return voices


def ensure_dialogue_state():
    if "speakers" not in st.session_state:
        st.session_state.speakers = [
            {"name": "A", "voice_id": None},
            {"name": "B", "voice_id": None},
        ]
    if "lines" not in st.session_state:
        st.session_state.lines = [
            {"speaker": "A", "text": "[cheerfully] Hi! Americano nóng, không đường nhé."},
            {"speaker": "B", "text": "Dạ, một Americano nóng. Anh ở Đà Nẵng lâu chưa?"},
            {"speaker": "A", "text": "Mới đến thôi. Tôi làm việc online. Trời mưa cũng hay!"},
        ]
    if "settings" not in st.session_state:
        st.session_state.settings = {
            "model_id": "eleven_v3",     # Text-to-Dialogue runs on v3
            "language_code": "",         # leave empty to auto-detect
            "apply_text_normalization": "auto",  # auto|on|off
            "seed": None,                # or an int 0..4294967295
            "output_format": "mp3_44100_128",    # default per API
        }


def build_inputs(lines: List[Dict[str, str]], speakers: List[Dict[str, str]]) -> List[Dict[str, str]]:
    # speaker name -> voice_id
    lookup = {s["name"]: s["voice_id"] for s in speakers}
    inputs = []
    for row in lines:
        spk = row.get("speaker")
        text = (row.get("text") or "").strip()
        if not text:
            continue
        vid = lookup.get(spk)
        if not vid:
            raise ValueError(f"Speaker '{spk}' has no voice selected.")
        inputs.append({"text": text, "voice_id": vid})
    if not inputs:
        raise ValueError("No valid lines to convert. Add text and choose voices.")
    return inputs


def convert_dialogue(api_key: str, payload: Dict[str, Any]) -> bytes:
    """
    Uses the official ElevenLabs text_to_dialogue API
    """
    client = ElevenLabs(api_key=api_key)
    
    # Use the official text_to_dialogue API
    audio: bytes = client.text_to_dialogue.convert(
        inputs=payload['inputs']
    )
    return audio


# ---------- UI ----------
st.set_page_config(page_title="ElevenLabs: Text → Dialogue", page_icon="🎙️", layout="wide")
st.title("🎙️ ElevenLabs Text → Dialogue (Streamlit)")
st.caption(
    "Write a short multi-speaker script, pick voices, and generate an audio dialogue. "
    "Tip: add tags like `[cheerfully]`, `[laughing]`, `[sigh]` for expressive deliveries."
)


ensure_dialogue_state()

with st.sidebar:
    st.header("🔑 API Key")
    st.text("Key priority: Secrets → ENV → Below")
    api_key_input = st.text_input("ELEVENLABS_API_KEY", type="password", placeholder="sk-…")
    if api_key_input:
        st.session_state.api_key = api_key_input

    api_key = get_api_key()
    if not api_key:
        st.warning("Add your ElevenLabs API key to continue.")
    else:
        st.success("API key loaded.")

    st.markdown("---")
    st.subheader("⚙️ Output")
    s = st.session_state.settings
    s["output_format"] = st.selectbox(
        "Output format (codec_rate_bitrate)",
        # Values per API reference; default matches docs
        [
            "mp3_44100_128",
            "mp3_44100_192",
            "mp3_22050_32",
            "pcm_16000",
            "pcm_22050",
            "pcm_24000",
            "pcm_44100",
            "ulaw_8000",
            "alaw_8000",
            "opus_48000",
        ],
        index=0,
        help="Default is mp3_44100_128. Higher bitrates/sample rates may require paid tiers."
    )
    st.session_state.settings = s

st.markdown("### 1) Pick your speakers & voices")
colA, colB = st.columns([1, 2], vertical_alignment="top")

with colA:
    if api_key:
        with st.spinner("Fetching voices…"):
            voices = fetch_voices(api_key)
        if not voices:
            st.error("No voices found in your ElevenLabs account.")
    else:
        voices = []

    # Show/edit speaker rows
    speakers = st.session_state.speakers
    add_col, rem_col = st.columns(2)
    if add_col.button("➕ Add speaker"):
        speakers.append({"name": f"S{len(speakers)+1}", "voice_id": None})
    if rem_col.button("➖ Remove last"):
        if len(speakers) > 1:
            speakers.pop()

    # Render speaker pickers
    for i, sp in enumerate(speakers):
        with st.expander(f"Speaker {i+1}"):
            sp["name"] = st.text_input("Name / Label", value=sp["name"], key=f"spname_{i}")
            if voices:
                labels = [v["label"] for v in voices]
                # Preselect the current voice if set
                current_idx = 0
                if sp.get("voice_id"):
                    for idx, v in enumerate(voices):
                        if v["id"] == sp["voice_id"]:
                            current_idx = idx
                            break
                choice = st.selectbox("Voice", labels, index=current_idx, key=f"spvoice_{i}")
                sp["voice_id"] = voices[labels.index(choice)]["id"]
            else:
                st.info("Add API key to list voices.")
    st.session_state.speakers = speakers

with colB:
    st.markdown("### 2) Write your dialogue")
    st.caption("Each row is one line. Choose who speaks and write the text. Use tags like `[cheerfully]`, `[laughing]`, `[sigh]`, or ambient cues like `[gentle footsteps]`.")
    # Build speaker options for the editor
    speaker_names = [sp["name"] for sp in st.session_state.speakers]
    # Streamlit data_editor with selectbox per row
    cfg = {
        "speaker": st.column_config.SelectboxColumn("Speaker", options=speaker_names, width="small"),
        "text": st.column_config.TextColumn("Line", help="Supports audio/emotion tags, e.g., [cheerfully] Hello!"),
    }
    lines = st.data_editor(
        st.session_state.lines,
        column_config=cfg,
        use_container_width=True,
        num_rows="dynamic",
        key="lines_editor",
    )
    st.session_state.lines = lines

    # Quick example button
    if st.button("🧪 Load Example (Da Nang coffee)"):
        st.session_state.lines = [
            {"speaker": speaker_names[0] if speaker_names else "A", "text": "[cheerfully] Xin chào! Cho mình một Americano nóng, không đường nhé."},
            {"speaker": speaker_names[1] if len(speaker_names) > 1 else "B", "text": "Dạ, một Americano nóng. Anh ở Đà Nẵng lâu chưa?"},
            {"speaker": speaker_names[0] if speaker_names else "A", "text": "Mới đến vài tuần. [lightly] Trời mưa hôm nay, nhưng mình thích không khí."},
            {"speaker": speaker_names[1] if len(speaker_names) > 1 else "B", "text": "Vâng, mưa ở đây đẹp. [curious] Anh làm nghề gì ạ?"},
            {"speaker": speaker_names[0] if speaker_names else "A", "text": "Mình làm online. [friendly] Cảm ơn!"},
        ]
        st.experimental_rerun()

st.markdown("### 3) Model & advanced")
adv1, adv2, adv3 = st.columns(3)
with adv1:
    st.session_state.settings["model_id"] = st.selectbox(
        "Model", ["eleven_v3"], index=0,
        help="Text-to-Dialogue runs on the Eleven v3 model."
    )
with adv2:
    lang = st.text_input(
        "Language code (ISO 639-1) — optional",
        value=st.session_state.settings.get("language_code", ""),
        placeholder="e.g., en, fr, vi (leave blank to auto-detect)"
    )
    st.session_state.settings["language_code"] = lang.strip() if lang else None
with adv3:
    seed_toggle = st.toggle("Use deterministic seed", value=bool(st.session_state.settings.get("seed") is not None))
    if seed_toggle:
        seed_val = st.number_input("Seed (0…4294967295)", min_value=0, max_value=4294967295, value=st.session_state.settings.get("seed") or 1337)
        st.session_state.settings["seed"] = int(seed_val)
        if st.button("🎲 Randomize seed"):
            st.session_state.settings["seed"] = random.randint(0, 2**32 - 1)
    else:
        st.session_state.settings["seed"] = None

norm = st.radio(
    "Text normalization",
    options=["auto", "on", "off"],
    index=["auto", "on", "off"].index(st.session_state.settings.get("apply_text_normalization", "auto")),
    horizontal=True,
    help="auto = let the API decide (e.g., spelling out numbers); 'on' always normalize; 'off' never normalize."
)
st.session_state.settings["apply_text_normalization"] = norm

st.markdown("---")
gen_left, gen_right = st.columns([1, 2])
with gen_left:
    go = st.button("🎧 Generate Dialogue", type="primary", use_container_width=True)
with gen_right:
    show_json = st.toggle("Show request JSON")

if go:
    if not api_key:
        st.error("Missing API key.")
    else:
        try:
            inputs = build_inputs(st.session_state.lines, st.session_state.speakers)

            payload = {
                "inputs": inputs,
                "model_id": st.session_state.settings["model_id"],
                "language_code": st.session_state.settings.get("language_code"),
                "seed": st.session_state.settings.get("seed"),
                "apply_text_normalization": st.session_state.settings.get("apply_text_normalization"),
                "output_format": st.session_state.settings.get("output_format"),
            }
            # Remove None to keep payload clean
            payload = {k: v for k, v in payload.items() if v not in (None, "", [])}

            if show_json:
                st.code(json.dumps(payload, indent=2, ensure_ascii=False), language="json")

            with st.spinner("Generating audio…"):
                audio_bytes = convert_dialogue(api_key, payload)

            st.success("Done!")
            st.audio(audio_bytes, format="audio/mp3")
            st.download_button("⬇️ Download MP3", data=audio_bytes, file_name="dialogue.mp3", mime="audio/mpeg")

        except Exception as e:
            st.exception(e)

st.markdown("---")
with st.expander("ℹ️ Tips"):
    st.markdown(
        """
- **Use delivery tags** in your text for emotion/FX: `[cheerfully]`, `[laughing]`, `[sigh]`, `[leaves rustling]`, `[auctioneer]`, etc.
- Keep lines **short and natural**; several short lines usually sound better than one huge paragraph.
- For **consistent re-runs**, set a **seed**.
- This endpoint is **not for realtime** chat; generate and pick your favorite take.
"""
    )
