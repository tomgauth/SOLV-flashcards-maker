# pip install wordfreq
import re
from statistics import mean, median

# Try to import wordfreq; fall back gracefully if unavailable (e.g. missing pkg_resources)
try:
    from wordfreq import zipf_frequency  # type: ignore
    WORD_FREQ_AVAILABLE = True
except Exception:
    WORD_FREQ_AVAILABLE = False

    def zipf_frequency(*args, **kwargs) -> float:
        """
        Fallback Zipf function used when wordfreq is not installed or broken.
        Always returns 0.0 so the rest of the app can still run.
        """
        return 0.0

# --- Simple FR tokenizer that keeps apostrophes inside words ---
WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:'[A-Za-zÀ-ÖØ-öø-ÿ]+)?", flags=re.UNICODE)

def fr_tokens(text: str):
    return [m.group(0) for m in WORD_RE.finditer(text)]

# --- Difficulty banding (heuristic! based on Zipf frequency) ---
# Zipf ~6.0+ ultra common; 5.x common; 4.x mid; 3.x low; <3 rare.
def band_from_zipf(z: float):
    if z >= 5.5:  return "A1 (ultra common)"
    if z >= 4.5:  return "A2 (very common)"
    if z >= 3.5:  return "B1 (common)"
    if z >= 2.5:  return "B2–C1 (uncommon)"
    return "C1–C2 (rare)"

def normalize_token(t: str):
    # Lowercase + strip leading apostrophe chunks for lookup (j', l', qu', d', etc.)
    t = t.lower()
    return t

def analyze_sentence(
    sentence: str,
    known_words: set[str] | None = None,
    rare_threshold: float = 3.0,      # <3.0 = rare
    useful_min: float = 3.0,          # flashcard candidate range
    useful_max: float = 4.8
):
    known_words = {normalize_token(w) for w in (known_words or set())}

    toks = fr_tokens(sentence)
    rows = []
    for t in toks:
        nt = normalize_token(t)
        z = zipf_frequency(nt, "fr")  # returns 0..7-ish float; 0 if unseen
        rows.append({
            "token": t,
            "norm": nt,
            "zipf": round(z, 3),
            "band": band_from_zipf(z),
            "is_rare": z < rare_threshold,
            "is_known": nt in known_words,
        })

    # sentence-level stats
    zipfs = [r["zipf"] for r in rows] or [0.0]
    mean_zipf = round(mean(zipfs), 3)
    med_zipf  = round(median(zipfs), 3)
    share_rare = round(sum(r["is_rare"] for r in rows) / max(len(rows), 1), 3)

    # Known-word coverage
    share_known = round(sum(r["is_known"] for r in rows) / max(len(rows), 1), 3)

    # Flashcard candidates: unknown words in a "learnable" frequency band
    candidates = sorted(
        [
            r for r in rows
            if (not r["is_known"]) and (useful_min <= r["zipf"] <= useful_max)
        ],
        key=lambda r: r["zipf"]  # easiest first → hardest? flip if you prefer
    )

    summary = {
        "tokens": rows,
        "stats": {
            "num_tokens": len(rows),
            "mean_zipf": mean_zipf,
            "median_zipf": med_zipf,
            "share_rare_words": share_rare,   # 0..1
            "known_word_coverage": share_known,  # 0..1
        },
        "flashcard_candidates": [
            {"token": c["token"], "zipf": c["zipf"], "band": c["band"]}
            for c in candidates
        ],
        "hardest_word": min(rows, key=lambda r: r["zipf"]) if rows else None,
        "easiest_word": max(rows, key=lambda r: r["zipf"]) if rows else None,
    }
    return summary

# --- Example ---
if __name__ == "__main__":
    sentence = "J'ai finalement réussi à prendre rendez-vous à la préfecture de Paris."
    # Example: words your student already knows (from your deck)
    known = {"j'ai", "à", "de", "paris", "prendre"}

    result = analyze_sentence(sentence, known_words=known)
    from pprint import pprint
    pprint(result)