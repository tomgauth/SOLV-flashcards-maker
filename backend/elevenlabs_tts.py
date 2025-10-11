import hashlib
import os
from typing import Dict, List, Tuple

# pydub no longer needed - using ElevenLabs built-in speed control

from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

__all__ = [
    "ElevenLabsError",
    "list_voices",
    "voices_for_language",
    "voices_for_language_strict",
    "group_voices_by_language",
    "synthesize_text",
    "synthesize_batch",
]


ENV_API_KEY = "ELEVENLABS_API_KEY"


class ElevenLabsError(RuntimeError):
    pass


def _client() -> ElevenLabs:
    api_key = os.environ.get(ENV_API_KEY)
    if not api_key:
        raise ElevenLabsError(f"Missing {ENV_API_KEY} environment variable")
    return ElevenLabs(api_key=api_key)


def list_voices() -> List[Dict]:
    """Return raw list of voices from ElevenLabs SDK (dicts)."""
    client = _client()
    resp = client.voices.get_all()
    # SDK returns a dataclass-like object; normalize to dicts
    voices = []
    for v in getattr(resp, "voices", []) or []:
        voices.append({
            "voice_id": getattr(v, "voice_id", ""),
            "name": getattr(v, "name", ""),
            "labels": getattr(v, "labels", {}) or {},
        })
    return voices


def voices_for_language(language_hint: str) -> List[Tuple[str, str]]:
    voices = list_voices()
    hint_lower = (language_hint or "").lower()
    results: List[Tuple[str, str]] = []

    for v in voices:
        name = v.get("name", "")
        labels = v.get("labels", {}) or {}
        label_values = [str(val).lower() for val in labels.values()]
        if (
            hint_lower in name.lower()
            or hint_lower in str(labels.get("language", "")).lower()
            or hint_lower in str(labels.get("accent", "")).lower()
            or any(hint_lower in val for val in label_values)
        ):
            results.append((v.get("voice_id", ""), name))
    return results


def voices_for_language_strict(language_label: str) -> List[Tuple[str, str]]:
    """Return voices whose labels['language'] matches language_label (case-insensitive).

    Falls back to matching any label value containing language_label if 'language' is absent.
    Does NOT fall back to all voices.
    """
    label = (language_label or "").strip().lower()
    matches: List[Tuple[str, str]] = []
    for v in list_voices():
        name = v.get("name", "")
        labels = v.get("labels", {}) or {}
        lang = str(labels.get("language", "")).strip().lower()
        if lang:
            if lang == label:
                matches.append((v.get("voice_id", ""), name))
            continue
        # If exact 'language' label missing, try any label value contains
        if any(label in str(val).lower() for val in labels.values()):
            matches.append((v.get("voice_id", ""), name))
    return matches


def group_voices_by_language() -> Dict[str, List[Tuple[str, str]]]:
    """Group voices by 2-letter language code extracted from labels; 'Unknown' otherwise."""
    import re
    groups: Dict[str, List[Tuple[str, str]]] = {}
    
    # Language code to full name mapping
    lang_code_to_name = {
        "fr": "French",
        "en": "English", 
        "it": "Italian",
        "vi": "Vietnamese",
        "tr": "Turkish",
        "es": "Spanish",
        "de": "German",
        "pt": "Portuguese",
        "ru": "Russian",
        "ja": "Japanese",
        "ko": "Korean",
        "zh": "Chinese",
        "ar": "Arabic",
        "hi": "Hindi",
        "nl": "Dutch",
        "sv": "Swedish",
        "no": "Norwegian",
        "da": "Danish",
        "fi": "Finnish",
        "pl": "Polish",
        "cs": "Czech",
        "hu": "Hungarian",
        "ro": "Romanian",
        "bg": "Bulgarian",
        "hr": "Croatian",
        "sk": "Slovak",
        "sl": "Slovenian",
        "et": "Estonian",
        "lv": "Latvian",
        "lt": "Lithuanian",
        "el": "Greek",
        "he": "Hebrew",
        "th": "Thai",
        "uk": "Ukrainian",
        "ca": "Catalan",
        "eu": "Basque",
        "ga": "Irish",
        "cy": "Welsh",
        "mt": "Maltese",
        "is": "Icelandic",
        "mk": "Macedonian",
        "sq": "Albanian",
        "sr": "Serbian",
        "bs": "Bosnian",
        "me": "Montenegrin",
        "mk": "Macedonian",
        "sl": "Slovenian",
        "sk": "Slovak",
        "cs": "Czech",
        "hu": "Hungarian",
        "ro": "Romanian",
        "bg": "Bulgarian",
        "hr": "Croatian",
        "et": "Estonian",
        "lv": "Latvian",
        "lt": "Lithuanian",
        "el": "Greek",
        "he": "Hebrew",
        "th": "Thai",
        "uk": "Ukrainian",
        "ca": "Catalan",
        "eu": "Basque",
        "ga": "Irish",
        "cy": "Welsh",
        "mt": "Maltese",
        "is": "Icelandic",
        "mk": "Macedonian",
        "sq": "Albanian",
        "sr": "Serbian",
        "bs": "Bosnian",
        "me": "Montenegrin"
    }
    
    for v in list_voices():
        labels = v.get("labels", {}) or {}
        voice_id = v.get("voice_id", "")
        name = v.get("name", "")
        
        # Look for 2-letter language code in labels
        lang_code = None
        for key, value in labels.items():
            # Convert to string and look for 2-letter code pattern
            value_str = str(value).lower()
            # Match 2-letter language code with spaces before and after
            match = re.search(r'\b([a-z]{2})\b', value_str)
            if match:
                potential_code = match.group(1)
                if potential_code in lang_code_to_name:
                    lang_code = potential_code
                    break
        
        # If no language code found in labels, try to extract from voice name
        if not lang_code:
            name_lower = name.lower()
            # Look for language indicators in the name
            if any(indicator in name_lower for indicator in ['french', 'français']):
                lang_code = 'fr'
            elif any(indicator in name_lower for indicator in ['english', 'american', 'british']):
                lang_code = 'en'
            elif any(indicator in name_lower for indicator in ['italian', 'italiano']):
                lang_code = 'it'
            elif any(indicator in name_lower for indicator in ['vietnamese', 'vietnam']):
                lang_code = 'vi'
            elif any(indicator in name_lower for indicator in ['turkish', 'türkçe']):
                lang_code = 'tr'
            elif any(indicator in name_lower for indicator in ['spanish', 'español']):
                lang_code = 'es'
            elif any(indicator in name_lower for indicator in ['german', 'deutsch']):
                lang_code = 'de'
            elif any(indicator in name_lower for indicator in ['portuguese', 'português']):
                lang_code = 'pt'
            elif any(indicator in name_lower for indicator in ['russian', 'русский']):
                lang_code = 'ru'
            elif any(indicator in name_lower for indicator in ['japanese', '日本語']):
                lang_code = 'ja'
            elif any(indicator in name_lower for indicator in ['korean', '한국어']):
                lang_code = 'ko'
            elif any(indicator in name_lower for indicator in ['chinese', '中文']):
                lang_code = 'zh'
            elif any(indicator in name_lower for indicator in ['arabic', 'العربية']):
                lang_code = 'ar'
            elif any(indicator in name_lower for indicator in ['hindi', 'हिन्दी']):
                lang_code = 'hi'
        
        # Use the full language name as the key
        if lang_code:
            key = lang_code_to_name.get(lang_code, lang_code.upper())
        else:
            key = "Unknown"
            
        groups.setdefault(key, []).append((voice_id, name))
    
    return groups


