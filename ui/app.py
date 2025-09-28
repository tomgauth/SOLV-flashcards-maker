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
from backend.sentence_analyzer import analyze_sentence, fr_tokens, band_from_zipf
from backend.formality_checker import check_formality_pronouns, add_formality_markers
from wordfreq import zipf_frequency
from statistics import mean

st.set_page_config(page_title="Flashcards Creator", page_icon="🃏", layout="centered")

st.title("Flashcards Creator")

def get_sentence_zipf_score(text: str) -> dict:
    """Get Zipf analysis for a French sentence."""
    if not text.strip():
        return {"zipf_score": 0.0, "difficulty_band": "Unknown", "word_count": 0}
    
    try:
        tokens = fr_tokens(text)
        if not tokens:
            return {"zipf_score": 0.0, "difficulty_band": "Unknown", "word_count": 0}
        
        zipf_scores = []
        for token in tokens:
            score = zipf_frequency(token.lower(), "fr")
            if score > 0:  # Only include words found in the frequency database
                zipf_scores.append(score)
        
        if not zipf_scores:
            return {"zipf_score": 0.0, "difficulty_band": "Unknown", "word_count": len(tokens)}
        
        mean_zipf = mean(zipf_scores)
        return {
            "zipf_score": round(mean_zipf, 2),
            "difficulty_band": band_from_zipf(mean_zipf),
            "word_count": len(tokens)
        }
    except Exception:
        return {"zipf_score": 0.0, "difficulty_band": "Error", "word_count": 0}


def analyze_phrase_set(phrases: list) -> dict:
    """Analyze the entire set of phrases for word overlap and difficulty distribution."""
    if not phrases:
        return {"total_words": 0, "unique_words": 0, "overlap_ratio": 0.0, "difficulty_distribution": {}}
    
    all_tokens = set()
    difficulty_counts = {}
    total_word_count = 0
    
    for phrase in phrases:
        if not phrase.strip():
            continue
        try:
            tokens = fr_tokens(phrase)
            total_word_count += len(tokens)
            
            for token in tokens:
                all_tokens.add(token.lower())
                score = zipf_frequency(token.lower(), "fr")
                if score > 0:
                    band = band_from_zipf(score)
                    difficulty_counts[band] = difficulty_counts.get(band, 0) + 1
        except Exception:
            continue
    
    unique_words = len(all_tokens)
    overlap_ratio = (total_word_count - unique_words) / max(total_word_count, 1)
    
    return {
        "total_words": total_word_count,
        "unique_words": unique_words,
        "overlap_ratio": round(overlap_ratio, 3),
        "difficulty_distribution": difficulty_counts
    }

st.write("Paste two-column TSV: left = A (UserLanguage), right = B (TargetLanguage)")

# Initialize session state
if 'parsed_data' not in st.session_state:
    st.session_state.parsed_data = []
if 'show_input' not in st.session_state:
    st.session_state.show_input = True
if 'enhanced_data' not in st.session_state:
    st.session_state.enhanced_data = []
if 'warning_rows' not in st.session_state:
    st.session_state.warning_rows = []

# Show input form only if we haven't parsed data yet
if st.session_state.show_input:
    tsv_text = st.text_area("1️⃣ Paste the phrases in TSV format (A\tB) here", height=220)
else:
    st.info("📋 Data has been parsed. Use the buttons below to modify or regenerate.")
    if st.button("🔄 Edit Input Data"):
        st.session_state.show_input = True
        st.session_state.parsed_data = []
        st.session_state.enhanced_data = []
        st.session_state.warning_rows = []
        st.rerun()

colType = st.columns([1])[0]
with colType:
    card_type = st.selectbox("2️⃣ Choose the card type", ["Recall", "Recognise"], index=0)

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
deck_title = st.text_input("3️⃣ Name your deck", value=default_deck_title, help="Final deck name (suffix)")
col1, col2 = st.columns([1, 1])
with col1:
    preview = st.button("Preview")
with col2:
    generate = st.button("4️⃣ Click Here to Generate the .apkg")

