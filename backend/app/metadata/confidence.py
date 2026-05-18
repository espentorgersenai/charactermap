import math
import re

from rapidfuzz import fuzz


def extract_year_from_query(query: str) -> int | None:
    """Extract a 4-digit year (1800-2030) from the query string."""
    match = re.search(r"\b(1[89]\d{2}|20[012]\d|2030)\b", query)
    if match:
        return int(match.group(1))
    return None


def compute_confidence(
    query: str,
    candidate_title: str,
    is_single_result: bool,
    popularity_count: int,
    candidate_year: int | None,
    query_year: int | None,
) -> float:
    """Compute confidence score per SPEC §9.4.

    score = 0.5 * title_similarity
          + 0.2 * (single_result ? 1 : 0)
          + 0.15 * popularity_signal   # log-normalised to 0-1
          + 0.15 * year_proximity      # 1.0 if years match exactly, else 0.0
    """
    title_sim = fuzz.ratio(query.lower(), candidate_title.lower()) / 100.0
    single = 1.0 if is_single_result else 0.0
    pop = min(1.0, math.log1p(popularity_count) / math.log1p(1000))
    year_prox = 0.0
    if query_year and candidate_year and query_year == candidate_year:
        year_prox = 1.0
    score = 0.5 * title_sim + 0.2 * single + 0.15 * pop + 0.15 * year_prox
    return round(min(1.0, score), 4)
