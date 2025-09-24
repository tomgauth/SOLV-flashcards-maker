from typing import List, Dict

_HEADER_TOKENS = {"French", "English", "English Auto"}

def _strip_header_if_present(text: str) -> str:
    if not text:
        return text
    lines = text.splitlines()
    if not lines:
        return text
    first = lines[0]
    parts = [p.strip() for p in first.split("\t")]
    # Consider header if every non-empty cell is one of the allowed header tokens
    non_empty = [p for p in parts if p]
    if non_empty and all(p in _HEADER_TOKENS for p in non_empty):
        return "\n".join(lines[1:])
    return text

def parse_two_column_tsv(text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not text:
        return rows
    text_to_parse = _strip_header_if_present(text)
    for i, line in enumerate(text_to_parse.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            raise ValueError(f"Line {i}: expected 2 columns separated by a tab.")
        a = parts[0].strip()
        b = parts[1].strip()
        rows.append({"A": a, "B": b, "row": str(i)})
    return rows

