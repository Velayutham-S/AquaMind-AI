import re
from typing import Dict
from app.resolution import LOCATION_ALIASES

class SpellCorrector:
    """Corrects common spelling errors, typos, and transliterated location name aliases in user queries."""

    # Map of obvious typos/phonetic spellings to standard English spelling equivalents
    COMMON_TYPOS: Dict[str, str] = {
        "sallim": "Salem",
        "salem": "Salem",
        "kovai": "Coimbatore",
        "coimbator": "Coimbatore",
        "coimbatore": "Coimbatore",
        "trichy": "Tiruchirappalli",
        "trichi": "Tiruchirappalli",
        "nellai": "Tirunelveli",
        "tirunelveli": "Tirunelveli",
        "madras": "Chennai",
        "chenai": "Chennai",
        "chennai": "Chennai",
        "tuticorin": "Thoothukudi",
        "thoothukudi": "Thoothukudi",
        "dindigul": "Dindigul",
        "dindigulh": "Dindigul",
        "dharmapuri": "Dharmapuri",
        "erode": "Erode",
        "karur": "Karur",
        "namakkal": "Namakkal",
        "thanjavur": "Thanjavur",
        "tanjore": "Thanjavur",
        "vellur": "Vellore",
        "vellore": "Vellore",
        "tirupur": "Tiruppur",
        "tiruppur": "Tiruppur",
        "pondicherry": "Puducherry",
        "puducherry": "Puducherry",
        "kanniyakumari": "Kanniyakumari",
        "kanyakumari": "Kanniyakumari",
        "virudhunagar": "Virudhunagar"
    }

    @classmethod
    def correct(cls, query: str) -> str:
        """Processes query string, identifying and correcting location-specific typos and aliases."""
        if not query:
            return ""

        words = query.split()
        corrected_words = []
        
        for word in words:
            # Clean symbols for dictionary lookup
            cleaned_word = re.sub(r"[^\w]", "", word).lower()
            
            # 1. Lookup in custom typos / standard mapping
            if cleaned_word in cls.COMMON_TYPOS:
                corrected_word = cls.COMMON_TYPOS[cleaned_word]
                # Preserve capitalization / spacing if word had symbols
                # e.g., "kovai," -> "Coimbatore,"
                prefix = re.match(r"^[^\w]*", word).group(0)
                suffix = re.search(r"[^\w]*$", word).group(0)
                corrected_words.append(f"{prefix}{corrected_word}{suffix}")
            else:
                # 2. Check location resolver aliases (like karumathampatti -> KARUMATHAMPATTY)
                if cleaned_word in LOCATION_ALIASES:
                    corrected_word = LOCATION_ALIASES[cleaned_word].title()
                    prefix = re.match(r"^[^\w]*", word).group(0)
                    suffix = re.search(r"[^\w]*$", word).group(0)
                    corrected_words.append(f"{prefix}{corrected_word}{suffix}")
                else:
                    corrected_words.append(word)

        return " ".join(corrected_words)
