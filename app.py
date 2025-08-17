from datetime import datetime
from pathlib import Path
import streamlit as st
from heuristics import evaluate_deck, suggest_improvements
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

    # ---------- AI-advies ----------
    with st.expander("AI-advies", expanded=True):
        use_llm = st.toggle("AI-advies (LLM) inschakelen",
                            value=True, key="llm_on")

        advice_lines = []
        if use_llm:
            try:
                from transformers import pipeline

                @st.cache_resource
                def get_llm():
                    # Tekst-naar-tekst; goed voor korte instructieve tips
                    return pipeline("text2text-generation", model="google/flan-t5-small")

                gen = get_llm()
                EXAMPLE = (
                    "- Voeg anti-air toe (Musketeer/Firecracker).\n"
                    "- Verlaag elixir met cycle-kaarten.\n"
                    "- Koppel wincon aan small spell.\n"
                    "- Neem defensieve building op."
                )
                prompt = f"""Maak 4 korte, concrete bullets met advies voor een Clash Royale deck.
Deck: {', '.join([c['name'] for c in deck])}
Metrics (0-1): overall={m['overall']:.2f}, balance={m['balance']:.2f}, coverage={m['coverage']:.2f}, spells={m['spells']:.2f}, wincon={m['wincon']:.2f}, synergy={m['synergy']:.2f}.
Schrijf in het Nederlands.
Uitvoerregels:
- Alleen bullets die starten met "- ".
- Max 10 woorden per bullet.

Voorbeeld:
{EXAMPLE}

Antwoord:
"""
                out = gen(
                    prompt,
                    max_new_tokens=96,
                    num_beams=4,
                    do_sample=False,
                    no_repeat_ngram_size=3
                )[0]["generated_text"]

                lines = [l.strip() for l in out.splitlines()
                         if l.strip().startswith("- ")]
                advice_lines = lines[:4]
                if len(advice_lines) < 3:
                    advice_lines = [
                        f"- {t}" for t in suggest_improvements(deck, m, avg)]
            except Exception:
                st.info("LLM niet beschikbaar — toon rule-based tips.")
                advice_lines = [
                    f"- {t}" for t in suggest_improvements(deck, m, avg)]
        else:
            advice_lines = [
                f"- {t}" for t in suggest_improvements(deck, m, avg)]

        st.write("\n".join(advice_lines) or "- Geen extra tips nodig.")
        st.caption(f"Adviesbron: **{'LLM (google/flan-t5-small)' if use_llm else 'Heuristiek'}**")

        # Bewaar advies
        if st.button("Bewaar AI-advies (.md)", key="save_advice"):
            Path("docs").mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            with open(f"docs/ai_advice_{ts}.md", "w", encoding="utf-8") as f:
                f.write("# AI-advies\n")
                f.write(f"Deck: {', '.join([c['name'] for c in deck])}\n\n")
                f.write("## Tips\n")
                for t in advice_lines:
                    f.write(f"{t}\n")
            st.success("Opgeslagen in docs/")
else:
    st.info("Selecteer en analyseer eerst 8 **unieke** kaarten.")
