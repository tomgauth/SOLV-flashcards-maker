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

st.write("Paste TSV data: Column 1 = A (UserLanguage), Column 2 = B (TargetLanguage), Column 3 = Notes (optional)")

# Initialize session state
if 'parsed_data' not in st.session_state:
    st.session_state.parsed_data = []
if 'show_input' not in st.session_state:
    st.session_state.show_input = True
if 'enhanced_data' not in st.session_state:
    st.session_state.enhanced_data = []
if 'warning_rows' not in st.session_state:
    st.session_state.warning_rows = []
if 'voice_selections' not in st.session_state:
    st.session_state.voice_selections = {}

# Show input form only if we haven't parsed data yet
if st.session_state.show_input:
    tsv_text = st.text_area("1️⃣ Paste the phrases in TSV format (A\tB\tNotes) here", height=220, help="Tab-separated values: Column 1 = User Language, Column 2 = Target Language, Column 3 = Notes (optional)")
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
    target_language_choice = st.selectbox("Target language label", ["French", "Italian", "Vietnamese", "Russian", "Chinese", "English"], index=0)

# Additional generator settings: Stability + Deck title (with today as default)
gen_stability = st.slider("Stability (deck)", 0.0, 1.0, 1.0, 0.05, help="Voice stability (1.0 = most stable)")

default_deck_title = date.today().isoformat()
deck_title = st.text_input("3️⃣ Name your deck", value=default_deck_title, help="Final deck name (suffix)")
col1, col2 = st.columns([1, 1])
with col1:
    preview = st.button("✅ Preview")
with col2:
    # Only enable generate button if preview has been completed
    generate_enabled = st.session_state.enhanced_data and len(st.session_state.enhanced_data) > 0
    generate = st.button("⬇️ Click Here to Generate the .apkg", disabled=not generate_enabled)

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
                # swap A and B, but preserve Notes
                transformed = [{"A": r["B"], "B": r["A"], "Notes": r.get("Notes", ""), "row": r["row"]} for r in parsed]
            
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
                        "Notes": row.get("Notes", ""),
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
                enhanced_parsed = [{"A": r["A"], "B": r["B"], "Notes": r.get("Notes", "")} for r in transformed]
                st.session_state.enhanced_data = enhanced_parsed
                st.session_state.warning_rows = []
            
            # Initialize voice selections for each row
            st.session_state.voice_selections = {}
            
            st.success(f"Parsed {len(transformed)} rows.")
            st.rerun()
            
    except Exception as e:
        st.error(str(e))

# Display stored data if available
if st.session_state.enhanced_data:
    enhanced_parsed = st.session_state.enhanced_data
    warning_rows = st.session_state.warning_rows
    parsed = st.session_state.parsed_data
    
    # Get available voices for the target language
    @st.cache_data(show_spinner=False)
    def _get_voices_for_language(language):
        try:
            groups = group_voices_by_language()
            return groups.get(language, [])
        except Exception:
            return []
    
    available_voices = _get_voices_for_language(target_language_choice)
    
    # Create voice options for dropdown
    voice_options = []
    for voice_id, name in available_voices:
        # Extract language code and accent from voice name
        import re
        lang_code = "Unknown"
        accent = ""
        
        name_lower = name.lower()
        if any(indicator in name_lower for indicator in ['french', 'français']):
            lang_code = "FR"
        elif any(indicator in name_lower for indicator in ['english', 'american', 'british']):
            lang_code = "EN"
        elif any(indicator in name_lower for indicator in ['italian', 'italiano']):
            lang_code = "IT"
        elif any(indicator in name_lower for indicator in ['vietnamese', 'vietnam']):
            lang_code = "VI"
        elif any(indicator in name_lower for indicator in ['turkish', 'türkçe']):
            lang_code = "TR"
        elif any(indicator in name_lower for indicator in ['spanish', 'español']):
            lang_code = "ES"
        elif any(indicator in name_lower for indicator in ['german', 'deutsch']):
            lang_code = "DE"
        elif any(indicator in name_lower for indicator in ['portuguese', 'português']):
            lang_code = "PT"
        elif any(indicator in name_lower for indicator in ['russian', 'русский']):
            lang_code = "RU"
        elif any(indicator in name_lower for indicator in ['chinese', '中文']):
            lang_code = "ZH"
        
        # Extract accent information
        if any(acc in name_lower for acc in ['american', 'british', 'parisian', 'standard', 'canadian', 'australian']):
            if 'american' in name_lower:
                accent = "American"
            elif 'british' in name_lower:
                accent = "British"
            elif 'parisian' in name_lower:
                accent = "Parisian"
            elif 'standard' in name_lower:
                accent = "Standard"
            elif 'canadian' in name_lower:
                accent = "Canadian"
            elif 'australian' in name_lower:
                accent = "Australian"
        
        # Format display name
        display_name = f"{lang_code}"
        if accent:
            display_name += f" ({accent})"
        display_name += f" - {name}"
        
        voice_options.append((voice_id, display_name))
    
    # Automatically assign voices in rotation for variety
    if voice_options:
        for i, row in enumerate(enhanced_parsed):
            # Rotate through available voices
            voice_index = i % len(voice_options)
            selected_voice_id = voice_options[voice_index][0]
            selected_voice_name = voice_options[voice_index][1]
            st.session_state.voice_selections[i] = selected_voice_id
            
            # Update the voice display in the row
            row["Voice"] = selected_voice_name
    else:
        st.error(f"No voices available for {target_language_choice}. Check your ElevenLabs API key.")
    
    # Show warning if any formal/informal pronouns found
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
                        "Notes": row.get("Notes", ""),
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
                    "Notes": row.get("Notes", ""),
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
        
    # Display the single preview table with voice assignments
    st.subheader("📋 Preview with Voice Assignments")
    if warning_rows:
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
    
    # Generate button - right below the table
    st.markdown("---")
    generate = st.button("🎯 Generate .apkg", type="primary", disabled=not st.session_state.enhanced_data)