# Handle preview and generate buttons
if preview and st.session_state.show_input and 'tsv_text' in locals() and tsv_text.strip():
    try:
        parsed = parse_two_column_tsv(tsv_text)
        target_index = 0 if target_col_choice.startswith("1") else 1
        user_index = 0 if user_col_choice.startswith("1") else 1
        if target_index == user_index:
            st.error("TargetLanguage and UserLanguage cannot use the same column.")
        else:
            # Our backend expects A = UserLanguage, B = TargetLanguage
            if user_index == 0 and target_index == 1:
                transformed = parsed  # already A=user, B=target
            else:
                # swap A and B
                transformed = [{"A": r["B"], "B": r["A"], "row": r["row"]} for r in parsed]
            
            # Store in session state and hide input
            st.session_state.parsed_data = transformed
            st.session_state.show_input = False
            
            # Analyze and store enhanced data
            if target_language_choice == "French" and transformed:
                st.info("🔍 Analyzing French phrases with Zipf frequency scoring...")
                enhanced_parsed = []
                warning_rows = []
                
                for i, row in enumerate(transformed):
                    target_phrase = row["B"]  # Target language is column B
                    zipf_analysis = get_sentence_zipf_score(target_phrase)
                    formality_check = check_formality_pronouns(target_phrase)
                    
                    enhanced_row = {
                        "A": row["A"],
                        "B": row["B"], 
                        "Zipf Score": zipf_analysis["zipf_score"],
                        "Difficulty": zipf_analysis["difficulty_band"],
                        "Words": zipf_analysis["word_count"]
                    }
                    
                    # Add warning column if there are formality pronouns
                    if formality_check["has_pronouns"]:
                        enhanced_row["Warning"] = formality_check["warning"]
                        warning_rows.append(i)
                    else:
                        enhanced_row["Warning"] = ""
                    
                    enhanced_parsed.append(enhanced_row)
                
                st.session_state.enhanced_data = enhanced_parsed
                st.session_state.warning_rows = warning_rows
            else:
                # Non-French or no analysis needed
                enhanced_parsed = [{"A": r["A"], "B": r["B"]} for r in transformed]
                st.session_state.enhanced_data = enhanced_parsed
                st.session_state.warning_rows = []
            
            st.success(f"Parsed {len(transformed)} rows.")
            st.rerun()
            
    except Exception as e:
        st.error(str(e))

# Display stored data if available
if st.session_state.enhanced_data:
    enhanced_parsed = st.session_state.enhanced_data
    warning_rows = st.session_state.warning_rows
    parsed = st.session_state.parsed_data
    
    # Display the dataframe with conditional styling
    if warning_rows:
        st.warning(f"⚠️ Found {len(warning_rows)} phrase(s) with formal/informal 'you' pronouns that need clarification")
        
        # Auto-fix button
        if st.button("🔧 Auto-fix formality pronouns", help="Add (formal you) or (informal you) to English phrases"):
            # Create a copy of parsed data for modification
            fixed_parsed = []
            for i, row in enumerate(parsed):
                if i in warning_rows:
                    # Get the formality check for this row
                    formality_check = check_formality_pronouns(row["B"])
                    
                    # Determine what to add to the English phrase
                    english_phrase = add_formality_markers(row["A"], formality_check["pronoun_type"])
                    
                    fixed_parsed.append({
                        "A": english_phrase,
                        "B": row["B"],
                        "row": row["row"]
                    })
                else:
                    fixed_parsed.append(row)
            
            # Update the session state
            st.session_state.parsed_data = fixed_parsed
            
            # Re-analyze with fixed data
            enhanced_parsed = []
            warning_rows = []
            
            for i, row in enumerate(fixed_parsed):
                target_phrase = row["B"]
                zipf_analysis = get_sentence_zipf_score(target_phrase)
                formality_check = check_formality_pronouns(target_phrase)
                
                enhanced_row = {
                    "A": row["A"],
                    "B": row["B"], 
                    "Zipf Score": zipf_analysis["zipf_score"],
                    "Difficulty": zipf_analysis["difficulty_band"],
                    "Words": zipf_analysis["word_count"]
                }
                
                if formality_check["has_pronouns"]:
                    enhanced_row["Warning"] = formality_check["warning"]
                    warning_rows.append(i)
                else:
                    enhanced_row["Warning"] = ""
                
                enhanced_parsed.append(enhanced_row)
            
            # Update session state
            st.session_state.enhanced_data = enhanced_parsed
            st.session_state.warning_rows = warning_rows
            
            st.success("✅ Formality pronouns have been automatically added to English phrases!")
            st.rerun()
        
        # Create styled dataframe for warnings
        import pandas as pd
        df = pd.DataFrame(enhanced_parsed)
        
        # Apply orange background to warning rows
        def highlight_warnings(row):
            if row.name in warning_rows:
                return ['background-color: #ffebcd'] * len(row)  # Light orange
            return [''] * len(row)
        
        styled_df = df.style.apply(highlight_warnings, axis=1)
        st.dataframe(styled_df, use_container_width=True)
    else:
        st.dataframe(enhanced_parsed, use_container_width=True)
    
    # Show summary analysis
    st.subheader("📊 Phrase Set Analysis")
    target_phrases = [row["B"] for row in parsed if row["B"].strip()]
    analysis = analyze_phrase_set(target_phrases)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Words", analysis["total_words"])
    with col2:
        st.metric("Unique Words", analysis["unique_words"])
    with col3:
        st.metric("Word Overlap", f"{analysis['overlap_ratio']:.1%}")
    
    if analysis["difficulty_distribution"]:
        st.subheader("🎯 Difficulty Distribution")
        for band, count in sorted(analysis["difficulty_distribution"].items()):
            st.write(f"**{band}**: {count} words")

