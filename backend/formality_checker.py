"""Formality pronoun checker for French text analysis."""

import re
from typing import Dict


def check_formality_pronouns(text: str) -> Dict:
    """Check for formal/informal 'you' pronouns in French text.
    
    Args:
        text: French text to analyze
        
    Returns:
        Dictionary with:
        - has_pronouns: bool - whether any formality pronouns were found
        - pronoun_type: str or None - 'informal', 'formal', 'mixed', or None
        - warning: str or None - warning message for the user
    """
    if not text.strip():
        return {"has_pronouns": False, "pronoun_type": None, "warning": None}
    
    # Normalize text for checking
    text_lower = text.lower()
    
    # Create word boundary regex patterns for pronouns
    # Use negative lookbehind/lookahead to ensure we don't match within words
    # (?<![a-zA-Zàâäéèêëïîôöùûüÿç]) = not preceded by letter
    # (?![a-zA-Zàâäéèêëïîôöùûüÿç]) = not followed by letter
    informal_patterns = [
        r'(?<![a-zA-Zàâäéèêëïîôöùûüÿç])tu(?![a-zA-Zàâäéèêëïîôöùûüÿç])',      # tu
        r'(?<![a-zA-Zàâäéèêëïîôöùûüÿç])t\'(?![a-zA-Zàâäéèêëïîôöùûüÿç])',     # t' (with apostrophe)
        r'(?<![a-zA-Zàâäéèêëïîôöùûüÿç])te(?![a-zA-Zàâäéèêëïîôöùûüÿç])',      # te
        r'(?<![a-zA-Zàâäéèêëïîôöùûüÿç])ton(?![a-zA-Zàâäéèêëïîôöùûüÿç])',     # ton
        r'(?<![a-zA-Zàâäéèêëïîôöùûüÿç])ta(?![a-zA-Zàâäéèêëïîôöùûüÿç])',      # ta
        r'(?<![a-zA-Zàâäéèêëïîôöùûüÿç])tes(?![a-zA-Zàâäéèêëïîôöùûüÿç])'      # tes
    ]
    
    # For formal pronouns, exclude cases where "vous" is followed by a verb (like "tutoyer")
    formal_patterns = [
        r'(?<![a-zA-Zàâäéèêëïîôöùûüÿç])vous(?![a-zA-Zàâäéèêëïîôöùûüÿç])(?!\s+\w+er\b)',    # vous (but not followed by verb ending in -er)
        r'(?<![a-zA-Zàâäéèêëïîôöùûüÿç])vos(?![a-zA-Zàâäéèêëïîôöùûüÿç])',     # vos
        r'(?<![a-zA-Zàâäéèêëïîôöùûüÿç])votre(?![a-zA-Zàâäéèêëïîôöùûüÿç])'    # votre
    ]
    
    # Check for informal pronouns using regex
    has_informal = any(re.search(pattern, text_lower) for pattern in informal_patterns)
    
    # Check for formal pronouns using regex
    has_formal = any(re.search(pattern, text_lower) for pattern in formal_patterns)
    
    if has_informal and has_formal:
        return {
            "has_pronouns": True,
            "pronoun_type": "mixed",
            "warning": "⚠️ Mixed formal/informal pronouns detected"
        }
    elif has_informal:
        return {
            "has_pronouns": True,
            "pronoun_type": "informal",
            "warning": "⚠️ Informal 'you' (tu/t'/te/ton) - specify if formal or informal"
        }
    elif has_formal:
        return {
            "has_pronouns": True,
            "pronoun_type": "formal",
            "warning": "⚠️ Formal 'you' (vous/vos/votre) - specify if formal or informal"
        }
    else:
        return {"has_pronouns": False, "pronoun_type": None, "warning": None}


def add_formality_markers(english_phrase: str, pronoun_type: str) -> str:
    """Add formality markers to English phrases based on pronoun type.
    
    Args:
        english_phrase: The English phrase to modify
        pronoun_type: Type of pronoun detected ('informal', 'formal', 'mixed')
        
    Returns:
        Modified English phrase with appropriate formality markers
    """
    if pronoun_type == "informal":
        if not english_phrase.endswith("(informal you)"):
            return english_phrase + " (informal you)"
    elif pronoun_type == "formal":
        if not english_phrase.endswith("(formal you)"):
            return english_phrase + " (formal you)"
    elif pronoun_type == "mixed":
        if not "(informal you)" in english_phrase and not "(formal you)" in english_phrase:
            return english_phrase + " (informal you, formal you)"
    
    return english_phrase