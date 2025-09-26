import hashlib
import os
from typing import Dict, List, Tuple

try:
    from pydub import AudioSegment
    _HAS_PYDUB = True
except Exception:
    _HAS_PYDUB = False

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
    """Group voices by labels['language'] when available; 'Unknown' otherwise."""
    groups: Dict[str, List[Tuple[str, str]]] = {}
    for v in list_voices():
        labels = v.get("labels", {}) or {}
        lang = str(labels.get("language", "Unknown")).strip() or "Unknown"
        key = lang
        groups.setdefault(key, []).append((v.get("voice_id", ""), v.get("name", "")))
    return groups


def _hash(text: str, voice_id: str, model_id: str, speaking_rate: float) -> str:
    base = f"{text}\u241f{voice_id}\u241f{model_id}\u241f{speaking_rate}"
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
    base = _hash(text, voice_id, model_id, speaking_rate)
    fname = f"{base}.mp3"
    fpath = os.path.join(out_dir, fname)

    if not os.path.exists(fpath) or speaking_rate != 1.0:
        client = _client()
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
            ),
        )
        tmp_path = fpath + ".tmp"
        with open(tmp_path, "wb") as f:
            for chunk in stream:
                if isinstance(chunk, (bytes, bytearray)):
                    f.write(chunk)

        if speaking_rate != 1.0 and _HAS_PYDUB:
            try:
                audio = AudioSegment.from_file(tmp_path)
                new_rate = int(audio.frame_rate * speaking_rate)
                sped = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(audio.frame_rate)
                sped.export(fpath, format="mp3")
                os.remove(tmp_path)
            except Exception:
                os.replace(tmp_path, fpath)
        else:
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

