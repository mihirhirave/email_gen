import base64
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import requests
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

# --------------------------------------------------
# Load .env
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
# Streamlit page
# --------------------------------------------------
st.set_page_config(page_title="GitHub Interview Prep", page_icon="🐙", layout="wide")
st.title("🐙 GitHub‑Based Interview Question Generator")

# --------------------------------------------------
# Session defaults
# --------------------------------------------------
st.session_state.setdefault("questions", [])
st.session_state.setdefault("answers", [])
st.session_state.setdefault("idx", 0)

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def gh_headers(tok: str | None = None) -> dict:
    hdrs = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "gh-readme-extractor/1.0",
    }
    if tok:
        hdrs["Authorization"] = f"Bearer {tok}"
    return hdrs


def fetch_readme(owner: str, repo: str, hdrs: dict) -> str:
    try:
        r = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/readme",
            headers=hdrs,
            timeout=15,
        )
        if r.status_code == 200:
            return base64.b64decode(r.json().get("content", "")).decode(errors="ignore")
    except requests.exceptions.RequestException:
        pass
    return ""

# --------------------------------------------------
# Input form
# --------------------------------------------------
with st.form("inputs"):
    github_url = st.text_input("GitHub Profile URL", placeholder="https://github.com/username")
    gh_token = st.text_input("GitHub Personal Access Token (optional)", type="password")
    portfolio_url = st.text_input("Portfolio Website (optional)", placeholder="https://yourportfolio.com/projects")
    student_name = st.text_input("Your Name", placeholder="e.g., Jane Doe")
    university_name = st.text_input("Your University/Organization", placeholder="e.g., University of Example")
    submitted = st.form_submit_button("Generate Questions")

# --------------------------------------------------
# Generate questions
# --------------------------------------------------
if submitted:
    # basic validation
    if not github_url.strip():
        st.error("GitHub URL is required.")
        st.stop()

    parsed = urlparse(github_url)
    if parsed.netloc.lower().rstrip("/") not in {"github.com", "www.github.com"}:
        st.error("Enter a valid github.com URL.")
        st.stop()

    user_path = [seg for seg in parsed.path.split("/") if seg]
    if len(user_path) != 1:
        st.error("Provide a profile URL, not a repository URL.")
        st.stop()

    user = user_path[0]
    hdrs = gh_headers(gh_token or None)

    # fetch repos
    try:
        repo_resp = requests.get(
            f"https://api.github.com/users/{user}/repos?per_page=100",
            headers=hdrs,
            timeout=15,
        )
    except requests.exceptions.RequestException as exc:
        st.error(f"Network error while fetching repositories: {exc}")
        st.stop()

    if repo_resp.status_code != 200:
        msg = (
            repo_resp.json().get("message", "Unknown error")
            if repo_resp.headers.get("Content-Type", "").startswith("application/json")
            else repo_resp.text
        )
        st.error(f"Failed to fetch repositories. Status {repo_resp.status_code}: {msg}")
        st.stop()

    repos = repo_resp.json()
    if not repos:
        st.error("No public repositories found for this user.")
        st.stop()

    # gather READMEs
    docs = []
    for repo in repos:
        readme_txt = fetch_readme(user, repo["name"], hdrs)
        if readme_txt:
            docs.append(f"# {repo['name']}\n{readme_txt}")

    corpus = "\n\n".join(docs)
    if not corpus.strip():
        st.error("No READMEs found in the user's repositories.")
        st.stop()

    # OpenAI key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY environment variable not set. Add it to your environment or .env file.")
        st.stop()

    # LLM call
    llm = ChatOpenAI(api_key=api_key, temperature=0)
    prompt = PromptTemplate.from_template(
        """
        You are an interviewer. Based on the following project documentation, generate 10 insightful questions to ask the candidate. Return the questions as a JSON array of strings with no additional keys or wrapper text.
        ### DOCUMENTATION
        {docs}
        """
    )
    chain = prompt | llm
    try:
        raw = chain.invoke({"docs": corpus}).content
        qs = json.loads(raw)
        if isinstance(qs, dict):
            qs = list(qs.values())
        if not isinstance(qs, list):
            raise ValueError("Parsed JSON is not a list of questions.")
    except Exception as exc:
        st.error(f"Failed to parse questions from LLM response: {exc}")
        st.stop()

    # store state
    st.session_state.questions = qs
    st.session_state.answers = []
    st.session_state.idx = 0

# --------------------------------------------------
# Q&A loop
# --------------------------------------------------
if st.session_state.get("questions"):
    i = st.session_state.idx
    if i < len(st.session_state.questions):
        question = st.session_state.questions[i]
        st.subheader(f"Question {i + 1}")
        st.write(question)
        answer = st.text_area("Your Answer", key=f"ans_{i}")
        if st.button("Submit Answer"):
            st.session_state.answers.append({"question": question, "answer": answer})
            st.session_state.idx += 1
            st.experimental_rerun()
    else:
        st.success("All questions answered.")
        st.write(st.session_state.answers)
        st.download_button(
            label="Download Q&A JSON",
            data=json.dumps(st.session_state.answers, indent=2),
            file_name="qa.json",
            mime="application/json",
        )
