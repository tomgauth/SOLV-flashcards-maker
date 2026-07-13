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


class ElevenLabsError(RuntimeError):
    pass


# Language code to full name mapping (used to group and match voices)
LANG_CODE_TO_NAME: Dict[str, str] = {
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
}

# Reverse mapping: full language name (lowercase) -> 2-letter code
NAME_TO_LANG_CODE: Dict[str, str] = {name.lower(): code for code, name in LANG_CODE_TO_NAME.items()}


def _client(api_key: str | None) -> ElevenLabs:
    key = (api_key or "").strip()
    if not key:
        raise ElevenLabsError("Missing ElevenLabs API key. Please enter your own API key.")
    return ElevenLabs(api_key=key)


def list_voices(api_key: str | None) -> List[Dict]:
    """Return raw list of voices from ElevenLabs SDK (dicts)."""
    client = _client(api_key)
    resp = client.voices.get_all()
    # SDK returns a dataclass-like object; normalize to dicts
    voices = []
    for v in getattr(resp, "voices", []) or []:
        # Language codes verified by ElevenLabs (most reliable source, when present).
        # Entries look like {language: 'fr', locale: 'fr-FR', accent: ...}.
        languages = set()
        for vl in getattr(v, "verified_languages", None) or []:
            code = str(getattr(vl, "language", "") or "").strip().lower()
            if code:
                languages.add(code.split("-")[0])
        fine_tuning = getattr(v, "fine_tuning", None)
        ft_lang = str(getattr(fine_tuning, "language", "") or "").strip().lower() if fine_tuning else ""
        if ft_lang:
            languages.add(ft_lang.split("-")[0])
        voices.append({
            "voice_id": getattr(v, "voice_id", ""),
            "name": getattr(v, "name", ""),
            "labels": getattr(v, "labels", {}) or {},
            "languages": sorted(languages),
        })
    return voices


def voices_for_language(language_hint: str, api_key: str | None) -> List[Tuple[str, str]]:
    voices = list_voices(api_key)
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


def voices_for_language_strict(language_label: str, api_key: str | None) -> List[Tuple[str, str]]:
    """Return voices matching language_label (case-insensitive).

    Checks the voice's verified language codes first, then labels['language'],
    then any label value containing language_label.
    Does NOT fall back to all voices.
    """
    label = (language_label or "").strip().lower()
    label_code = NAME_TO_LANG_CODE.get(label)
    matches: List[Tuple[str, str]] = []
    for v in list_voices(api_key):
        name = v.get("name", "")
        # Verified language codes from the API (e.g. ['en', 'fr'])
        if label_code and label_code in (v.get("languages") or []):
            matches.append((v.get("voice_id", ""), name))
            continue
        labels = v.get("labels", {}) or {}
        lang = str(labels.get("language", "")).strip().lower()
        if lang:
            if lang == label or lang == label_code:
                matches.append((v.get("voice_id", ""), name))
            continue
        # If exact 'language' label missing, try any label value contains
        if any(label in str(val).lower() for val in labels.values()):
            matches.append((v.get("voice_id", ""), name))
    return matches


def group_voices_by_language(api_key: str | None) -> Dict[str, List[Tuple[str, str]]]:
    """Group voices by language.

    Detection order, per voice:
    1. verified language codes returned by the ElevenLabs API,
    2. a 2-letter language code found in the voice labels,
    3. language words in the voice name.
    A multilingual voice appears in every language group it supports;
    voices with no detectable language go under 'Unknown'.
    """
    import re
    groups: Dict[str, List[Tuple[str, str]]] = {}

    for v in list_voices(api_key):
        labels = v.get("labels", {}) or {}
        voice_id = v.get("voice_id", "")
        name = v.get("name", "")

        # 1) Verified language codes from the API (a voice can support several)
        lang_codes = {c for c in (v.get("languages") or []) if c in LANG_CODE_TO_NAME}

        # 2) Look for 2-letter language code in labels
        lang_code = None
        if not lang_codes:
            for key, value in labels.items():
                # Convert to string and look for 2-letter code pattern
                value_str = str(value).lower()
                # Match 2-letter language code with spaces before and after
                match = re.search(r'\b([a-z]{2})\b', value_str)
                if match:
                    potential_code = match.group(1)
                    if potential_code in LANG_CODE_TO_NAME:
                        lang_code = potential_code
                        break

        # 3) If no language code found in labels, try to extract from voice name
        if not lang_codes and not lang_code:
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

        if lang_code:
            lang_codes.add(lang_code)

        # Use the full language name(s) as key(s); a multilingual voice
        # is listed under every language it supports
        keys = {LANG_CODE_TO_NAME.get(c, c.upper()) for c in lang_codes} or {"Unknown"}
        for key in sorted(keys):
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
    api_key: str | None = None,
) -> Dict[str, str]:
    """Synthesize one text using ElevenLabs SDK and save as MP3."""
    os.makedirs(out_dir, exist_ok=True)
    # Clamp speed to ElevenLabs supported range for consistent caching
    clamped_speed = max(0.7, min(1.2, speaking_rate))
    base = _hash(text, voice_id, model_id, clamped_speed, stability, similarity_boost, style, use_speaker_boost, output_format)
    fname = f"{base}.mp3"
    fpath = os.path.join(out_dir, fname)

    if not os.path.exists(fpath):
        client = _client(api_key)
        
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
    api_key: str | None = None,
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
                api_key=api_key,
            )
        )
    return results

