import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import os
import json
import streamlit as st
from src.storage.database import get_all_jobs, get_job_by_hash
from src.analyzer.qa_responder import answer
from src.analyzer.resume_parser import parse_from_bytes, get_resume_text
from config.settings import RESUME_PATH

st.set_page_config(page_title="Job Hunter", page_icon="🎯", layout="wide")

# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.title("🎯 Job Hunter")
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()
page = st.sidebar.radio("Navigate", ["Dashboard", "Q&A Responder"])
days = st.sidebar.slider("Show jobs from last N days", 1, 14, 7)
tier_filter = st.sidebar.multiselect(
    "Filter by tier", ["Strong", "Maybe", "Skip"], default=["Strong", "Maybe"]
)

# ── Dashboard Page ──────────────────────────────────────────────────────────
if page == "Dashboard":
    st.title("📊 Job Matches")

    all_jobs = get_all_jobs(days=days)
    scored_all = [j for j in all_jobs if j.get("ats_score") not in (None, "")]
    pending    = [j for j in all_jobs if j.get("ats_score") in (None, "")]

    # Apply tier filter only to the scored display, not the counts
    scored = [j for j in scored_all if j.get("fit_tier") in tier_filter] if tier_filter else scored_all

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Jobs", len(all_jobs))
    col2.metric("Strong Matches", sum(1 for j in scored_all if j["fit_tier"] == "Strong"))
    col3.metric("Maybe", sum(1 for j in scored_all if j["fit_tier"] == "Maybe"))
    col4.metric("Pending Scoring", len(pending))

    st.divider()

    if not scored:
        st.info("No scored jobs yet. Run `python main.py` to fetch and score jobs.")
    else:
        for job in scored:
            score = job["ats_score"]
            tier = job["fit_tier"]
            color = {"Strong": "🟢", "Maybe": "🟡", "Skip": "🔴"}.get(tier, "⚪")

            with st.expander(
                f"{color} **{job['title']}** — {job['company']} | {job['location']} | {score}/100",
                expanded=(tier == "Strong"),
            ):
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    st.markdown(f"**Summary:** {job.get('ats_summary', '')}")
                    matched = json.loads(job.get("matched_keywords") or "[]")
                    missing = json.loads(job.get("missing_keywords") or "[]")
                    if matched:
                        st.success(f"✅ Matched: {', '.join(matched)}")
                    if missing:
                        st.warning(f"⚠️ Missing: {', '.join(missing)}")
                with col_b:
                    st.metric("ATS Score", f"{score}/100")
                    st.caption(f"Source: {job.get('source', '')}")
                    st.caption(f"Posted: {job.get('date_posted', 'N/A')}")

                st.link_button("Apply →", job["url"])

    if pending:
        st.divider()
        st.subheader(f"⏳ {len(pending)} jobs pending ATS scoring")
        st.caption("Run `python main.py` to score them.")

# ── Q&A Responder Page ──────────────────────────────────────────────────────
elif page == "Q&A Responder":
    st.title("💬 Job Application Q&A")
    st.caption("Paste a question from Workday / Greenhouse / Lever — get an answer using your actual resume.")

    # Resolve resume: use local file if present, otherwise ask for upload
    resume_text = ""
    if os.path.exists(RESUME_PATH):
        resume_text = get_resume_text()
    else:
        uploaded = st.file_uploader(
            "Upload your resume PDF (required on cloud — stored only for this session)",
            type=["pdf"],
            key="resume_upload",
        )
        if uploaded:
            resume_text = parse_from_bytes(uploaded.read())
            st.success("Resume loaded.")
        else:
            st.info("Upload your resume PDF above to use the Q&A feature.")

    job_context = st.text_area(
        "Job context (optional — paste the job title + key requirements)",
        height=100,
        placeholder="e.g. Senior Data Engineer at Shopify. Requires: PySpark, Delta Lake, dbt, Airflow...",
    )

    question = st.text_area(
        "Application question",
        height=120,
        placeholder="e.g. Describe your experience designing and optimizing large-scale data pipelines.",
    )

    if st.button("Generate Answer", type="primary", disabled=not (question and resume_text)):
        with st.spinner("Generating personalized answer..."):
            result = answer(question=question, job_context=job_context, resume_text=resume_text)
        st.divider()
        st.subheader("Your Answer")
        st.write(result)
        st.divider()
        st.download_button("Copy as text", data=result, file_name="answer.txt", mime="text/plain")
