from datetime import datetime
from pathlib import Path
import streamlit as st
from heuristics import average_elixir, evaluate_deck, suggest_improvements
from card_db import CARD_DB

# ---------- Session state ----------
if "analysis" not in st.session_state:
    st.session_state["analysis"] = None
if "deck_names" not in st.session_state:
    st.session_state["deck_names"] = []

# ---------- UI ----------
st.set_page_config(page_title="Clash Royale Deck Analyzer",
                   page_icon="🛡️", layout="centered")
st.title("Clash Royale Deck Analyzer")

st.subheader("1) Kies je 8 kaarten")
all_cards = sorted(CARD_DB.keys())
default_deck = ["Hog Rider", "Fireball", "Zap", "The Log",
                "Musketeer", "Cannon", "Skeletons", "Ice Spirit"]

selected = st.multiselect("Deck (exact 8 **unieke** kaarten)",
                          all_cards, default=default_deck, max_selections=8)
dup = len(selected) != len(set(selected))
if dup:
    st.error("Dubbele kaarten gedetecteerd.")
if len(selected) != 8:
    st.warning(
        f"Je hebt {len(selected)} kaarten geselecteerd — selecteer er precies 8.")

st.subheader("2) Analyseer")
if st.button("Analyze deck", disabled=dup or len(selected) != 8, key="analyze_btn"):
    st.session_state["analysis"] = evaluate_deck(selected)
    st.session_state["deck_names"] = selected

