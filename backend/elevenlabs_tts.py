# --- add near imports ---
import json

# --- replace list_voices() ---
def list_voices() -> List[Dict]:
    """Return raw list of voices from ElevenLabs SDK (dicts)."""
    client = _client()
    # get_all is legacy; search() is the current endpoint
    resp = client.voices.search()
    voices = []
    for v in getattr(resp, "voices", []) or []:
        voices.append({
            "voice_id": getattr(v, "voice_id", ""),
            "name": getattr(v, "name", ""),
            "labels": getattr(v, "labels", {}) or {},
        })
    return voices

# --- add helpers ---
def _allowed_voice_ids(client: ElevenLabs) -> Dict[str, str]:
    """IDs -> names for voices this account can use via API."""
    resp = client.voices.search()
    return {v.voice_id: v.name for v in getattr(resp, "voices", []) or []}

def _extract_status_from_exception(e: Exception) -> str:
    """Best-effort parse of ElevenLabs error payload in exception string."""
    s = str(e)
    try:
        j = json.loads(s[s.index("{"):])
        return ((j.get("detail") or {}).get("status")) or ""
    except Exception:
        return ""

def _pick_fallback_voice_id(client: ElevenLabs, avoid: Tuple[str, ...] = ()) -> str:
    for v in client.voices.search().voices:
        if v.voice_id not in avoid:
            return v.voice_id
    raise ElevenLabsError("No usable voices found on this account.")

# --- modify synthesize_text() convert call: wrap in try/except + preflight ---
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
    fallback_on_reader_only: bool = True,  # <--- NEW
) -> Dict[str, str]:
    """Synthesize one text using ElevenLabs SDK and save as MP3."""
    os.makedirs(out_dir, exist_ok=True)
    base = _hash(text, voice_id, model_id, speaking_rate)
    fname = f"{base}.mp3"
    fpath = os.path.join(out_dir, fname)

    if not os.path.exists(fpath) or speaking_rate != 1.0:
        client = _client()

        # Preflight: if the requested voice_id isn't in your usable set,
        # it's either not in "My Voices" or not API-eligible (e.g., Reader-only).
        allowed = _allowed_voice_ids(client)
        if voice_id not in allowed:
            if fallback_on_reader_only:
                voice_id = _pick_fallback_voice_id(client, avoid=(voice_id,))
            else:
                raise ElevenLabsError(
                    "Voice ID is not available via API on this account "
                    "(may be Reader-only/Iconic or not in 'My Voices')."
                )

        try:
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
        except Exception as e:
            status = _extract_status_from_exception(e)
            if status == "famous_voice_not_permitted" and fallback_on_reader_only:
                # Swap to a safe voice and retry once
                voice_id = _pick_fallback_voice_id(client, avoid=(voice_id,))
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
            else:
                # bubble up original error
                raise

        tmp_path = fpath + ".tmp"
        with open(tmp_path, "wb") as f:
            for chunk in stream:
                if isinstance(chunk, (bytes, bytearray)):
                    f.write(chunk)

        if speaking_rate != 1.0 and _HAS_PYDUB:
            try:
                audio = AudioSegment.from_file(tmp_path)
                new_rate = int(audio.frame_rate * speaking_rate)
                sped = audio._spawn(
                    audio.raw_data,
                    overrides={"frame_rate": new_rate}
                ).set_frame_rate(audio.frame_rate)
                sped.export(fpath, format="mp3")
                os.remove(tmp_path)
            except Exception:
                os.replace(tmp_path, fpath)
        else:
            os.replace(tmp_path, fpath)

    return {"filename": fname, "path": fpath}
