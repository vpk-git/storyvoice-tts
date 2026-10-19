import asyncio
import os
import tempfile
from pathlib import Path

import edge_tts
import streamlit as st

st.set_page_config(page_title="StoryVoice TTS", page_icon="🎙️", layout="centered")
st.title("🎙️ StoryVoice — Text-to-Speech")
st.caption("Turn scripts into natural-sounding narration and download the result as an MP3.")

DEFAULT_TEXT = """What happens when ten years of love turn into pain, jealousy, and doubt?
In this episode, one decision could change their relationship forever."""

LANGUAGE_VOICES = {
    "English (US)": [
        ("Jenny — conversational", "en-US-JennyNeural"),
        ("Aria — expressive", "en-US-AriaNeural"),
        ("Guy — warm male", "en-US-GuyNeural"),
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
    "Hindi": [
        ("Swara — female", "hi-IN-SwaraNeural"),
        ("Madhur — male", "hi-IN-MadhurNeural"),
    ],
    "Kannada": [
        ("Sapna — female", "kn-IN-SapnaNeural"),
        ("Gagan — male", "kn-IN-GaganNeural"),
    ],
    "Tamil": [
        ("Pallavi — female", "ta-IN-PallaviNeural"),
        ("Valluvar — male", "ta-IN-ValluvarNeural"),
    ],
    "Telugu": [
        ("Shruti — female", "te-IN-ShrutiNeural"),
        ("Mohan — male", "te-IN-MohanNeural"),
    ],
    "French": [
        ("Denise — female", "fr-FR-DeniseNeural"),
        ("Henri — male", "fr-FR-HenriNeural"),
    ],
    "German": [
        ("Katja — female", "de-DE-KatjaNeural"),
        ("Conrad — male", "de-DE-ConradNeural"),
    ],
    "Italian": [
        ("Elsa — female", "it-IT-ElsaNeural"),
        ("Diego — male", "it-IT-DiegoNeural"),
    ],
    "Japanese": [
        ("Nanami — female", "ja-JP-NanamiNeural"),
        ("Keita — male", "ja-JP-KeitaNeural"),
    ],
    "Korean": [
        ("SunHi — female", "ko-KR-SunHiNeural"),
        ("InJoon — male", "ko-KR-InJoonNeural"),
    ],
    "Chinese (Mandarin)": [
        ("Xiaoxiao — female", "zh-CN-XiaoxiaoNeural"),
        ("Yunxi — male", "zh-CN-YunxiNeural"),
    ],
}

SPEECH_STYLES = {
    "Default (natural)": None,
    "😠 Angry": "angry",
    "😊 Cheerful": "cheerful",
    "😢 Sad": "sad",
    "😌 Calm": "calm",
    "😨 Fearful": "fearful",
    "🤗 Friendly": "friendly",
    "😤 Shouting": "shouting",
    "🤫 Whispering": "whispering",
    "😃 Excited": "excited",
    "🙏 Hopeful": "hopeful",
    "😐 Serious": "serious",
    "🥺 Gentle": "gentle",
    "😔 Depressed": "depressed",
    "😳 Embarrassed": "embarrassed",
    "💚 Empathetic": "empathetic",
    "😒 Unfriendly": "unfriendly",
    "📰 Newscast": "newscast",
    "🎙️ Narration (professional)": "narration-professional",
    "🎶 Lyrical": "lyrical",
    "💬 Chat": "chat",
    "📢 Advertisement": "advertisement-upbeat",
    "📖 Poetry reading": "poetry-reading",
    "🏟️ Sports commentary": "sports-commentary",
    "🎬 Documentary": "documentary-narration",
}

# Prosody adjustments per mood — these work with ALL voices.
# Format: (rate_offset%, pitch_offset_Hz, volume_offset%)
MOOD_PROSODY = {
    "angry":                 (20,   5,   15),
    "cheerful":              (10,   4,   10),
    "sad":                   (-20, -4,  -10),
    "calm":                  (-15, -2,   -5),
    "fearful":               (15,   6,  -10),
    "friendly":              (5,    3,    5),
    "shouting":              (10,   8,   25),
    "whispering":            (-10, -3,  -30),
    "excited":               (25,   6,   15),
    "hopeful":               (5,    3,    5),
    "serious":               (-5,  -2,    5),
    "gentle":                (-15, -2,  -15),
    "depressed":             (-25, -6,  -15),
    "embarrassed":           (-10, -2,  -10),
    "empathetic":            (-5,  -1,   -5),
    "unfriendly":            (5,   -3,   10),
    "newscast":              (0,    0,    5),
    "narration-professional":(-5,   0,    5),
    "lyrical":               (-15,  4,    0),
    "chat":                  (10,   3,    0),
    "advertisement-upbeat":  (15,   5,   10),
    "poetry-reading":        (-20,  3,    0),
    "sports-commentary":     (25,   7,   15),
    "documentary-narration": (-10, -1,    5),
}


with st.sidebar:
    st.header("Voice settings")

    language = st.selectbox(
        "🌐 Language",
        options=list(LANGUAGE_VOICES.keys()),
        index=0,
    )

    voice = st.selectbox(
        "🗣️ Voice",
        options=LANGUAGE_VOICES[language],
        format_func=lambda item: item[0],
    )

    style_label = st.selectbox(
        "🎭 Speech mood",
        options=list(SPEECH_STYLES.keys()),
        index=0,
    )
    style = SPEECH_STYLES[style_label]
    speed_options = {
        "0.5x": "-50%",
        "0.75x": "-25%",
        "1x": "+0%",
        "1.25x": "+25%",
        "1.5x": "+50%",
        "1.75x": "+75%",
        "2x": "+100%",
    }
    speed_label = st.select_slider(
        "Speaking speed",
        options=list(speed_options.keys()),
        value="1x",
    )
    rate = speed_options[speed_label]
    pitch = st.select_slider("Pitch", options=["-5Hz", "-2Hz", "+0Hz", "+2Hz", "+5Hz"], value="+0Hz")

text = st.text_area("Paste your narration script", value=DEFAULT_TEXT, height=280,
                    placeholder="Paste your episode recap or narration here...")
st.caption(f"{len(text):,} characters")

col1, col2 = st.columns(2)
with col1:
    generate = st.button("Generate MP3", type="primary", use_container_width=True)
with col2:
    clear = st.button("Clear text", use_container_width=True)

if clear:
    st.session_state["script"] = ""
    st.rerun()

if generate:
    if not text.strip():
        st.error("Paste some text first.")
    else:
        def _clamp(val, lo, hi):
            return max(lo, min(hi, val))

        def _parse_rate(s):
            """'+25%' -> 25"""
            return int(s.replace("%", "").replace("+", ""))

        def _parse_pitch(s):
            """'+2Hz' -> 2"""
            return int(s.replace("Hz", "").replace("+", ""))

        def _fmt_rate(v):
            return f"+{v}%" if v >= 0 else f"{v}%"

        def _fmt_pitch(v):
            return f"+{v}Hz" if v >= 0 else f"{v}Hz"

        def _fmt_volume(v):
            return f"+{v}%" if v >= 0 else f"{v}%"

        async def make_audio(content, voice_name, rate_value, pitch_value,
                             output_path, style_value=None):
            """Generate audio using edge_tts.

            When *style_value* is provided:
            1. Prosody (rate/pitch/volume) is adjusted to simulate the mood.
               This works with **every** voice.
            2. An ``<mstts:express-as>`` SSML tag is also injected for voices
               that support Microsoft's native style engine (bonus quality).
            """
            import edge_tts.communicate as _etc

            _original_mkssml = _etc.mkssml

            # Compute mood-adjusted prosody values.
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
                """SSML with mstts:express-as + mood-adjusted prosody."""
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
                """SSML with mood-adjusted prosody only (no express-as)."""
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
                # --- Tier 1: express-as + mood prosody ---
                if style_value:
                    _etc.mkssml = _mkssml_with_express_as
                communicate = edge_tts.Communicate(
                    content, voice_name,
                    rate=rate_value, pitch=pitch_value,
                )
                await communicate.save(output_path)
            except Exception:
                # --- Tier 2: mood prosody only (drop express-as) ---
                if style_value:
                    try:
                        _etc.mkssml = _mkssml_prosody_only
                        communicate = edge_tts.Communicate(
                            content, voice_name,
                            rate=rate_value, pitch=pitch_value,
                        )
                        await communicate.save(output_path)
                        return
                    except Exception:
                        pass
                # --- Tier 3: plain defaults ---
                _etc.mkssml = _original_mkssml
                st.warning("Mood could not be applied. Using default voice.")
                communicate = edge_tts.Communicate(content, voice_name)
                await communicate.save(output_path)
            finally:
                _etc.mkssml = _original_mkssml


        with st.spinner("Generating narration... Keep this tab open."):
            output_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                    output_path = tmp.name
                asyncio.run(make_audio(text, voice[1], rate, pitch, output_path, style))
                audio_bytes = Path(output_path).read_bytes()
                st.success("Your narration is ready.")
                st.audio(audio_bytes, format="audio/mp3")
                st.download_button("⬇️ Download narration (MP3)", data=audio_bytes,
                                   file_name="storyvoice_narration.mp3", mime="audio/mpeg",
                                   type="primary", use_container_width=True)
            except Exception as exc:
                st.error("Audio generation failed. Check your internet connection and try again. The online voice service may be temporarily unavailable.")
                with st.expander("Technical details"):
                    st.code(str(exc))
            finally:
                if output_path and os.path.exists(output_path):
                    os.unlink(output_path)

st.divider()
st.caption("Uses edge-tts to access online Microsoft Edge text-to-speech voices. It is not an official Microsoft API and requires internet access. Voice availability and service limits can change. Check applicable terms before commercial use.")