if generate and st.session_state.parsed_data:
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
            st.session_state.parsed_data,
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

# --- Sentence Analyzer ---
st.markdown("---")
st.subheader("📊 Sentence Analyzer")

analyzer_text = st.text_area(
    "Enter a French sentence to analyze", 
    value="J'ai finalement réussi à prendre rendez-vous à la préfecture de Paris.",
    height=100,
    help="Analyze word difficulty using Zipf frequency scoring"
)

# Known words input
known_words_text = st.text_input(
    "Known words (comma-separated)", 
    value="j'ai, à, de, paris, prendre",
    help="Words the student already knows (optional)"
)

analyze_btn = st.button("🔍 Analyze Sentence")

if analyze_btn and analyzer_text.strip():
    try:
        # Parse known words
        known_words = set()
        if known_words_text.strip():
            known_words = {word.strip().lower() for word in known_words_text.split(",") if word.strip()}
        
        # Analyze the sentence
        result = analyze_sentence(analyzer_text.strip(), known_words=known_words)
        
        # Display results
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Mean Zipf", f"{result['stats']['mean_zipf']}")
        with col2:
            st.metric("Known Coverage", f"{result['stats']['known_word_coverage']:.1%}")
        with col3:
            st.metric("Rare Words", f"{result['stats']['share_rare_words']:.1%}")
        
        # Flashcard candidates
        if result['flashcard_candidates']:
            st.subheader("🎯 Flashcard Candidates")
            for candidate in result['flashcard_candidates']:
                st.write(f"**{candidate['token']}** - {candidate['band']} (Zipf: {candidate['zipf']})")
        else:
            st.info("No flashcard candidates found in the learnable frequency range (3.0-4.8)")
        
        # Word details
        with st.expander("📝 Detailed Word Analysis"):
            for token in result['tokens']:
                status = "✅ Known" if token['is_known'] else "❌ Unknown"
                rarity = "🔴 Rare" if token['is_rare'] else "🟢 Common"
                st.write(f"**{token['token']}** - {token['band']} (Zipf: {token['zipf']}) - {status} - {rarity}")
        
        # Hardest and easiest words
        if result['hardest_word'] and result['easiest_word']:
            col_hard, col_easy = st.columns(2)
            with col_hard:
                st.metric(
                    "Hardest Word", 
                    f"{result['hardest_word']['token']}", 
                    f"Zipf: {result['hardest_word']['zipf']}"
                )
            with col_easy:
                st.metric(
                    "Easiest Word", 
                    f"{result['easiest_word']['token']}", 
                    f"Zipf: {result['easiest_word']['zipf']}"
                )
        
    except Exception as e:
        st.error(f"Analysis failed: {e}")

# --- TTS Test (ElevenLabs) ---
st.markdown("---")
st.subheader("🎤 Voice Selection & TTS Test (ElevenLabs)")

@st.cache_data(show_spinner=False)
def _get_all_voices():
    try:
        return list_voices()
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def _get_groups():
    try:
        return group_voices_by_language()
    except Exception:
        return {}

# Voice Selection Section
st.subheader("🎯 Select Voice by Language")

# Get all voices
all_voices = _get_all_voices()
groups = _get_groups()

# Target languages we want to show
target_languages = ["French", "Italian", "English", "Vietnamese"]

# Create columns for each target language
lang_cols = st.columns(len(target_languages))

