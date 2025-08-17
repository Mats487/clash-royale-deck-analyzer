import streamlit as st
from heuristics import evaluate_deck
from card_db import CARD_DB

st.set_page_config(page_title="Clash Royale Deck Analyzer", page_icon="🛡️", layout="centered")
st.title("Clash Royale Deck Analyzer")

st.subheader("1) Kies je 8 kaarten")
all_cards = sorted(CARD_DB.keys())

default_deck = ["Hog Rider","Fireball","Zap","The Log","Musketeer","Cannon","Skeletons","Ice Spirit"]
selected = st.multiselect("Deck (exact 8 kaarten)", all_cards, default=default_deck, max_selections=8)
if len(selected) != 8:
    st.warning(f"Je hebt {len(selected)} kaarten geselecteerd — selecteer er precies 8.")
    st.stop()

st.subheader("2) Analyseer")
if st.button("Analyze deck"):
    result = evaluate_deck(selected)
    deck = result["deck"]
    avg  = result["avg_elixir"]
    m    = result["metrics"]

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

    st.markdown("---")
    st.subheader("3) (Optioneel) AI-advies")
    enable_llm = st.toggle("LLM-advies inschakelen (download model bij eerste keer)")
    if enable_llm:
        try:
            from transformers import pipeline
            @st.cache_resource
            def get_generator():
                # Klein, lokaal model; kan je later vervangen door bv. flan-t5-base
                return pipeline("text-generation", model="distilgpt2")
            gen = get_generator()

            prompt = (
                "You are a Clash Royale coach. Give concise, actionable tips.\n"
                f"Deck: {', '.join([c['name'] for c in deck])}\n"
                f"Metrics (0-1): overall={m['overall']:.2f}, balance={m['balance']:.2f}, "
                f"coverage={m['coverage']:.2f}, spells={m['spells']:.2f}, wincon={m['wincon']:.2f}, synergy={m['synergy']:.2f}.\n"
                "Return 4 bullet points with improvements (card swaps or playstyle)."
            )
            out = gen(prompt, max_new_tokens=120, do_sample=True, temperature=0.8)[0]["generated_text"]
            st.write(out.split("Return")[0].strip())  # simpele trim
        except Exception:
            st.info("LLM niet beschikbaar. Fallback naar rule-based advies.")
            tips = []
            if m["wincon"] < 0.5: tips.append("Voeg minstens 1 duidelijke win condition toe (bv. Hog Rider, Giant of Balloon).")
            if m["coverage"] < 0.75: tips.append("Zorg voor anti-air, splash, building en tank-killer in het deck.")
            if avg > 4.5: tips.append("Gemiddelde elixir is hoog: vervang 1–2 dure kaarten door cycle/goedkope support.")
            if m["spells"] < 0.67: tips.append("Gebruik een mix van small + medium/big spell voor betere spell-coverage.")
            if m["synergy"] < 0.5: tips.append("Koppel je wincon aan support (bv. building voor verdediging + small spell).")
            st.write("\n".join([f"- {t}" for t in tips]) or "- Deck ziet er coherent uit; focus op micro-play.")


# Benchmarks
import pandas as pd

st.divider()
st.subheader("Benchmarks")

SAMPLE_DECKS = {
    "Hog 2.6": [
        "Hog Rider","Musketeer","Cannon","Fireball","The Log","Ice Spirit","Skeletons","Zap"
    ],
    "Giant Beatdown": [
        "Giant","Baby Dragon","Mega Minion","Lightning","Zap","Minions","Valkyrie","Inferno Tower"
    ],
    "LavaLoon": [
        "Lava Hound","Balloon","Baby Dragon","Mega Minion","Tombstone","Arrows","Fireball","Skeletons"
    ],
    "X-Bow Cycle": [
        "X-Bow","Tesla","Archers","Fireball","The Log","Ice Spirit","Skeletons","Knight"
    ],
}

if st.button("Run benchmarks"):
    rows = []
    for name, deck in SAMPLE_DECKS.items():
        res = evaluate_deck(deck); m = res["metrics"]
        rows.append({
            "Deck": name,
            "AvgElixir": res["avg_elixir"],
            "Overall": round(m["overall"],3),
            "Balance": round(m["balance"],3),
            "Coverage": round(m["coverage"],3),
            "Spells": round(m["spells"],3),
            "Wincon": round(m["wincon"],3),
            "Synergy": round(m["synergy"],3),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
    st.info("Maak een screenshot en voeg die toe aan README en rapport.")
