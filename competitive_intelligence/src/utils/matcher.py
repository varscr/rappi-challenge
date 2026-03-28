from rapidfuzz import fuzz, process
from typing import List, Tuple, Optional

def match_store_names(target_name: str, candidate_names: List[str], threshold: int = 80) -> Optional[Tuple[str, float]]:
    """
    Finds the best match for a store name among a list of candidates using fuzzy matching.
    Returns (matched_name, score) or None if no match above threshold.
    """
    if not candidate_names:
        return None
    
    # We use token_set_ratio because platforms often add suffixes or prefixes 
    # (e.g., "McDonald's - Polanco" vs "McDonald's")
    result = process.extractOne(target_name, candidate_names, scorer=fuzz.token_set_ratio)
    
    if result and result[1] >= threshold:
        return result[0], result[1]
    
    return None

def normalize_name(name: str) -> str:
    """Basic normalization for better matching."""
    return name.lower().strip().replace("-", " ").replace("(", "").replace(")", "")
