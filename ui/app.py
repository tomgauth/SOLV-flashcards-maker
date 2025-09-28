import streamlit as st

# Main app entry point
st.set_page_config(
    page_title="Anki Creator Tools",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🎯 Anki Creator Tools")
st.markdown("Welcome to the Anki Creator Tools suite!")

st.markdown("""
## Available Tools

### 🏠 Flashcard Creator
Create Anki flashcards with automatic text-to-speech generation using ElevenLabs voices.

**Features:**
- TSV input for flashcard pairs
- Automatic voice assignment and rotation
- Zipf frequency analysis for difficulty assessment
- Formality pronoun detection and auto-fix
- Multiple card types (Recall/Recognize)

### 🎭 Text to Dialogue Generator
Convert text into dialogue with multiple voices for immersive learning experiences.

**Features:**
- Multi-voice dialogue generation
- Voice selection and customization
- Audio export capabilities

## Getting Started

1. Use the sidebar to navigate between tools
2. Make sure your ElevenLabs API key is configured
3. Start creating your learning materials!

---

*Built with Streamlit and powered by ElevenLabs TTS*
""")

# Sidebar info
with st.sidebar:
    st.markdown("## 🚀 Quick Start")
    st.markdown("""
    1. **Configure API Key**: Set your ElevenLabs API key in the sidebar
    2. **Choose Tool**: Select a tool from the sidebar
    3. **Create Content**: Follow the tool-specific instructions
    4. **Export**: Download your generated content
    """)
    
    st.markdown("## 📚 Tools")
    st.markdown("""
    - **🏠 Flashcard Creator**: Create Anki decks with TTS
    - **🎭 Text to Dialogue**: Generate multi-voice dialogues
    """)
    
    st.markdown("## ⚙️ Configuration")
    api_key = st.text_input(
        "ElevenLabs API Key",
        type="password",
        help="Enter your ElevenLabs API key to enable TTS features"
    )
    
    if api_key:
        st.session_state.api_key = api_key
        st.success("✅ API key configured")
    else:
        st.warning("⚠️ API key required for TTS features")