selected_voices = {}
for i, lang in enumerate(target_languages):
    with lang_cols[i]:
        st.write(f"**{lang}**")
        
        # Get voices for this language
        lang_voices = groups.get(lang, [])
        
        if lang_voices:
            # Create dropdown options with language - code - name format
            voice_options = []
            for voice_id, name in lang_voices:
                # Find the full voice data to get language code
                voice_data = next((v for v in all_voices if v.get("voice_id") == voice_id), {})
                labels = voice_data.get("labels", {})
                
                # Extract 2-letter language code from labels
                lang_code = "Unknown"
                accent = ""
                
                # Look for 2-letter language code in labels
                import re
                for key, value in labels.items():
                    value_str = str(value).lower()
                    # Match 2-letter language code
                    match = re.search(r'\b([a-z]{2})\b', value_str)
                    if match:
                        potential_code = match.group(1)
                        if potential_code in ['fr', 'en', 'it', 'vi', 'tr', 'es', 'de', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi']:
                            lang_code = potential_code.upper()
                            break
                
                # Extract accent information
                for key, value in labels.items():
                    value_str = str(value).lower()
                    if any(acc in value_str for acc in ['american', 'british', 'parisian', 'standard', 'canadian', 'australian']):
                        accent = str(value)
                        break
                
                # Format: Language - Code - Name
                display_name = f"{lang_code}"
                if accent:
                    display_name += f" ({accent})"
                display_name += f" - {name}"
                
                voice_options.append((voice_id, display_name))
            
            # Create selectbox
            if voice_options:
                selected_voice = st.selectbox(
                    f"Choose {lang} voice:",
                    options=[opt[1] for opt in voice_options],
                    key=f"voice_{lang.lower()}",
                    help=f"Available {lang} voices"
                )
                
                # Find the selected voice ID
                selected_voice_id = next(opt[0] for opt in voice_options if opt[1] == selected_voice)
                selected_voices[lang] = selected_voice_id
            else:
                st.write("No voices found")
                selected_voices[lang] = None
        else:
            st.write("No voices found")
            selected_voices[lang] = None

# Show all available voices in an expander
with st.expander("📋 All Available Voices"):
    if all_voices:
        st.write("**Complete voice list:**")
        for voice in all_voices:
            voice_id = voice.get("voice_id", "")
            name = voice.get("name", "")
            labels = voice.get("labels", {})
            
            # Extract 2-letter language code from labels
            lang_code = "Unknown"
            accent = ""
            
            import re
            for key, value in labels.items():
                value_str = str(value).lower()
                # Match 2-letter language code
                match = re.search(r'\b([a-z]{2})\b', value_str)
                if match:
                    potential_code = match.group(1)
                    if potential_code in ['fr', 'en', 'it', 'vi', 'tr', 'es', 'de', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi']:
                        lang_code = potential_code.upper()
                        break
            
            # Extract accent information
            for key, value in labels.items():
                value_str = str(value).lower()
                if any(acc in value_str for acc in ['american', 'british', 'parisian', 'standard', 'canadian', 'australian']):
                    accent = str(value)
                    break
            
            st.write(f"**{name}** ({voice_id[:8]}...) - {lang_code}" + (f" ({accent})" if accent else ""))
    else:
        st.error("No voices available. Check your ElevenLabs API key.")

# TTS Test Section
st.subheader("🔊 TTS Test")

tts_text = st.text_input("Text to synthesize", value="bonjour", help="Enter text to convert to speech")

# Language selection for testing
test_lang = st.selectbox("Test language", target_languages, index=0)

# Get the selected voice for the test language
test_voice_id = selected_voices.get(test_lang)
if test_voice_id:
    st.info(f"Selected voice for {test_lang}: {test_voice_id[:8]}...")
else:
    st.warning(f"No voice selected for {test_lang}")

# Legacy language-based selection (keeping for compatibility)
col_lang, col_voice = st.columns([1, 2])
with col_lang:
    available_langs = sorted(groups.keys()) if groups else ["Unknown"]
    tts_language = st.selectbox("Legacy Language", available_langs, index=available_langs.index("French") if "French" in available_langs else 0)
with col_voice:
    voice_options = groups.get(tts_language, [])
    voice_labels = [f"{name} ({vid[:6]})" for vid, name in voice_options] if voice_options else ["<aucune voix trouvée>"]
    voice_selection = st.selectbox("Legacy Voice", voice_labels, index=0)

speaking_rate = st.slider("Speed", 0.5, 1.5, 0.7, 0.05, help="0.7 par défaut (un peu plus lent que normal)")

tts_col1, tts_col2 = st.columns([1, 1])
with tts_col1:
    synth_btn = st.button("🔊 Generate Audio")

if synth_btn:
    # Use the selected voice from the new interface
    if test_voice_id:
        voice_id = test_voice_id
        st.info(f"Using selected {test_lang} voice: {voice_id[:8]}...")
    else:
        # Fallback to legacy selection
        if not voice_options:
            st.error("No voice available. Check your ELEVENLABS_API_KEY and ElevenLabs access.")
        else:
            idx = voice_labels.index(voice_selection) if voice_selection in voice_labels else 0
            voice_id = voice_options[idx][0]
    
    if voice_id:
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
            st.download_button("📥 Download MP3", data=audio_bytes, file_name=out["filename"], mime="audio/mpeg")
            st.success("✅ Audio ready!")
        except ElevenLabsError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"TTS Error: {e}")
    else:
        st.error("No voice selected. Please choose a voice from the selection above.")
