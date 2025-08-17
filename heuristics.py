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
    have_small = has_tag(deck, "small_spell")
    have_medium = has_tag(deck, "medium_spell")
    have_big = has_tag(deck, "big_spell")
    return (have_small + have_medium + have_big) / 3.0


def win_condition_score(deck: List[Dict[str, Any]]) -> float:
    wc = count_tag(deck, "wincon")
    return min(1.0, wc / 2.0)


def synergy_score(deck: List[Dict[str, Any]], avg_elixir: float) -> float:
    s = 0.0
    if has_tag(deck, "wincon") and has_tag(deck, "building"):
        s += 0.2
    if has_tag(deck, "wincon") and has_tag(deck, "small_spell"):
        s += 0.2
    if has_tag(deck, "splash") and has_tag(deck, "swarm"):
        s += 0.1
    if has_tag(deck, "tank_killer") and has_tag(deck, "splash"):
        s += 0.1
    if avg_elixir <= 3.1:
        s += 0.2
    elif avg_elixir <= 4.0:
        s += 0.1
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
    if avg_elixir > 4.5:
        penalty = min(0.2, (avg_elixir - 4.5) * 0.1)
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


def suggest_improvements(deck, metrics, avg_elixir):
    # Verzamel tags en simpele archetype-detectie
    tags = {t for c in deck for t in c["tags"]}
    names = [c["name"] for c in deck]
    is_hog_cycle = ("Hog Rider" in names) and (avg_elixir <= 3.1)

    tips = []

    # Coverage-gaten (alleen toevoegen als ze echt missen)
    if "anti_air" not in tags:
        tips.append(
            "Ontbreekt anti-air: overweeg Musketeer, Mega Minion of Firecracker.")
    if "splash" not in tags:
        tips.append("Voeg splash-damage toe (Baby Dragon, Valkyrie of Wizard).")
    if "building" not in tags:
        tips.append(
            "Zet een defensieve building (Cannon/Tesla/Inferno Tower) in.")
    if "tank_killer" not in tags:
        tips.append(
            "Neem een tank killer (Inferno Tower/Dragon of Mini P.E.K.K.A).")

    # Spells: discrete check i.p.v. 0.67 afrondingsgedoe
    have_small = "small_spell" in tags
    have_medium = "medium_spell" in tags
    have_big = "big_spell" in tags
    spell_cats = int(have_small) + int(have_medium) + int(have_big)
    if spell_cats < 2:
        tips.append(
            "Gebruik mix van spells: minstens twee categorieën (small/medium/big).")

    # Wincon/tempo
    if metrics.get("wincon", 0) < 0.5:
        tips.append(
            "Voeg een duidelijke win condition toe (Hog, Giant, Balloon, …).")
    if avg_elixir > 4.5:
        tips.append(
            "Gemiddelde elixir is hoog: vervang 1–2 dure kaarten door cycle.")

    # Archetype-specifiek (Hog cycle)
    if is_hog_cycle:
        tips.extend([
            "Cycle Hog met Skeletons + Ice Spirit; forceer druk.",
            "Gebruik The Log/Zap tegen swarms; chip consequent.",
            "Cannon centraal voor pulls; counterpush met Hog.",
            "Fireball voor waarde: raak troep + toren waar kan."
        ])

    # Altijd min. 4 bullets: vul generieke, niet-te-specifieke tips aan
    generic = [
        "Speel rond je wincon; bewaar elixir voor defense.",
        "Zoek spells-waarde: raak meerdere doelen tegelijk.",
        "Plaats building 4–2 centraal voor betere pulls.",
        "Roteer goedkoop om tempo en druk te houden.",
    ]
    for g in generic:
        if len(tips) >= 4:
            break
        if g not in tips:
            tips.append(g)

    return tips[:4]
