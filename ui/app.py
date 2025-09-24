import os
import tempfile
import streamlit as st
import sys
from pathlib import Path
from datetime import date

# Ensure project root (containing `backend/`) is on sys.path for imports when run via Streamlit
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.simple_parsing import parse_two_column_tsv
from backend.simple_flashcards import build_simple_apkg
from backend.elevenlabs_tts import list_voices, group_voices_by_language, voices_for_language_strict, synthesize_text, ElevenLabsError

st.set_page_config(page_title="Flashcards Creator", page_icon="🃏", layout="centered")

st.title("Flashcards Creator")

st.write("Paste two-column TSV: left = A (UserLanguage), right = B (TargetLanguage)")

tsv_text = st.text_area("TSV (A\tB)", height=220)

colType = st.columns([1])[0]
with colType:
    card_type = st.selectbox("Card type", ["Recall", "Recognise"], index=0)

colA, colB, colLang = st.columns([1, 1, 2])
with colA:
    target_col_choice = st.selectbox("TargetLanguage column", ["1 (left)", "2 (right)"], index=0)
with colB:
    user_col_choice = st.selectbox("UserLanguage column", ["1 (left)", "2 (right)"], index=1)
with colLang:
    target_language_choice = st.selectbox("Target language label", ["French", "Italian", "Vietnamese Central", "Russian"], index=0)

# Additional generator settings: Speed and Stability + Deck title (with today as default)
colSpeed, colStab = st.columns([1, 1])
with colSpeed:
    gen_speaking_rate = st.slider("Speed (deck)", 0.5, 1.5, 0.5, 0.05, help="0.5 par défaut (plus lent)")
with colStab:
    gen_stability = st.slider("Stability (deck)", 0.0, 1.0, 1.0, 0.05)

default_deck_title = date.today().isoformat()
deck_title = st.text_input("Deck title", value=default_deck_title, help="Nom final du paquet (suffixe)")
col1, col2 = st.columns([1, 1])
with col1:
    preview = st.button("Preview")
with col2:
    generate = st.button("Generate .apkg")

parsed = []
if (preview or generate) and tsv_text.strip():
    try:
        parsed = parse_two_column_tsv(tsv_text)
        target_index = 0 if target_col_choice.startswith("1") else 1
        user_index = 0 if user_col_choice.startswith("1") else 1
        if target_index == user_index:
            st.error("TargetLanguage and UserLanguage cannot use the same column.")
            parsed = []
        else:
            # Our backend expects A = UserLanguage, B = TargetLanguage
            if user_index == 0 and target_index == 1:
                transformed = parsed  # already A=user, B=target
            else:
                # swap A and B
                transformed = [{"A": r["B"], "B": r["A"], "row": r["row"]} for r in parsed]
            parsed = transformed
        st.success(f"Parsed {len(parsed)} rows.")
        st.dataframe([{"A": r["A"], "B": r["B"]} for r in parsed], use_container_width=True)
    except Exception as e:
        st.error(str(e))

if generate and parsed:
    try:
        # Map language label to country flag for sub-deck root
        FLAG_BY_LANG = {
            "French": "🇫🇷",
            "Italian": "🇮🇹",
            "Vietnamese Central": "🇻🇳",
            "Russian": "🇷🇺",
        }
        flag_root = FLAG_BY_LANG.get(target_language_choice, target_language_choice)
        hierarchical_deck_name = f"{flag_root}::{card_type}::{deck_title}".strip(":")
        out_path = build_simple_apkg(
            parsed,
            deck_name=hierarchical_deck_name,
            card_type=card_type.lower(),
            tts_language=target_language_choice,
            stability=gen_stability,
            speaking_rate=gen_speaking_rate,
        )

        with open(out_path, "rb") as f:
            st.download_button(
                "Download deck.apkg",
                data=f.read(),
                file_name=f"{deck_title}.apkg",
                mime="application/octet-stream",
            )
        st.success("Deck generated!")
    except Exception as e:
        st.error(f"Failed to generate deck: {e}")

# --- TTS Test (ElevenLabs) ---
st.markdown("---")
st.subheader("TTS Test (ElevenLabs)")

@st.cache_data(show_spinner=False)
def _get_groups():
    try:
        return group_voices_by_language()
    except Exception:
        return {}


tts_text = st.text_input("Texte à synthétiser", value="bonjour", help="Entrez le texte à lire à voix haute")


col_lang, col_voice = st.columns([1, 2])
with col_lang:
    groups = _get_groups()
    available_langs = sorted(groups.keys()) if groups else ["Unknown"]
    tts_language = st.selectbox("Langue", available_langs, index=available_langs.index("French") if "French" in available_langs else 0)
with col_voice:
    voice_options = groups.get(tts_language, [])
    voice_labels = [f"{name} ({vid[:6]})" for vid, name in voice_options] if voice_options else ["<aucune voix trouvée>"]
    voice_selection = st.selectbox("Voix", voice_labels, index=0)

speaking_rate = st.slider("Speed", 0.5, 1.5, 0.7, 0.05, help="0.7 par défaut (un peu plus lent que normal)")

tts_col1, tts_col2 = st.columns([1, 1])
with tts_col1:
    synth_btn = st.button("Générer l'audio")

if synth_btn:
    if not voice_options:
        st.error("Aucune voix disponible. Vérifiez ELEVENLABS_API_KEY et vos accès ElevenLabs.")
    else:
        idx = voice_labels.index(voice_selection) if voice_selection in voice_labels else 0
        voice_id = voice_options[idx][0]
        try:
            out = synthesize_text(
                tts_text,
                voice_id,
                out_dir=os.path.join(tempfile.gettempdir(), "eleven_media"),
                stability=1.0,
                similarity_boost=0.7,
                style=0.0,
                speaking_rate=speaking_rate,
            )
            with open(out["path"], "rb") as f:
                audio_bytes = f.read()
            st.audio(audio_bytes, format="audio/mp3")
            st.download_button("Télécharger MP3", data=audio_bytes, file_name=out["filename"], mime="audio/mpeg")
            st.success("Audio prêt")
        except ElevenLabsError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Erreur TTS: {e}")
