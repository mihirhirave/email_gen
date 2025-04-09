import base64
import requests
import streamlit as st
from urllib.parse import urlparse

st.set_page_config(page_title="GitHub README Extractor", page_icon="🐙", layout="wide")

st.title("🐙 GitHub README Extractor")

url = st.text_input(
    "GitHub Profile or Repository URL",
    placeholder="https://github.com/user  or  https://github.com/user/repo",
)

token = st.text_input("GitHub Personal Access Token (optional)", type="password")


def gh_headers(tok: str):
    h = {"Accept": "application/vnd.github+json"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def fetch_readme(owner: str, repo: str, h: dict) -> str:
    try:
        r = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/readme",
            headers=h,
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            return base64.b64decode(data.get("content", "")).decode(errors="ignore")
        return "README not found."
    except requests.exceptions.RequestException as e:
        return f"Error fetching README: {e}"


if st.button("Extract READMEs"):
    if not url.strip():
        st.error("Please enter a GitHub URL.")
    else:
        p = urlparse(url)
        if p.netloc.lower().rstrip("/") not in {"github.com", "www.github.com"}:
            st.error("URL must be from github.com")
        else:
            segments = [s for s in p.path.split("/") if s]
            headers = gh_headers(token.strip())
            try:
                if len(segments) == 1:
                    user = segments[0]
                    repo_resp = requests.get(
                        f"https://api.github.com/users/{user}/repos?per_page=100",
                        headers=headers,
                        timeout=15,
                    )
                    if repo_resp.status_code != 200:
                        st.error("Failed to fetch repositories (user may be private or rate‑limited).")
                    else:
                        repos = repo_resp.json()
                        st.success(f"Found {len(repos)} public repositories for {user}.")
                        for repo in repos:
                            name = repo["name"]
                            readme_text = fetch_readme(user, name, headers)
                            with st.expander(name, expanded=False):
                                st.text_area("README", readme_text, height=400, key=f"ta_{name}")
                                st.download_button(
                                    "Download README",
                                    readme_text,
                                    f"{name}_README.md",
                                    "text/markdown",
                                    key=f"dl_{name}",
                                )
                elif len(segments) >= 2:
                    owner, repo = segments[0], segments[1]
                    readme_text = fetch_readme(owner, repo, headers)
                    st.subheader(f"{owner}/{repo}")
                    st.text_area("README", readme_text, height=400)
                    st.download_button(
                        "Download README", readme_text, "README.md", "text/markdown"
                    )
                else:
                    st.error("Invalid GitHub URL.")
            except requests.exceptions.RequestException as e:
                st.error(f"Network error: {e}")
