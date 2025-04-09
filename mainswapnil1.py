import os
import json
import io
from pathlib import Path
import requests
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

# Optional PDF generator
try:
    from fpdf import FPDF  # pip install fpdf
except ImportError:
    FPDF = None

# --------------------------------------------------
# Load environment variables (.env is optional)
# --------------------------------------------------
ENV_PATH = Path(__file__).resolve().parent / ".env"
if ENV_PATH.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=ENV_PATH, override=True)
    except ModuleNotFoundError:
        with ENV_PATH.open() as fh:
            for line in fh:
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k, v)

# --------------------------------------------------
# Streamlit configuration
# --------------------------------------------------
st.set_page_config(page_title="Interview Question Generator", page_icon="📝", layout="wide")
st.title("📝 Custom Interview Question Generator")

# --------------------------------------------------
# Session defaults
# --------------------------------------------------
st.session_state.setdefault("questions", [])
st.session_state.setdefault("answers", [])
st.session_state.setdefault("idx", 0)

# --------------------------------------------------
# Helper to fetch portfolio text
# --------------------------------------------------

def fetch_portfolio_text(url: str) -> str:
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return ""

# --------------------------------------------------
# Input form
# --------------------------------------------------
with st.form("inputs"):
    portfolio_url = st.text_input("Portfolio Website (optional)", placeholder="https://yourportfolio.com/projects")
    student_name = st.text_input("Your Name", placeholder="e.g., Jane Doe")
    university_name = st.text_input("Your University/Organization", placeholder="e.g., University of Example")
    submitted = st.form_submit_button("Generate Questions")

# --------------------------------------------------
# Generate questions using OpenAI
# --------------------------------------------------
if submitted:
    if not student_name.strip():
        st.error("Please enter your name.")
        st.stop()

    portfolio_text = fetch_portfolio_text(portfolio_url) if portfolio_url.strip() else ""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY environment variable not set. Add it to your environment or .env file.")
        st.stop()

    llm = ChatOpenAI(api_key=api_key, temperature=0)
    prompt = PromptTemplate.from_template(
        """
        You are an interviewer preparing to evaluate a candidate.
        ### CANDIDATE DETAILS
        Name: {name}
        University / Organization: {university}
        ### PORTFOLIO CONTENT
        {portfolio}
        ### TASK
        Draft 10 in‑depth, insightful interview questions tailored to the candidate's background. Focus on technical depth, problem‑solving ability, and real‑world application of skills. Return the questions as a JSON array of strings with no additional keys or explanatory text.
        """
    )

    chain = prompt | llm
    try:
        raw = chain.invoke({"name": student_name, "university": university_name, "portfolio": portfolio_text}).content
        qs = json.loads(raw)
        if not isinstance(qs, list):
            raise ValueError("LLM did not return a JSON array of questions.")
    except Exception as exc:
        st.error(f"Failed to generate questions: {exc}")
        st.stop()

    st.session_state.questions = qs
    st.session_state.answers = []
    st.session_state.idx = 0

# --------------------------------------------------
# Q&A loop
# --------------------------------------------------
if st.session_state.questions:
    i = st.session_state.idx
    if i < len(st.session_state.questions):
        q = st.session_state.questions[i]
        st.subheader(f"Question {i + 1}")
        st.write(q)
        ans = st.text_area("Your Answer", key=f"ans_{i}")
        if st.button("Submit Answer"):
            st.session_state.answers.append({"question": q, "answer": ans})
            st.session_state.idx += 1
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()
    else:
        st.success("All questions answered. Thank you!")
        st.info("You can download your responses below.")

        # --------------------------------------------------
        # Generate PDF
        # --------------------------------------------------
        if FPDF is not None:
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            for idx, qa in enumerate(st.session_state.answers, 1):
                pdf.multi_cell(0, 10, f"Q{idx}: {qa['question']}")
                pdf.multi_cell(0, 10, f"A{idx}: {qa['answer']}")
                pdf.ln(2)
            pdf_bytes = pdf.output(dest="S").encode("latin-1")
            st.download_button(
                label="Download Q&A PDF",
                data=pdf_bytes,
                file_name="qa.pdf",
                mime="application/pdf",
            )
        else:
            st.warning("Install the 'fpdf' package to enable PDF downloads (pip install fpdf).")

        # Also allow JSON download for convenience
        st.download_button(
            label="Download Q&A JSON",
            data=json.dumps(st.session_state.answers, indent=2),
            file_name="qa.json",
            mime="application/json",
        )
