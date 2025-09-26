import os
import random
import tempfile
from typing import List, Dict

import genanki
from .note_models import build_recall_model, build_recognize_model
from .elevenlabs_tts import synthesize_text, voices_for_language_strict, list_voices


def build_simple_apkg(
    pairs: List[Dict[str, str]],
    deck_name: str = "Flashcards Creator Deck",
    *,
    card_type: str = "recall",
    tts_language: str = "French",
    voice_ids: List[str] | None = None,
    stability: float = 0.7,
    similarity_boost: float = 0.7,
    style: float = 0.0,
    use_speaker_boost: bool = True,
    speaking_rate: float = 1.0,
) -> str:
    print(f"[build_simple_apkg] start | pairs={len(pairs)} | deck='{deck_name}' | card_type={card_type} | tts_language={tts_language}")
    # Choose model by card_type (support 'recognise' and 'recognize')
    card_type_norm = (card_type or "").strip().lower()
    if card_type_norm == "recall":
        model = build_recall_model()
    else:
        model = build_recognize_model()

    deck_id = random.randrange(1_000_000_000, 9_999_999_999)
    deck = genanki.Deck(deck_id, deck_name)

    # Prepare TTS voices list when needed (for both recall and recognize, we fill TargetAudio)
    resolved_voice_ids: List[str] = []
    VOICE_WHITELIST_PREFIXES: Dict[str, List[str]] = {
        # Only use these IDs (prefix match) for the given language label
        "Vietnamese Central": ["RmcV9c"],
    }
    if voice_ids:
        resolved_voice_ids = voice_ids
    else:
        # If language has an explicit whitelist, enforce it strictly
        if tts_language in VOICE_WHITELIST_PREFIXES:
            prefixes = VOICE_WHITELIST_PREFIXES[tts_language]
            all_vs = list_voices()
            allowed = [v.get("voice_id", "") for v in all_vs if any(v.get("voice_id", "").startswith(p) for p in prefixes)]
            resolved_voice_ids = [vid for vid in allowed if vid]
            print(f"[build_simple_apkg] whitelist applied for '{tts_language}': {resolved_voice_ids}")
        else:
            strict = voices_for_language_strict(tts_language)
            if strict:
                resolved_voice_ids = [vid for vid, _ in strict]
            else:
                # fallback to any available voices
                resolved_voice_ids = [v.get("voice_id", "") for v in list_voices()]

        # Filter out "famous" voices (not permitted) based on labels when available
        try:
            all_vs = list_voices()
            famous_ids = {v.get("voice_id", "") for v in all_vs if str((v.get("labels") or {}).get("category", "")).lower() == "famous"}
            if famous_ids:
                before = len(resolved_voice_ids)
                resolved_voice_ids = [vid for vid in resolved_voice_ids if vid not in famous_ids]
                after = len(resolved_voice_ids)
                if before != after:
                    print(f"[build_simple_apkg] filtered famous voices: {before-after} removed")
        except Exception:
            # If labels are unavailable, continue; per-voice try/except below handles 401s
            pass
    print(f"[build_simple_apkg] resolved voices: {len(resolved_voice_ids)} candidates")

    media_files: List[str] = []
    tmp_media_dir = os.path.join(tempfile.gettempdir(), "anki_media")

    for idx, r in enumerate(pairs):
        user_language = r.get("A", "")
        target_language = r.get("B", "")

        # Synthesize target text with failover across voices
        audio_info = {"filename": "", "path": ""}
        if target_language and resolved_voice_ids:
            candidate_voices = list(resolved_voice_ids)
            random.shuffle(candidate_voices)
            last_error = None
            for voice_id in candidate_voices:
                try:
                    print(f"[build_simple_apkg] row {idx} | try voice={voice_id[:8]} | text='{target_language[:40]}'")
                    audio_info = synthesize_text(
                        target_language,
                        voice_id,
                        out_dir=tmp_media_dir,
                        stability=stability,
                        similarity_boost=similarity_boost,
                        style=style,
                        use_speaker_boost=use_speaker_boost,
                        speaking_rate=speaking_rate,
                    )
                    if audio_info.get("path"):
                        media_files.append(audio_info["path"])
                        print(f"[build_simple_apkg] row {idx} | OK voice={voice_id[:8]} | file={audio_info['filename']}")
                        break
                except Exception as e:
                    last_error = e
                    print(f"[build_simple_apkg] row {idx} | voice failed {voice_id[:8]} | {e}")
            if not audio_info.get("filename") and last_error:
                print(f"[build_simple_apkg] row {idx} | all voices failed | {last_error}")

        target_audio_field = f"[sound:{audio_info['filename']}]" if audio_info.get("filename") else ""

        fields = [
            user_language,          # UserLanguage
            target_audio_field,     # TargetAudio (filename like [sound:...])
            target_language,        # TargetLanguage
            "",                    # TargetIPA
            "",                    # Notes
            card_type,              # card_type (e.g., 'recall' or 'recognise')
        ]
        note = genanki.Note(model=model, fields=fields)
        deck.add_note(note)

    pkg = genanki.Package(deck)
    if media_files:
        pkg.media_files = media_files
    out_path = os.path.join(tempfile.gettempdir(), f"deck_{deck_id}.apkg")
    print(f"[build_simple_apkg] writing package | media_files={len(media_files)} | out={out_path}")
    pkg.write_to_file(out_path)
    print(f"[build_simple_apkg] done")
    return out_path

