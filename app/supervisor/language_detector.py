import re

class LanguageDetector:
    """Classifies user queries into language scripts: English ('en'), Tamil ('ta'), or Mixed ('mixed')."""

    TAMIL_CHAR_RE = re.compile(r"[\u0b80-\u0bff]")
    LATIN_CHAR_RE = re.compile(r"[a-zA-Z]")

    @classmethod
    def detect(cls, text: str) -> str:
        if not text:
            return "en"
        
        tamil_chars = cls.TAMIL_CHAR_RE.findall(text)
        latin_chars = cls.LATIN_CHAR_RE.findall(text)
        
        total_tamil = len(tamil_chars)
        total_latin = len(latin_chars)
        
        if total_tamil > 0 and total_latin > 0:
            return "mixed"
        
        if total_tamil > 0:
            return "ta"
            
        # If Latin only, check for common Tanglish words (phonetic Tamil written in Latin script)
        tanglish_words = {
            "kovai", "nellai", "trichy", "epadi", "irukeenga", "vanakkam", "neer", "nilathadi",
            "mazhai", "semicritical", "ennangina", "enna", "irukku", "namathu", "district",
            "thanjavur", "ponnamaravathy", "puducherry", "oruthan"
        }
        
        words = [w.lower().strip(",.?/!@#") for w in text.split()]
        matches = sum(1 for w in words if w in tanglish_words)
        
        # Heuristic: if more than 1 matching Tanglish word or starts with greeting
        if matches >= 1:
            return "mixed"
            
        return "en"
