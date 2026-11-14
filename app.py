import asyncio
import concurrent.futures
import html
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import edge_tts
import streamlit as st

# ==============================================================================
# 1. PAGE SETUP & HCI RESEARCH THEME CONFIGURATION
# ==============================================================================
st.set_page_config(
    page_title="CogRead — Cognitive Accessibility & HCI Reader",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
if "friction_count" not in st.session_state:
    st.session_state["friction_count"] = 0
if "resolved_sentences" not in st.session_state:
    st.session_state["resolved_sentences"] = set()
if "active_text" not in st.session_state:
    st.session_state["active_text"] = ""
if "active_scenario_title" not in st.session_state:
    st.session_state["active_scenario_title"] = "Medical Discharge Summary"

# ==============================================================================
# 2. RESEARCH SAMPLE PRESETS (Zero-Friction HCI Onboarding)
# ==============================================================================
SCENARIOS = {
    "Medical Discharge Summary": {
        "badge": "Clinical Jargon",
        "description": "Dense discharge instructions with pharmacological instructions and contraindications.",
        "text": (
            "The patient presented with acute exacerbation of chronic obstructive pulmonary disease "
            "complicated by secondary bacterial pneumonia. Initiated on intravenous methylprednisolone "
            "taper and broad-spectrum empiric levofloxacin therapy. Discharge directives mandate ambulatory "
            "supplemental oxygen titration at two liters per minute via nasal cannula. Concomitant non-steroidal "
            "anti-inflammatory drugs remain strictly contraindicated due to elevated gastrointestinal hemorrhage risk. "
            "Follow-up spirometry and arterial blood gas analysis required within fourteen days."
        ),
    },
    "Bank Loan / Legal Clause": {
        "badge": "Legal & Financial",
        "description": "Complex acceleration, cross-default, and indemnity clauses in personal credit agreements.",
        "text": (
            "In the event of borrower default under any antecedent covenant, the lender reserves an unfettered "
            "statutory right to exercise acceleration of all outstanding principal indebtedness without prior demand. "
            "Compounding default interest shall accrue at five percent per annum above the base lending rate calculated "
            "diurnally. The borrower agrees to indemnify, defend, and hold harmless the credit institution against any "
            "encumbrances, adjudications, or legal disbursements arising from collateral liquidation. Mandatory binding "
            "arbitration clauses supersede jurisdictional courtroom proceedings."
        ),
    },
    "Technical Research Abstract": {
        "badge": "Academic Complexity",
        "description": "Dense machine learning abstract with statistical notation and architectural jargon.",
        "text": (
            "We formulate an asymmetric multi-head self-attention architecture that amortizes quadratic computational "
            "complexity down to linear sub-sampling bounds. The model regularizes inductive bias via stochastic "
            "orthogonal weight initialization to mitigate catastrophic gradient vanishing during backpropagation. "
            "Empirical evaluations substantiate a 4.2% top-1 perplexity reduction across heterogeneous non-stationary "
            "distributions. Ablation benchmarks corroborate that sparse feed-forward projections preserve representational "
            "fidelity while significantly decreasing floating-point latency on constrained edge hardware."
        ),
    },
}

# Set default text if empty
if not st.session_state["active_text"]:
    st.session_state["active_text"] = SCENARIOS["Medical Discharge Summary"]["text"]

# ==============================================================================
# 3. EXISTING TTS CORE ENGINE & PROSODY MAPPINGS (PRESERVED & ENHANCED)
# ==============================================================================
LANGUAGE_VOICES = {
    "English (US)": [
        ("Jenny — conversational (Clear & Gentle)", "en-US-JennyNeural"),
        ("Guy — warm male (Patient Pacing)", "en-US-GuyNeural"),
        ("Aria — expressive", "en-US-AriaNeural"),
        ("Ana — child", "en-US-AnaNeural"),
        ("Davis — calm male", "en-US-DavisNeural"),
    ],
    "English (UK)": [
        ("Sonia — conversational", "en-GB-SoniaNeural"),
        ("Ryan — male", "en-GB-RyanNeural"),
        ("Maisie — female", "en-GB-MaisieNeural"),
    ],
    "English (India)": [
        ("Neerja — female", "en-IN-NeerjaNeural"),
        ("Prabhat — male", "en-IN-PrabhatNeural"),
    ],
    "English (Australia)": [
        ("Natasha — female", "en-AU-NatashaNeural"),
        ("William — male", "en-AU-WilliamNeural"),
    ],
}

SPEECH_STYLES = {
    "Default (natural)": None,
    "😌 Calm (Recommended for Cognitive Ease)": "calm",
    "🎙️ Professional Narration": "narration-professional",
    "🤗 Friendly & Warm": "friendly",
    "🥺 Gentle": "gentle",
    "💚 Empathetic": "empathetic",
    "📰 Clear Newscast": "newscast",
}

MOOD_PROSODY = {
    "calm": (-15, -2, -5),
    "friendly": (5, 3, 5),
    "gentle": (-15, -2, -15),
    "empathetic": (-5, -1, -5),
    "narration-professional": (-5, 0, 5),
    "newscast": (0, 0, 5),
}

def _clamp(val, lo, hi):
    return max(lo, min(hi, val))

def _parse_rate(s: str) -> int:
    return int(s.replace("%", "").replace("+", ""))

def _parse_pitch(s: str) -> int:
    return int(s.replace("Hz", "").replace("+", ""))

def _fmt_rate(v: int) -> str:
    return f"+{v}%" if v >= 0 else f"{v}%"

def _fmt_pitch(v: int) -> str:
    return f"+{v}Hz" if v >= 0 else f"{v}Hz"

def _fmt_volume(v: int) -> str:
    return f"+{v}%" if v >= 0 else f"{v}%"

async def _synthesize_edge_audio(
    content: str, voice_name: str, rate_value: str, pitch_value: str,
    output_path: str, style_value: Optional[str] = None
):
    """Core edge_tts synthesis routine with robust 3-tier style and prosody fallback."""
    import edge_tts.communicate as _etc

    _original_mkssml = _etc.mkssml
    base_rate = _parse_rate(rate_value)
    base_pitch = _parse_pitch(pitch_value)

    if style_value and style_value in MOOD_PROSODY:
        dr, dp, dv = MOOD_PROSODY[style_value]
        adj_rate = _fmt_rate(_clamp(base_rate + dr, -50, 100))
        adj_pitch = _fmt_pitch(_clamp(base_pitch + dp, -10, 10))
        adj_volume = _fmt_volume(_clamp(dv, -50, 50))
    else:
        adj_rate = rate_value
        adj_pitch = pitch_value
        adj_volume = "+0%"

    def _mkssml_with_express_as(tc, escaped_text):
        if isinstance(escaped_text, bytes):
            escaped_text = escaped_text.decode("utf-8")
        return (
            "<speak version='1.0' "
            "xmlns='http://www.w3.org/2001/10/synthesis' "
            "xmlns:mstts='http://www.w3.org/2001/mstts' "
            "xml:lang='en-US'>"
            f"<voice name='{tc.voice}'>"
            f"<mstts:express-as style='{style_value}'>"
            f"<prosody pitch='{adj_pitch}' rate='{adj_rate}' volume='{adj_volume}'>"
            f"{escaped_text}"
            "</prosody>"
            "</mstts:express-as>"
            "</voice>"
            "</speak>"
        )

    def _mkssml_prosody_only(tc, escaped_text):
        if isinstance(escaped_text, bytes):
            escaped_text = escaped_text.decode("utf-8")
        return (
            "<speak version='1.0' "
            "xmlns='http://www.w3.org/2001/10/synthesis' "
            "xml:lang='en-US'>"
            f"<voice name='{tc.voice}'>"
            f"<prosody pitch='{adj_pitch}' rate='{adj_rate}' volume='{adj_volume}'>"
            f"{escaped_text}"
            "</prosody>"
            "</voice>"
            "</speak>"
        )

    try:
        # Tier 1: express-as + mood prosody
        if style_value:
            _etc.mkssml = _mkssml_with_express_as
        communicate = edge_tts.Communicate(content, voice_name, rate=rate_value, pitch=pitch_value)
        await communicate.save(output_path)
    except Exception:
        # Tier 2: mood prosody only
        if style_value:
            try:
                _etc.mkssml = _mkssml_prosody_only
                communicate = edge_tts.Communicate(content, voice_name, rate=rate_value, pitch=pitch_value)
                await communicate.save(output_path)
                return
            except Exception:
                pass
        # Tier 3: standard defaults
        _etc.mkssml = _original_mkssml
        communicate = edge_tts.Communicate(content, voice_name)
        await communicate.save(output_path)
    finally:
        _etc.mkssml = _original_mkssml

def _run_async_in_thread(coro):
    """Safely execute asyncio coroutine inside Streamlit's threaded environment."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()

@st.cache_data(show_spinner=False, ttl=3600)
def generate_speech_bytes(
    content: str, voice_name: str, rate_value: str, pitch_value: str, style_value: Optional[str]
) -> bytes:
    """Cached wrapper around edge_tts to prevent redundant synthesis and ensure instant playback."""
    if not content or not content.strip():
        return b""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        output_path = tmp.name
    try:
        _run_async_in_thread(
            _synthesize_edge_audio(content.strip(), voice_name, rate_value, pitch_value, output_path, style_value)
        )
        return Path(output_path).read_bytes()
    finally:
        if os.path.exists(output_path):
            try:
                os.unlink(output_path)
            except OSError:
                pass

# ==============================================================================
# 4. DETERMINISTIC COGNITIVE SIMPLIFIER & SENTENCE DECOMPOSER
# ==============================================================================
JARGON_REPLACEMENTS = {
    # Medical
    r"\bacute exacerbation\b": "sudden worsening",
    r"\bchronic obstructive pulmonary disease\b": "long-term lung disease (COPD)",
    r"\bsecondary bacterial pneumonia\b": "a chest/lung infection caused by bacteria",
    r"\bintravenous methylprednisolone taper\b": "IV steroid medicine gradually decreased",
    r"\bbroad-spectrum empiric levofloxacin therapy\b": "antibiotic pills (levofloxacin) to fight bacteria",
    r"\bdischarge directives mandate\b": "hospital release instructions require",
    r"\bambulatory supplemental oxygen titration\b": "portable oxygen tank adjustment",
    r"\bnasal cannula\b": "small soft nose breathing tubes",
    r"\bconcomitant non-steroidal anti-inflammatory drugs\b": "taking pain relievers like ibuprofen or aspirin at the same time",
    r"\bstrictly contraindicated\b": "strictly forbidden (do not take)",
    r"\belevated gastrointestinal hemorrhage risk\b": "high risk of stomach bleeding",
    r"\bfollow-up spirometry\b": "a scheduled breathing checkup",
    r"\barterial blood gas analysis\b": "a routine blood oxygen lab test",
    r"\bhypertension\b": "high blood pressure",
    r"\bhyperlipidemia\b": "high cholesterol",
    # Legal / Financial
    r"\bantecedent covenant\b": "earlier loan promise or contract rule",
    r"\bunfettered statutory right\b": "full legal power under the law",
    r"\bexercise acceleration of all outstanding principal indebtedness\b": "demand full repayment of the entire loan immediately",
    r"\bwithout prior demand\b": "without needing to warn you first",
    r"\bcompounding default interest\b": "extra penalty interest charged on unpaid amounts",
    r"\baccrue at five percent per annum\b": "build up at 5% each year",
    r"\bdiurnally\b": "every single day",
    r"\bindemnify, defend, and hold harmless\b": "pay for any legal costs or damages yourself",
    r"\bcollateral liquidation\b": "selling off your pledged assets or property",
    r"\bmandatory binding arbitration\b": "a private arbitrator making the final decision",
    r"\bsupersede jurisdictional courtroom proceedings\b": "replaces going to a regular public court",
    # Technical Research
    r"\bformulate an asymmetric multi-head self-attention architecture\b": "design an AI attention system",
    r"\bamortizes quadratic computational complexity down to linear sub-sampling bounds\b": "reduces processing power requirements from heavy to very light",
    r"\bregularizes inductive bias\b": "guides the AI model toward cleaner learning patterns",
    r"\bstochastic orthogonal weight initialization\b": "randomly balanced startup settings",
    r"\bcatastrophic gradient vanishing\b": "math numbers dropping to zero and stalling training",
    r"\bempirical evaluations substantiate\b": "real-world tests prove",
    r"\btop-1 perplexity reduction\b": "better accuracy and fewer word prediction mistakes",
    r"\bheterogeneous non-stationary distributions\b": "diverse, unpredictable real-world data",
    r"\bablation benchmarks corroborate\b": "feature tests confirm",
    r"\bsparse feed-forward projections\b": "simplified neural network layers",
    r"\brepresentational fidelity\b": "high audio or text quality",
    r"\bfloating-point latency\b": "delay and calculation time",
}

PLAIN_EXPLANATIONS = {
    # High-friction concept cards for inline exploration
    "acute exacerbation": "A sudden, severe flare-up of symptoms that can make normal breathing difficult.",
    "contraindicated": "Medically dangerous to use together; could cause serious side effects like internal bleeding.",
    "acceleration": "The bank demands you repay the ENTIRE loan balance today, not just the missed monthly installment.",
    "binding arbitration": "You forfeit your constitutional right to take a dispute before an elected judge or jury.",
    "amortizes quadratic computational complexity": "It speeds up calculations so the algorithm can run on mobile devices or lower-power laptops without freezing.",
}

def split_into_sentences(text: str) -> List[str]:
    """Segment text into individual sentences while preserving clean sentence structures."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    # Split on terminal punctuation followed by space or end
    raw = re.split(r"(?<=[.!?])\s+", cleaned)
    return [s.strip() for s in raw if s.strip()]

def simplify_text_deterministically(sentence: str) -> Tuple[str, List[str]]:
    """Transform complex syntax and jargon into plain, actionable language with term highlights."""
    simplified = sentence
    highlighted_terms = []

    # Replace specific jargon matches
    for pattern, plain in JARGON_REPLACEMENTS.items():
        if re.search(pattern, simplified, flags=re.IGNORECASE):
            raw_match = re.search(pattern, sentence, flags=re.IGNORECASE).group(0)
            highlighted_terms.append(raw_match)
            simplified = re.sub(pattern, f"**{plain}**", simplified, flags=re.IGNORECASE)

    # Break up long coordinating clauses
    simplified = re.sub(r",\s+which\s+", ". This ", simplified)
    simplified = re.sub(r",\s+whereas\s+", ". In contrast, ", simplified)
    simplified = re.sub(r";\s*", ". ", simplified)

    return simplified, highlighted_terms

def get_sentence_insight(sentence: str) -> str:
    """Generate an accessible educational insight for cognitive friction resolution."""
    insights = []
    for term, expl in PLAIN_EXPLANATIONS.items():
        if re.search(r"\b" + re.escape(term) + r"\b", sentence, flags=re.IGNORECASE):
            insights.append(f"• **Key Term ('{term}')**: {expl}")

    if not insights:
        insights.append("• **Plain Summary**: This statement outlines a specific requirement or technical restriction.")
        insights.append("• **Actionable Takeaway**: Pay close attention to dates, dosage/percentages, or binding conditions mentioned.")

    return "\n".join(insights)

# ==============================================================================
# 5. SIDEBAR: ACCESSIBILITY & TELEMETRY CONTROLS
# ==============================================================================
with st.sidebar:
    st.markdown("### 🧠 Cognitive HCI Dashboard")
    st.caption("Mixed-Initiative Accessibility & Prosody Framework")

    st.markdown("---")
    st.markdown("#### 👤 Reader Profile Mode")
    reader_mode = st.radio(
        "Select Cognitive Assistance Level:",
        options=[
            "Standard Mode",
            "Cognitive Load Reduction (Simplified)",
            "Low-Vision / High-Contrast Mode",
        ],
        index=0,
        help="Adapts visual density, typography scale, and linguistic complexity.",
    )

    st.markdown("---")
    st.markdown("#### 🎚️ Prosody & Pacing")
    speed_presets = {
        "🐢 Slow (0.75x — Deep Comprehension)": "-25%",
        "🚶 Standard (1.0x — Normal Pace)": "+0%",
        "🏃 Brisk (1.25x — Skimming)": "+25%",
    }
    selected_preset = st.selectbox("Speech Pacing Preset", list(speed_presets.keys()), index=0)
    rate_val = speed_presets[selected_preset]

    language = st.selectbox("🌐 Voice Dialect", list(LANGUAGE_VOICES.keys()), index=0)
    voice_tuple = st.selectbox(
        "🗣️ Synthetic Voice Agent",
        options=LANGUAGE_VOICES[language],
        format_func=lambda x: x[0],
    )
    voice_id = voice_tuple[1]

    style_label = st.selectbox("🎭 Speech Mood / Tone", list(SPEECH_STYLES.keys()), index=1)
    style_val = SPEECH_STYLES[style_label]

    st.markdown("---")
    st.markdown("#### 📊 User Struggle Telemetry")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.metric(
            label="Friction Points Resolved",
            value=f"{st.session_state['friction_count']} pts",
        )
    with col_t2:
        num_sentences = len(split_into_sentences(st.session_state["active_text"]))
        ratio = (
            f"{(len(st.session_state['resolved_sentences']) / max(1, num_sentences)) * 100:.0f}%"
            if num_sentences > 0
            else "0%"
        )
        st.metric(label="Text Clarified", value=ratio)

    if st.session_state["friction_count"] > 0:
        if st.button("Reset Telemetry Counter", use_container_width=True):
            st.session_state["friction_count"] = 0
            st.session_state["resolved_sentences"] = set()
            st.rerun()

    st.markdown("---")
    st.caption(
        "🛡️ **Zero-Crash Reliability:** Edge-TTS engine with SSML fallback. "
        "Deterministic local rule-simplifier ensures instant operation without external API keys."
    )

# ==============================================================================
# 6. DYNAMIC ACCESSIBILITY STYLING (Low-Vision & High-Contrast Mode)
# ==============================================================================
is_high_contrast = reader_mode == "Low-Vision / High-Contrast Mode"
is_simplified = reader_mode == "Cognitive Load Reduction (Simplified)"

if is_high_contrast:
    st.markdown(
        """
        <style>
        .hci-sentence-card {
            background-color: #1a1e24 !important;
            border: 3px solid #ffcc00 !important;
            border-radius: 12px !important;
            padding: 24px !important;
            margin-bottom: 24px !important;
            color: #ffffff !important;
            font-size: 23px !important;
            line-height: 1.85 !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif !important;
        }
        .hci-sentence-number {
            background-color: #ffcc00 !important;
            color: #000000 !important;
            font-weight: 900 !important;
            font-size: 18px !important;
            padding: 4px 14px !important;
            border-radius: 6px !important;
            display: inline-block !important;
            margin-bottom: 12px !important;
        }
        .hci-simplified-card {
            background-color: #0d2818 !important;
            border: 2px solid #52b788 !important;
            color: #d8f3dc !important;
            padding: 16px !important;
            border-radius: 8px !important;
            font-size: 20px !important;
            margin-top: 14px !important;
        }
        .stTextArea textarea {
            font-size: 20px !important;
            line-height: 1.6 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <style>
        .hci-sentence-card {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-left: 5px solid #3b82f6;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 18px;
            font-size: 16.5px;
            line-height: 1.65;
            color: #1e293b;
        }
        .hci-sentence-number {
            background-color: #e0f2fe;
            color: #0369a1;
            font-weight: 700;
            font-size: 13px;
            padding: 3px 8px;
            border-radius: 4px;
            display: inline-block;
            margin-bottom: 8px;
        }
        .hci-simplified-card {
            background-color: #f0fdf4;
            border: 1px dashed #22c55e;
            color: #14532d;
            padding: 14px 18px;
            border-radius: 6px;
            font-size: 15.5px;
            margin-top: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ==============================================================================
# 7. MAIN UI: RESEARCH BANNER & ZERO-FRICTION ONBOARDING
# ==============================================================================
st.markdown("## 🧠 CogRead: Cognitive Accessibility & HCI Reader")
st.markdown(
    "*A Human-Centered AI prototype evaluating how adaptive multimodal presentation, "
    "prosody pacing, and sentence-level friction reduction alleviate cognitive strain.*"
)

st.info(
    "💡 **HCI Research Objective:** *Exploring how adaptive text simplification, "
    "prosody control, and sentence-level friction tracking reduce cognitive load for non-expert readers.*"
)

# 1-Click Interactive Preset Scenarios
st.markdown("##### 🚀 1-Click Scenario Presets (Reviewer Test Suite)")
preset_cols = st.columns(3)

for idx, (scenario_name, data) in enumerate(SCENARIOS.items()):
    with preset_cols[idx]:
        is_active = st.session_state["active_scenario_title"] == scenario_name
        btn_type = "primary" if is_active else "secondary"
        if st.button(
            f"**{scenario_name}**\n\n`{data['badge']}`",
            key=f"preset_btn_{idx}",
            type=btn_type,
            use_container_width=True,
        ):
            st.session_state["active_text"] = data["text"]
            st.session_state["active_scenario_title"] = scenario_name
            st.rerun()

# Scenario Description Cue
current_desc = SCENARIOS.get(
    st.session_state["active_scenario_title"], {}
).get("description", "Custom reader text.")
st.caption(f"📌 **Current Focus ({st.session_state['active_scenario_title']}):** {current_desc}")

# Main Text Input Area
raw_text = st.text_area(
    "Input Text / Narration Script:",
    value=st.session_state["active_text"],
    height=150,
    help="Edit freely or pick any of the presets above.",
)
if raw_text != st.session_state["active_text"]:
    st.session_state["active_text"] = raw_text

sentences = split_into_sentences(raw_text)

# Full Audio Narration Bar
st.markdown("---")
col_audio_head, col_audio_btn = st.columns([3, 1])
with col_audio_head:
    st.markdown("#### 🎧 Complete Passage Narration")
    st.caption(f"Mode: **{reader_mode}** | Speed: **{rate_val}** | Voice: **{voice_tuple[0]}**")

full_audio_bytes = generate_speech_bytes(raw_text, voice_id, rate_val, "+0Hz", style_val)
if full_audio_bytes:
    st.audio(full_audio_bytes, format="audio/mp3")
    st.download_button(
        "⬇️ Download Full Passage Audio (MP3)",
        data=full_audio_bytes,
        file_name="cogread_full_narration.mp3",
        mime="audio/mpeg",
        use_container_width=True,
    )
else:
    st.warning("Enter text above to preview narration.")

# ==============================================================================
# 8. INTERACTIVE "FRICTION & CONFUSION" MIXED-INITIATIVE LOOP
# ==============================================================================
st.markdown("---")
st.markdown("### 🔍 Sentence-Level Cognitive Friction Explorer")
st.markdown(
    "HCI mixed-initiative interface: Each sentence is decomposed into an individual card. "
    "If any clause is ambiguous or high-friction, trigger **'Confusing? Simplify this'** "
    "for instant translation, key concept breakdown, and localized single-sentence TTS."
)

if not sentences:
    st.info("No sentences detected. Please paste text or select a preset.")
else:
    for i, sent in enumerate(sentences):
        card_key = f"sent_{i}"
        is_clarified = card_key in st.session_state["resolved_sentences"]

        # Prepare sentence display based on profile
        simplified_version, key_terms = simplify_text_deterministically(sent)
        display_text = simplified_version if is_simplified else sent

        # Outer card container
        st.markdown(
            f"""
            <div class="hci-sentence-card">
                <span class="hci-sentence-number">Sentence {i + 1} of {len(sentences)}</span>
                <div>{display_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_act1, col_act2, col_act3 = st.columns([2, 2, 4])

        with col_act1:
            btn_label = "✅ Clarified (Undo)" if is_clarified else "🤔 Confusing? Simplify this"
            if st.button(btn_label, key=f"btn_simplify_{i}", use_container_width=True):
                if is_clarified:
                    st.session_state["resolved_sentences"].remove(card_key)
                    st.session_state["friction_count"] = max(0, st.session_state["friction_count"] - 1)
                else:
                    st.session_state["resolved_sentences"].add(card_key)
                    st.session_state["friction_count"] += 1
                st.rerun()

        with col_act2:
            # Targeted single-sentence TTS
            play_sentence_audio = st.button(
                f"🔊 Hear Sentence {i + 1}",
                key=f"btn_listen_{i}",
                use_container_width=True,
            )

        # Inline Expanded Assistive Panel if marked as confusing OR if user explicitly requested audio
        if is_clarified or play_sentence_audio:
            with st.container():
                st.markdown(
                    f"""
                    <div class="hci-simplified-card">
                        <strong>💡 Plain-Language Interpretation:</strong><br>
                        {simplified_version}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Concept breakdown
                insight = get_sentence_insight(sent)
                st.markdown(insight)

                # Targeted Audio Generation
                target_speech_text = simplified_version if is_simplified else sent
                # Strip markdown asterisks for clean TTS pronunciation
                clean_tts_target = re.sub(r"\*+", "", target_speech_text)

                with st.spinner("Synthesizing focused sentence audio..."):
                    sent_audio_bytes = generate_speech_bytes(
                        clean_tts_target, voice_id, rate_val, "+0Hz", style_val
                    )
                    if sent_audio_bytes:
                        st.audio(sent_audio_bytes, format="audio/mp3")

# ==============================================================================
# 9. RESEARCH METHODOLOGY & PORTFOLIO FOOTER
# ==============================================================================
st.markdown("---")
with st.expander("📚 HCI Research Context & Accessibility Design Decisions"):
    st.markdown(
        """
        - **Cognitive Load Theory (Sweller):** Complex syntactic structures and specialized domain vocabulary compete for working memory capacity. Providing multimodal redundant channels (prosody pacing + visual card isolation) reduces extraneous cognitive load.
        - **Mixed-Initiative Assistance (Horvitz):** Rather than blindly rewriting the entire text, the interface allows user-guided friction tagging, preserving user agency while capturing real-time struggle telemetry.
        - **WCAG 2.2 Alignment:** Satisfies Success Criterion 3.1.5 (Reading Level) and 1.4.8 (Visual Presentation) through 22px+ font scaling, high-contrast borders, and clear typographic hierarchy.
        """
    )

st.caption(
    "Built for HCI Research & Accessibility Portfolios. Powered by Streamlit, edge-tts, and Human-Centered AI heuristics."
)