def _hash(text: str, voice_id: str, model_id: str, speaking_rate: float, stability: float, similarity_boost: float, style: float, use_speaker_boost: bool, output_format: str) -> str:
    base = f"{text}\u241f{voice_id}\u241f{model_id}\u241f{speaking_rate}\u241f{stability}\u241f{similarity_boost}\u241f{style}\u241f{use_speaker_boost}\u241f{output_format}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()[:12]


def synthesize_text(
    text: str,
    voice_id: str,
    out_dir: str,
    *,
    model_id: str = "eleven_multilingual_v2",
    stability: float = 0.7,
    similarity_boost: float = 0.7,
    style: float = 0.0,
    use_speaker_boost: bool = True,
    speaking_rate: float = 1.0,
    output_format: str = "mp3_22050_32",
) -> Dict[str, str]:
    """Synthesize one text using ElevenLabs SDK and save as MP3."""
    os.makedirs(out_dir, exist_ok=True)
    # Clamp speed to ElevenLabs supported range for consistent caching
    clamped_speed = max(0.7, min(1.2, speaking_rate))
    base = _hash(text, voice_id, model_id, clamped_speed, stability, similarity_boost, style, use_speaker_boost, output_format)
    fname = f"{base}.mp3"
    fpath = os.path.join(out_dir, fname)

    if not os.path.exists(fpath):
        client = _client()
        
        # Use ElevenLabs built-in speed control (range: 0.7-1.2)
        if clamped_speed != speaking_rate:
            print(f"Speed {speaking_rate} clamped to {clamped_speed} (ElevenLabs range: 0.7-1.2)")
        
        print(f"Generating TTS with speed={clamped_speed}")
        stream = client.text_to_speech.convert(
            voice_id=voice_id,
            optimize_streaming_latency="0",
            output_format=output_format,
            model_id=model_id,
            text=text,
            voice_settings=VoiceSettings(
                stability=stability,
                similarity_boost=similarity_boost,
                style=style,
                use_speaker_boost=use_speaker_boost,
                speed=clamped_speed,  # Use ElevenLabs built-in speed control
            ),
        )
        
        tmp_path = fpath + ".tmp"
        with open(tmp_path, "wb") as f:
            for chunk in stream:
                if isinstance(chunk, (bytes, bytearray)):
                    f.write(chunk)

        os.replace(tmp_path, fpath)

    return {"filename": fname, "path": fpath}


def synthesize_batch(
    texts: List[str],
    voice_id: str,
    out_dir: str,
    *,
    model_id: str = "eleven_multilingual_v2",
    stability: float = 0.7,
    similarity_boost: float = 0.7,
    style: float = 0.0,
    use_speaker_boost: bool = True,
    speaking_rate: float = 1.0,
    output_format: str = "mp3_22050_32",
) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    for t in texts:
        results.append(
            synthesize_text(
                t,
                voice_id,
                out_dir,
                model_id=model_id,
                stability=stability,
                similarity_boost=similarity_boost,
                style=style,
                use_speaker_boost=use_speaker_boost,
                speaking_rate=speaking_rate,
                output_format=output_format,
            )
        )
    return results

