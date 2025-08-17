from typing import List, Dict, Any
from statistics import mean
from card_db import CARD_DB  # geen alias meer

def normalize_deck(names: List[str]) -> List[Dict[str, Any]]:
    deck = []
    for n in names:
        if n in CARD_DB:
            deck.append({"name": n, **CARD_DB[n]})
    return deck[:8]

def average_elixir(deck: List[Dict[str, Any]]) -> float:
    return round(mean(c["elixir"] for c in deck), 2) if deck else 0.0

def count_role(deck, role): 
    return sum(1 for c in deck if role in c["roles"])

def has_tag(deck, tag): 
    return any(tag in c["tags"] for c in deck)

def count_tag(deck, tag): 
    return sum(1 for c in deck if tag in c["tags"])

def role_balance_score(deck: List[Dict[str, Any]]) -> float:
    offense = count_role(deck, "offense")
    defense = count_role(deck, "defense") + count_tag(deck, "building")
    score = 1.0 - abs(offense - defense) / 8.0
    return max(0.0, min(1.0, score))

def coverage_score(deck: List[Dict[str, Any]]) -> float:
    coverage_bits = [
        has_tag(deck, "anti_air"),
        has_tag(deck, "splash"),
        has_tag(deck, "building"),
        has_tag(deck, "tank_killer"),
    ]
    return sum(coverage_bits) / 4.0

def spell_coverage_score(deck: List[Dict[str, Any]]) -> float:
    have_small  = has_tag(deck, "small_spell")
    have_medium = has_tag(deck, "medium_spell")
    have_big    = has_tag(deck, "big_spell")
    return (have_small + have_medium + have_big) / 3.0

def win_condition_score(deck: List[Dict[str, Any]]) -> float:
    wc = count_tag(deck, "wincon")
    return min(1.0, wc / 2.0)

def synergy_score(deck: List[Dict[str, Any]], avg_elixir: float) -> float:
    s = 0.0
    if has_tag(deck, "wincon") and has_tag(deck, "building"): s += 0.2
    if has_tag(deck, "wincon") and has_tag(deck, "small_spell"): s += 0.2
    if has_tag(deck, "splash") and has_tag(deck, "swarm"): s += 0.1
    if has_tag(deck, "tank_killer") and has_tag(deck, "splash"): s += 0.1
    if avg_elixir <= 3.1: s += 0.2
    elif avg_elixir <= 4.0: s += 0.1
    return max(0.0, min(1.0, s))

def overall_score(metrics: Dict[str, float], avg_elixir: float) -> float:
    base = (
        0.25 * metrics["balance"] +
        0.20 * metrics["coverage"] +
        0.15 * metrics["spells"] +
        0.20 * metrics["wincon"] +
        0.20 * metrics["synergy"]
    )
    penalty = 0.0
    if avg_elixir > 4.5: penalty = min(0.2, (avg_elixir - 4.5) * 0.1)
    return max(0.0, min(1.0, base - penalty))

def evaluate_deck(names: List[str]) -> Dict[str, Any]:
    deck = normalize_deck(names)
    avg = average_elixir(deck)
    m = {
        "balance": role_balance_score(deck),
        "coverage": coverage_score(deck),
        "spells":   spell_coverage_score(deck),
        "wincon":   win_condition_score(deck),
        "synergy":  synergy_score(deck, avg),
    }
    m["overall"] = overall_score(m, avg)
    return {"deck": deck, "avg_elixir": avg, "metrics": m}