if generate and st.session_state.parsed_data:
    try:
        # Map language label to country flag for sub-deck root
        FLAG_BY_LANG = {
            "French": "🇫🇷",
            "Italian": "🇮🇹",
            "Vietnamese": "🇻🇳",
            "Russian": "🇷🇺",
            "Chinese": "🇨🇳",
            "English": "🇺🇸",
        }
        flag_root = FLAG_BY_LANG.get(target_language_choice, target_language_choice)
        hierarchical_deck_name = f"{flag_root}::{card_type}::{deck_title}".strip(":")
        
        # Add voice selections to parsed data
        parsed_with_voices = []
        for i, row in enumerate(st.session_state.parsed_data):
            row_with_voice = row.copy()
            row_with_voice["voice_id"] = st.session_state.voice_selections.get(i)
            parsed_with_voices.append(row_with_voice)
        
        # Initialize progress tracking
        total_cards = len(parsed_with_voices)
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text(f"🎯 Initializing flashcard generation... (0/{total_cards})")
        
        # Create a callback function to update progress
        def update_progress(current_card: int, total_cards: int, current_text: str = ""):
            progress = current_card / total_cards
            progress_bar.progress(progress)
            if current_card < total_cards:
                status_text.text(f"🎙️ Generating audio for card {current_card + 1}/{total_cards}: {current_text[:40]}...")
            else:
                status_text.text(f"📦 Finalizing .apkg file... ({total_cards}/{total_cards})")
        
        out_path = build_simple_apkg(
            parsed_with_voices,
            deck_name=hierarchical_deck_name,
            card_type=card_type.lower(),
            tts_language=target_language_choice,
            stability=gen_stability,
            speaking_rate=1.0,  # Use default natural speed
            use_preview_voices=True,  # Use the voice assignments from the preview table
            progress_callback=update_progress,  # Pass the progress callback
        )
        
        # Complete the progress bar
        progress_bar.progress(1.0)
        status_text.text(f"✅ Successfully generated {total_cards} flashcards!")

        # Show success banner
        st.success("🎉 Deck generated successfully!")
        
        # Download button
        with open(out_path, "rb") as f:
            st.download_button(
                "📥 Download deck.apkg",
                data=f.read(),
                file_name=f"{deck_title}.apkg",
                mime="application/octet-stream",
                type="primary"
            )
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
st.subheader("🎤 Text-to-Speech Generator")

@st.cache_data(show_spinner=False)
def _get_groups():
    try:
        return group_voices_by_language()
    except Exception:
        return {}

# Get available voices grouped by language
groups = _get_groups()

# Input text
tts_text = st.text_input("📝 Text to convert to speech", value="bonjour", help="Enter text to convert to speech")

# Language and voice selection
col_lang, col_voice = st.columns([1, 2])

with col_lang:
    # Get available languages (sorted, with French first if available)
    available_langs = sorted(groups.keys()) if groups else ["Unknown"]
    if "French" in available_langs:
        french_index = available_langs.index("French")
        available_langs.insert(0, available_langs.pop(french_index))
    
    selected_language = st.selectbox("🌍 Language", available_langs, index=0)

