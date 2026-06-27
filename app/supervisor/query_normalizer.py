import re

class QueryNormalizer:
    """Standardizes years, units, temporal ranges, parameters and localized terminology inside queries."""

    # Map raw numeric year representation to GEC assessment bounds
    YEAR_MAPPINGS = {
        "2020": "2020-2021",
        "2021": "2020-2021",
        "2022": "2022-2023",
        "2023": "2022-2023",
        "2024": "2023-2024",
        "2025": "2024-2025"
    }

    # Standardize parameters / units
    UNIT_MAPPINGS = {
        "hectare meter": "ham",
        "hectare meters": "ham",
        "cubic meters": "m3",
        "millimeters": "mm",
        "millimetre": "mm",
        "millimetres": "mm"
    }

    @classmethod
    def normalize(cls, query: str) -> str:
        """Applies normalizations to clean and format query string uniformly."""
        if not query:
            return ""

        # Normalize spaces
        query = " ".join(query.split())

        # Normalize units
        for raw_unit, clean_unit in cls.UNIT_MAPPINGS.items():
            query = re.sub(rf"\b{raw_unit}\b", clean_unit, query, flags=re.IGNORECASE)

        # Normalize years: e.g. "2024-25" -> "2024-2025"
        # Match pattern YYYY-YY
        query = re.sub(
            r"\b(20\d{2})-(\d{2})\b",
            lambda m: f"{m.group(1)}-20{m.group(2)}",
            query
        )

        # Match single YYYY years and expand them to corresponding GEC cycle ranges
        # e.g., "2024" -> "2023-2024"
        def year_replacer(match):
            y = match.group(0)
            if y in cls.YEAR_MAPPINGS:
                return cls.YEAR_MAPPINGS[y]
            return y

        # Only replace standalone YYYY years that are not already part of a range
        query = re.sub(
            r"(?<!-)\b(202\d)\b(?!-)",
            year_replacer,
            query
        )

        return query
