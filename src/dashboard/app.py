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
    st.caption("Paste screening questions from any job application — get personalized answers from your resume.")

    # Resume: always allow upload; fall back to local file if nothing uploaded
    resume_text = ""
    uploaded = st.file_uploader(
        "Upload a tailored resume PDF (optional — overrides default resume)",
        type=["pdf"],
        key="resume_upload",
    )
    if uploaded:
        resume_text = parse_from_bytes(uploaded.read())
        st.success("Using uploaded resume.")
    elif os.path.exists(RESUME_PATH):
        resume_text = get_resume_text()
        st.caption("Using default resume on file. Upload above to override.")
    else:
        st.warning("No resume found. Upload your resume PDF above.")

    job_context = st.text_area(
        "Job context (optional — paste job title + key requirements)",
        height=80,
        placeholder="e.g. Data Developer at GGC. Requires: Python, SQL, ETL pipelines, Azure...",
    )

    mode = st.radio("Mode", ["Single question", "Multiple questions"], horizontal=True)

    if mode == "Single question":
        question = st.text_area(
            "Application question",
            height=120,
            placeholder="e.g. Why do you think you will be a fit for this role?",
        )
        if st.button("Generate Answer", type="primary", disabled=not (question and resume_text)):
            with st.spinner("Generating personalized answer..."):
                result = answer(question=question, job_context=job_context, resume_text=resume_text)
            st.divider()
            st.subheader("Your Answer")
            st.write(result)
            st.download_button("Copy as text", data=result, file_name="answer.txt", mime="text/plain")

    else:
        st.caption("Paste all questions — one per line. Number them or not, it doesn't matter.")
        questions_text = st.text_area(
            "All application questions",
            height=200,
            placeholder="Why do you think you will be a fit for this role?\nDescribe your experience with data pipelines.\nWhat is your expected salary?",
        )

        if st.button("Generate All Answers", type="primary", disabled=not (questions_text and resume_text)):
            questions = [q.strip() for q in questions_text.strip().splitlines() if q.strip()]
            all_answers = []

            progress = st.progress(0, text="Answering questions...")
            for i, q in enumerate(questions):
                with st.spinner(f"Question {i+1}/{len(questions)}..."):
                    ans = answer(question=q, job_context=job_context, resume_text=resume_text)
                all_answers.append((q, ans))
                progress.progress((i + 1) / len(questions), text=f"Answered {i+1}/{len(questions)}")

            progress.empty()
            st.divider()

            full_text = ""
            for i, (q, ans) in enumerate(all_answers, 1):
                st.markdown(f"**Q{i}: {q}**")
                st.write(ans)
                st.divider()
                full_text += f"Q{i}: {q}\nA: {ans}\n\n"

            st.download_button(
                "Download all answers as text",
                data=full_text.strip(),
                file_name="application_answers.txt",
                mime="text/plain",
            )