# ---------- Resultaat tonen op basis van state ----------
res = st.session_state["analysis"]
if res:
    deck = res["deck"]
    avg = res["avg_elixir"]
    m = res["metrics"]

    st.write("**Gemiddelde elixir:**", avg)
    col1, col2, col3 = st.columns(3)
    col1.metric("Overall", f"{round(m['overall']*100):d} / 100")
    col2.metric("Balance", f"{round(m['balance']*100):d} / 100")
    col3.metric("Coverage", f"{round(m['coverage']*100):d} / 100")

    col4, col5, col6 = st.columns(3)
    col4.metric("Spells",  f"{round(m['spells']*100):d} / 100")
    col5.metric("Win condition", f"{round(m['wincon']*100):d} / 100")
    col6.metric("Synergy", f"{round(m['synergy']*100):d} / 100")

    with st.expander("Deck details"):
        st.write([c["name"] for c in deck])

    # ---------- Advies ----------
    with st.expander("Advies", expanded=True):
        use_llm = st.toggle("AI-advies (LLM) inschakelen",
                            value=False, key="llm_on")

        import re
        import random

        def names_list(deck):
            return [c["name"] for c in deck]

        def avg_elixir_of(names):
            return round(sum(CARD_DB[n]["elixir"] for n in names) / len(names), 2) if names else 0.0

        def has_tag_names(names, tag):
            return any(tag in CARD_DB[n]["tags"] for n in names)

        def count_role_names(names, role):
            return sum(1 for n in names if role in CARD_DB[n]["roles"])

        def missing_core(names):
            return {
                "building": not has_tag_names(names, "building"),
                "tank_killer": not has_tag_names(names, "tank_killer"),
                "wincon": not has_tag_names(names, "wincon"),
                "support": count_role_names(names, "support") < 2,
                "small_spell": not has_tag_names(names, "small_spell"),
                "big_spell": not (has_tag_names(names, "medium_spell") or has_tag_names(names, "big_spell")),
                "anti_air": not has_tag_names(names, "anti_air"),
            }

        def best_wincon(names, avg_val):
            pool_fast = ["Hog Rider", "Miner", "Goblin Barrel", "Mortar"]
            pool_heavy = ["Royal Giant", "Balloon",
                          "Graveyard", "Goblin Drill", "Battle Ram"]
            pool = pool_fast if avg_val <= 3.3 else pool_heavy
            for w in pool:
                if w not in names:
                    return w
            return None

        def best_support(names):
            options = ["Musketeer", "Firecracker",
                       "Valkyrie", "Electro Wizard", "Baby Dragon"]
            return next((x for x in options if x not in names), None)

        def best_small_spell(names):
            options = ["Zap", "The Log", "Giant Snowball",
                       "Arrows", "Barbarian Barrel", "Royal Delivery"]
            return next((x for x in options if x not in names), None)

        def best_big_spell(names):
            options = ["Fireball", "Poison", "Rocket",
                       "Lightning", "Earthquake"]
            return next((x for x in options if x not in names), None)

        def best_anti_air(names):
            options = ["Musketeer", "Firecracker", "Dart Goblin", "Electro Wizard", "Mega Minion", "Flying Machine"]
            return next((x for x in options if x not in names), None)

        # ---------- candidates builder ----------
        UNT_TOUCHABLES = {"Fireball","Poison","Rocket","Lightning","Inferno Tower","Zap","The Log"}

        def pick_out_card(deck_names, prefer_heavy=False, forbid=set()):
            """Kies een kaart om te vervangen, zonder wincons/untouchables/recent-added.
               'forbid' = set van kaarten die we NIET als out mogen kiezen (bv. al gebruikt)."""
            forbid = set(forbid) if forbid else set()
            candidates = [
                n for n in deck_names
                if "wincon" not in CARD_DB[n]["tags"]
                and n not in forbid
                and n not in UNT_TOUCHABLES
            ]
            if not candidates:
                candidates = [n for n in deck_names if n not in forbid] or deck_names[:]
            filtered = [c for c in candidates if c not in ["Skeletons","Ice Spirit","Fire Spirit","Electro Spirit"]]
            if filtered:
                candidates = filtered
            if prefer_heavy:
                candidates.sort(key=lambda n: (-CARD_DB[n]["elixir"], "building" in CARD_DB[n]["tags"]))
            else:
                candidates.sort(key=lambda n: (CARD_DB[n]["elixir"], "cycle" in CARD_DB[n]["tags"]))
            for cand in candidates:
                if cand not in forbid:
                    return cand
            return candidates[0]

        def build_rule_based_candidates(deck_names, prev_names, overall_score=None, avg_now=None):
            """
            Bepaalt welke kaarten vervangen moeten worden op basis van missende rollen.
            GEEN polish meer: als alle kernvereisten oké zijn -> geen vervang-adviezen.
            Zorgt er ook voor dat we NIET twee keer dezelfde 'out' gebruiken.
            """
            proposals = []
            used_out = set()
            used_in = set()

            gaps = missing_core(deck_names)
            if avg_now is None:
                avg_now = avg_elixir_of(deck_names)

            def would_lose_last_building(out_name, in_name):
                if "building" not in CARD_DB[out_name]["tags"]:
                    return False
                if "building" in CARD_DB[in_name]["tags"]:
                    return False
                bcount = sum(1 for n in deck_names if "building" in CARD_DB[n]["tags"])
                return bcount == 1

            def safe_append(out_name, in_name, reason):
                if not out_name or not in_name or out_name == in_name:
                    return False
                if out_name not in deck_names:
                    return False
                if out_name in UNT_TOUCHABLES:
                    return False
                if would_lose_last_building(out_name, in_name):
                    return False
                if out_name in used_out:
                    return False
                if in_name in used_in:
                    return False
                proposals.append((out_name, in_name, reason))
                used_out.add(out_name)
                used_in.add(in_name)
                return True

            if gaps["tank_killer"]:
                out_n = pick_out_card(deck_names, prefer_heavy=True, forbid=used_out)
                safe_append(out_n, "Inferno Tower", "counter tanks (tank killer + building)")

            if gaps["wincon"]:
                wc = best_wincon(deck_names, avg_now)
                if wc and wc not in deck_names and wc not in used_in:
                    out_n = pick_out_card(deck_names, prefer_heavy=(avg_now > 4.0), forbid=used_out)
                    safe_append(out_n, wc, "duidelijke win condition")

            if gaps["support"]:
                sup = best_support(deck_names)
                if sup and sup not in deck_names and sup not in used_in:
                    out_n = pick_out_card(deck_names, prefer_heavy=False, forbid=used_out)
                    safe_append(out_n, sup, "ondersteuning/anti-air/splash")

            if gaps["building"]:
                for b in ["Bomb Tower","Tesla","Cannon"]:
                    if b not in deck_names and b not in used_in:
                        out_n = pick_out_card(deck_names, prefer_heavy=True, forbid=used_out)
                        if safe_append(out_n, b, "defensieve building"):
                            break

            if gaps["small_spell"]:
                ss = best_small_spell(deck_names)
                if ss and ss not in deck_names and ss not in used_in:
                    out_n = pick_out_card(deck_names, prefer_heavy=False, forbid=used_out)
                    safe_append(out_n, ss, "altijd 1 kleine spell nodig")
            if gaps["big_spell"]:
                bs = best_big_spell(deck_names)
                if bs and bs not in deck_names and bs not in used_in:
                    out_n = pick_out_card(deck_names, prefer_heavy=True, forbid=used_out)
                    safe_append(out_n, bs, "minstens 1 medium/big spell nodig")

            if gaps.get("anti_air", False):
                aa = best_anti_air(deck_names)
                if aa and aa not in deck_names and aa not in used_in:
                    out_n = pick_out_card(deck_names, prefer_heavy=False, forbid=used_out)
                    safe_append(out_n, aa, "anti-air ontbreekt")

            return proposals

        # ---------- render ----------
        current_names = names_list(deck)
        prev_names = st.session_state.get("deck_names", [])
        candidates = build_rule_based_candidates(current_names, prev_names, overall_score=m["overall"], avg_now=avg)

        final_lines = []

        if use_llm:
            try:
                from transformers import pipeline

                @st.cache_resource
                def get_llm():
                    return pipeline("text2text-generation", model="google/flan-t5-base")

                gen = get_llm()

                MAX_TIPS = 4

                if not candidates:
                    adv_lines = ["- Dit deck is optimaal! 🎯"]
                else:
                    option_lines = [
                        f"{chr(65+i)}) VERVANG: {o} -> {i_} — reden: {r}" for i, (o, i_, r) in enumerate(candidates)
                    ]
                    prompt = f"""Je bent een Clash Royale coach.
Kies ALLE opties die het deck verbeteren (meerdere regels mogelijk).
Geef UITSLUITEND regels in dit formaat:
VERVANG: <KaartUit> -> <KaartIn> — reden: <korte reden>
Deck: {', '.join(current_names)}

Opties:
{chr(10).join(option_lines)}

Antwoord:"""

                    out = gen(prompt, max_new_tokens=200,
                              num_beams=4, do_sample=False, no_repeat_ngram_size=3)[0]["generated_text"]

                    parsed = re.findall(
                        r"VERVANG:\s*([A-Za-z .’'&\-]+)\s*->\s*([A-Za-z .’'&\-]+)\s*(?:—|-)\s*reden:\s*([^\n\r]+)", out)

                    adv_lines = []
                    if parsed:
                        for (a, b, r) in parsed:
                            adv_lines.append(f"- VERVANG: {a.strip()} -> {b.strip()} — reden: {r.strip()}")

                    if len(adv_lines) < min(MAX_TIPS, len(candidates)):
                        for (o, i_, r) in candidates:
                            line = f"- VERVANG: {o} -> {i_} — reden: {r}"
                            if all(f" {o} -> {i_} " not in s for s in adv_lines):
                                adv_lines.append(line)
                            if len(adv_lines) >= MAX_TIPS:
                                break

                st.write("\n".join(adv_lines))
                st.caption("Adviesbron: **LLM**")
                final_lines = adv_lines

            except Exception as e:
                st.error(f"LLM kon niet genereren: {type(e).__name__}: {e}")
                st.caption("Zet de toggle uit voor heuristiek.")
                final_lines = ["- (LLM-fout)"]

        else:
            tips = suggest_improvements(deck, m, avg)
            st.write("\n".join(f"- {t}" for t in tips))
            st.caption("Adviesbron: **Heuristiek**")
            final_lines = [f"- {t}" for t in tips]

        if st.button("Bewaar advies (.md)", key="save_advice"):
            Path("docs").mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            with open(f"docs/ai_advice_{ts}.md", "w", encoding="utf-8") as f:
                f.write("# Advies\n")
                f.write(f"Deck: {', '.join([c['name'] for c in deck])}\n\n")
                f.write("## Tips\n")
                for line in final_lines:
                    f.write(line + "\n")
            st.success("Opgeslagen in docs/")

else:
    st.info("Selecteer en analyseer eerst 8 **unieke** kaarten.")