with col_voice:
    # Get voices for selected language
    lang_voices = groups.get(selected_language, [])
    
    if lang_voices:
        # Create voice options with language code and accent info
        voice_options = []
        for voice_id, name in lang_voices:
            # Extract language code and accent from voice name/labels
            import re
            lang_code = "Unknown"
            accent = ""
            
            # Look for language indicators in the name
            name_lower = name.lower()
            if any(indicator in name_lower for indicator in ['french', 'français']):
                lang_code = "FR"
            elif any(indicator in name_lower for indicator in ['english', 'american', 'british']):
                lang_code = "EN"
            elif any(indicator in name_lower for indicator in ['italian', 'italiano']):
                lang_code = "IT"
            elif any(indicator in name_lower for indicator in ['vietnamese', 'vietnam']):
                lang_code = "VI"
            elif any(indicator in name_lower for indicator in ['turkish', 'türkçe']):
                lang_code = "TR"
            elif any(indicator in name_lower for indicator in ['spanish', 'español']):
                lang_code = "ES"
            elif any(indicator in name_lower for indicator in ['german', 'deutsch']):
                lang_code = "DE"
            elif any(indicator in name_lower for indicator in ['portuguese', 'português']):
                lang_code = "PT"
            elif any(indicator in name_lower for indicator in ['russian', 'русский']):
                lang_code = "RU"
            elif any(indicator in name_lower for indicator in ['chinese', '中文']):
                lang_code = "ZH"
            
            # Extract accent information
            if any(acc in name_lower for acc in ['american', 'british', 'parisian', 'standard', 'canadian', 'australian']):
                if 'american' in name_lower:
                    accent = "American"
                elif 'british' in name_lower:
                    accent = "British"
                elif 'parisian' in name_lower:
                    accent = "Parisian"
                elif 'standard' in name_lower:
                    accent = "Standard"
                elif 'canadian' in name_lower:
                    accent = "Canadian"
                elif 'australian' in name_lower:
                    accent = "Australian"
            
            # Format display name
            display_name = f"{lang_code}"
            if accent:
                display_name += f" ({accent})"
            display_name += f" - {name}"
            
            voice_options.append((voice_id, display_name))
        
        selected_voice = st.selectbox("🎤 Voice", [opt[1] for opt in voice_options], index=0)
        selected_voice_id = next(opt[0] for opt in voice_options if opt[1] == selected_voice)
    else:
        st.write("No voices found for this language")
        selected_voice_id = None

# Generate button
generate_btn = st.button("🔊 Generate Audio", type="primary")

# Audio generation and playback
if generate_btn:
    if not selected_voice_id:
        st.error("No voice selected. Please choose a language and voice.")
    elif not tts_text.strip():
        st.error("Please enter text to convert to speech.")
    else:
        try:
            with st.spinner("Generating audio..."):
                out = synthesize_text(
                    tts_text,
                    selected_voice_id,
                    out_dir=os.path.join(tempfile.gettempdir(), "eleven_media"),
                    stability=1.0,
                    similarity_boost=0.7,
                    style=0.0,
                    speaking_rate=1.0,  # Use default natural speed
                )
                
            with open(out["path"], "rb") as f:
                audio_bytes = f.read()
                
            # Play audio
            st.audio(audio_bytes, format="audio/mp3")
                
            # Download button
            st.download_button(
                "📥 Download MP3", 
                data=audio_bytes, 
                file_name=out["filename"], 
                mime="audio/mpeg"
            )
                
            st.success("✅ Audio ready!")
                
        except ElevenLabsError as e:
            st.error(f"ElevenLabs Error: {e}")
        except Exception as e:
            st.error(f"TTS Error: {e}")

# Show all available voices in an expander
with st.expander("📋 All Available Voices"):
    if groups:
        for lang, voices in sorted(groups.items()):
            st.write(f"**{lang}** ({len(voices)} voices)")
            for voice_id, name in voices:
                st.write(f"  • {name} ({voice_id[:8]}...)")
    else:
        st.error("No voices available. Check your ElevenLabs API key.")

# Navigation to other tools
st.markdown("---")
st.subheader("🔗 Other Tools")

col1, col2 = st.columns(2)
with col1:
    if st.button("🎭 Text to Dialogue Generator", help="Convert text into dialogue with multiple voices"):
        st.info("🎭 **Text to Dialogue Generator** is available as a separate tool. Run `streamlit run ui/text_to_dialogue.py` to access it.")

with col2:
    st.write("More tools coming soon...")
