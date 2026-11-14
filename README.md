# CogRead: Human-Centered AI & Cognitive Accessibility Reader

An interactive Human-Computer Interaction (HCI) research prototype exploring how adaptive text simplification, prosody control, and sentence-level friction tracking reduce cognitive load for non-expert readers.

---

## 🎯 Research Framing & Core Contributions
- **Multimodal Cognitive Load Reduction:** Combines synchronized prosody adjustments with visual sentence card segmentation to reduce split-attention effect and working memory strain.
- **Mixed-Initiative Interaction (Horvitz):** Sentence-level "Confusing? Simplify this" triggers maintain user agency and deliver targeted plain-language explanations with isolated audio clips.
- **User Struggle Telemetry:** Real-time friction metrics track which clauses cause reader cognitive burden.
- **Universal Accessibility (WCAG 2.2):** Low-Vision / High-Contrast profile with 22px+ font scaling, high-contrast borders, and clear typographic hierarchy.

---

## 🚀 1-Click Sample Scenarios
The reader includes 3 zero-friction scenarios ready for reviewers:
1. **Medical Discharge Summary:** Translates clinical jargon (acute exacerbation, levofloxacin, ambulatory titration, contraindications) into plain language.
2. **Bank Loan / Legal Clause:** Simplifies complex financial terminology (acceleration clauses, compounding interest, indemnity, binding arbitration).
3. **Technical Research Abstract:** Demystifies academic computer science writing (asymmetric self-attention, inductive bias, asymptotic complexity).

---

## ⚙️ Quick Start

### 1. Installation
Ensure Python 3.10+ is installed:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Run the Prototype
```powershell
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## ☁️ Deployment on Streamlit Community Cloud
- **Zero Authentication Walls:** Works immediately without mandatory API keys or login screens.
- **Cached Synthesis (`@st.cache_data`):** Edge-TTS audio generations are cached for instantaneous replay.
- **Fail-Safe Heuristics:** Built-in deterministic plain-language simplification rules ensure the reader never crashes even if external APIs are unreachable.
