import io
import json
import re
import requests
import pandas as pd
import streamlit as st
from pypdf import PdfReader


# ============================================================
# INTERVIEWIQ AI
# AI INTERVIEW & PLACEMENT INTELLIGENCE PLATFORM
# ============================================================

# ============================================================
# 🔑 OPENROUTER API KEY
# Paste your API key between the quotes.
# ============================================================

OPENROUTER_API_KEY = " api key"

# You can change this model if needed.
OPENROUTER_MODEL = "openai/gpt-4o-mini"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="InterviewIQ AI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "resume_text": "",
    "resume_name": "",
    "job_description": "",
    "ats_result": None,
    "skill_result": None,
    "roadmap_result": None,
    "questions": [],
    "answers": [],
    "current_question": 0,
    "interview_started": False,
    "interview_finished": False,
    "interview_result": None
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

.main-title {
    font-size: 42px;
    font-weight: 800;
}

.subtitle {
    font-size: 18px;
    opacity: 0.7;
}

.card {
    padding: 20px;
    border-radius: 15px;
    border: 1px solid #dddddd;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# BASIC FUNCTIONS
# ============================================================

def clean_text(text):

    text = re.sub(r"\s+", " ", text or "")

    return text.strip()


def extract_pdf_text(file_bytes):

    reader = PdfReader(io.BytesIO(file_bytes))

    pages = []

    for page in reader.pages:

        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        pages.append(text)

    return clean_text("\n".join(pages))


# ============================================================
# OPENROUTER API
# ============================================================

def call_ai(
    messages,
    temperature=0.2,
    max_tokens=2000
):

    if (
        not OPENROUTER_API_KEY
        or OPENROUTER_API_KEY
        == "PASTE_YOUR_OPENROUTER_API_KEY_HERE"
    ):

        raise ValueError(
            "Please enter your OpenRouter API key "
            "at the top of app.py."
        )

    headers = {

        "Authorization":
            f"Bearer {OPENROUTER_API_KEY}",

        "Content-Type":
            "application/json",

        "HTTP-Referer":
            "http://localhost:8501",

        "X-Title":
            "InterviewIQ AI"
    }

    payload = {

        "model":
            OPENROUTER_MODEL,

        "messages":
            messages,

        "temperature":
            temperature,

        "max_tokens":
            max_tokens
    }

    response = requests.post(

        OPENROUTER_URL,

        headers=headers,

        json=payload,

        timeout=120
    )

    if response.status_code != 200:

        try:
            error = response.json()
        except Exception:
            error = response.text

        raise RuntimeError(
            f"OpenRouter Error {response.status_code}: {error}"
        )

    data = response.json()

    return data["choices"][0]["message"]["content"]


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(text):

    text = text.strip()

    # Remove markdown code fences
    text = re.sub(
        r"^```json",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```",
        "",
        text
    )

    text = re.sub(
        r"```$",
        "",
        text
    )

    text = text.strip()

    try:

        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # Try extracting JSON object
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1:

        try:

            return json.loads(
                text[start:end + 1]
            )

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "AI returned an invalid JSON response."
    )


def score(value):

    try:

        return max(
            0,
            min(
                100,
                int(float(value))
            )
        )

    except Exception:

        return 0


# ============================================================
# ATS ANALYSIS
# ============================================================

def ats_analysis(resume, job_description):

    system_prompt = """

You are an expert ATS recruitment analyst.

Compare the candidate resume with the job description.

Return ONLY valid JSON.

Format:

{
    "ats_score": 0,
    "summary": "",
    "matched_skills": [],
    "missing_skills": [],
    "matched_keywords": [],
    "missing_keywords": [],
    "education_alignment": "",
    "experience_alignment": "",
    "improvements": []
}

Rules:

- ats_score must be between 0 and 100.
- Never invent candidate experience.
- Only identify skills explicitly supported by the resume.
- Clearly distinguish required skills from candidate skills.
"""

    user_prompt = f"""

CANDIDATE RESUME:

{resume[:18000]}


JOB DESCRIPTION:

{job_description[:12000]}

Analyze the candidate against this job.
"""

    result = call_ai(

        [
            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": user_prompt
            }
        ],

        temperature=0.1,
        max_tokens=2200
    )

    return extract_json(result)


# ============================================================
# SKILL GAP ANALYSIS
# ============================================================

def skill_gap_analysis(resume, job_description):

    system_prompt = """

You are an expert AI career advisor.

Analyze the candidate resume against the target job.

Return ONLY JSON.

Format:

{
    "overall_match": 0,
    "strong_skills": [],
    "technical_gaps": [],
    "soft_skill_gaps": [],
    "skills_to_develop": [
        {
            "skill": "",
            "priority": "High",
            "reason": ""
        }
    ],
    "recommended_projects": [],
    "next_steps": []
}

Do not invent skills or experience.
"""

    user_prompt = f"""

RESUME:

{resume[:18000]}


JOB DESCRIPTION:

{job_description[:12000]}
"""

    result = call_ai(

        [
            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": user_prompt
            }
        ],

        temperature=0.15,
        max_tokens=2400
    )

    return extract_json(result)


# ============================================================
# INTERVIEW QUESTIONS
# ============================================================

def generate_questions(
    resume,
    job_description,
    role,
    difficulty,
    number
):

    system_prompt = """

You are a senior technical interviewer.

Create a personalized mock interview.

Questions must be based on:

- Candidate resume
- Target job
- Candidate projects
- Required skills

Return ONLY JSON.

Format:

{
    "questions": [
        {
            "question": "",
            "category": "",
            "difficulty": "",
            "what_interviewer_checks": ""
        }
    ]
}

Categories can be:

Technical
Project
Behavioral
HR
Scenario
"""

    user_prompt = f"""

TARGET ROLE:

{role}


DIFFICULTY:

{difficulty}


NUMBER OF QUESTIONS:

{number}


RESUME:

{resume[:16000]}


JOB DESCRIPTION:

{job_description[:10000]}
"""

    result = call_ai(

        [
            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": user_prompt
            }
        ],

        temperature=0.35,
        max_tokens=2600
    )

    data = extract_json(result)

    return data.get("questions", [])[:number]


# ============================================================
# INTERVIEW EVALUATION
# ============================================================

def evaluate_interview(
    resume,
    role,
    questions,
    answers
):

    interview_data = []

    for i in range(len(questions)):

        interview_data.append({

            "question_number":
                i + 1,

            "question":
                questions[i].get(
                    "question",
                    ""
                ),

            "category":
                questions[i].get(
                    "category",
                    ""
                ),

            "answer":
                answers[i]

        })

    system_prompt = """

You are a senior interviewer.

Evaluate the candidate's mock interview.

Return ONLY JSON.

Format:

{
    "overall_score": 0,
    "technical_score": 0,
    "communication_score": 0,
    "relevance_score": 0,

    "strengths": [],

    "weaknesses": [],

    "question_feedback": [
        {
            "question_number": 1,
            "score": 0,
            "feedback": "",
            "better_answer_points": []
        }
    ],

    "final_feedback": "",

    "next_practice_topics": []
}

All scores must be 0-100.
"""

    user_prompt = f"""

TARGET ROLE:

{role}


RESUME:

{resume[:14000]}


INTERVIEW:

{json.dumps(
    interview_data,
    indent=2
)}
"""

    result = call_ai(

        [
            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": user_prompt
            }
        ],

        temperature=0.15,
        max_tokens=3000
    )

    return extract_json(result)


# ============================================================
# PERSONALIZED PREPARATION
# ============================================================

def preparation_plan(
    resume,
    job_description,
    skill_result
):

    system_prompt = """

You are an expert placement coach.

Create a personalized four-week preparation plan.

Return ONLY JSON.

Format:

{
    "target_role": "",
    "profile_summary": "",

    "week_1": [],
    "week_2": [],
    "week_3": [],
    "week_4": [],

    "daily_routine": [],
    "interview_focus": [],
    "project_suggestions": [],
    "final_checklist": []
}
"""

    user_prompt = f"""

RESUME:

{resume[:15000]}


JOB DESCRIPTION:

{job_description[:10000]}


SKILL GAP:

{json.dumps(
    skill_result,
    indent=2
)}
"""

    result = call_ai(

        [
            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": user_prompt
            }
        ],

        temperature=0.25,
        max_tokens=2800
    )

    return extract_json(result)


# ============================================================
# RESET INTERVIEW
# ============================================================

def reset_interview():

    st.session_state.questions = []

    st.session_state.answers = []

    st.session_state.current_question = 0

    st.session_state.interview_started = False

    st.session_state.interview_finished = False

    st.session_state.interview_result = None


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🎯 InterviewIQ AI")

    st.caption(
        "AI Interview & Placement Intelligence Platform"
    )

    st.divider()

    st.subheader("📄 Upload Resume")

    resume_file = st.file_uploader(

        "Upload PDF resume",

        type=["pdf"]
    )

    if resume_file:

        try:

            st.session_state.resume_text = (
                extract_pdf_text(
                    resume_file.getvalue()
                )
            )

            st.session_state.resume_name = (
                resume_file.name
            )

            st.success(
                "Resume uploaded successfully!"
            )

        except Exception as e:

            st.error(
                f"Resume error: {e}"
            )

    st.subheader("💼 Target Job")

    st.session_state.job_description = (
        st.text_area(

            "Paste Job Description",

            height=250,

            placeholder=(
                "Paste the complete job description..."
            )
        )
    )

    st.divider()

    if st.button(
        "🗑️ Reset Application",
        use_container_width=True
    ):

        for key, value in DEFAULTS.items():

            st.session_state[key] = value

        st.rerun()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">'
    '🎯 InterviewIQ AI'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'AI Interview & Placement Intelligence Platform'
    '</div>',
    unsafe_allow_html=True
)

st.write(
    "Analyze your resume, compare it with a job, "
    "identify skill gaps, conduct personalized mock "
    "interviews, and generate a preparation roadmap."
)


# ============================================================
# DASHBOARD
# ============================================================

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(

        "Resume",

        "Ready"
        if st.session_state.resume_text
        else "Missing"
    )

with col2:

    st.metric(

        "Job Description",

        "Ready"
        if st.session_state.job_description.strip()
        else "Missing"
    )

with col3:

    st.metric(

        "Interview Questions",

        len(
            st.session_state.questions
        )
    )

with col4:

    if st.session_state.ats_result:

        st.metric(

            "ATS Score",

            f"{score(st.session_state.ats_result.get('ats_score'))}/100"
        )

    else:

        st.metric(
            "ATS Score",
            "--"
        )


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📄 ATS Analysis",
        "🧩 Skill Gap",
        "🎤 Mock Interview",
        "📚 Preparation"
    ]
)


# ============================================================
# VALIDATION
# ============================================================

def profile_ready():

    if not st.session_state.resume_text:

        st.warning(
            "Please upload your resume PDF."
        )

        return False

    if not st.session_state.job_description.strip():

        st.warning(
            "Please paste a job description."
        )

        return False

    return True


# ============================================================
# TAB 1 — ATS
# ============================================================

with tab1:

    st.header(
        "📄 ATS Resume Analysis"
    )

    st.write(
        "Check how well your resume matches "
        "the selected job description."
    )

    if st.button(
        "🔍 Run ATS Analysis",
        use_container_width=True
    ):

        if profile_ready():

            with st.spinner(
                "Analyzing resume..."
            ):

                try:

                    st.session_state.ats_result = (
                        ats_analysis(

                            st.session_state.resume_text,

                            st.session_state.job_description
                        )
                    )

                    st.success(
                        "ATS analysis completed!"
                    )

                except Exception as e:

                    st.error(
                        f"ATS analysis failed: {e}"
                    )

    result = st.session_state.ats_result

    if result:

        ats_score = score(
            result.get(
                "ats_score"
            )
        )

        st.subheader(
            f"ATS Match Score: {ats_score}/100"
        )

        st.progress(
            ats_score / 100
        )

        st.info(
            result.get(
                "summary",
                ""
            )
        )

        col1, col2 = st.columns(2)

        with col1:

            st.subheader(
                "✅ Matched Skills"
            )

            for item in result.get(
                "matched_skills",
                []
            ):

                st.markdown(
                    f"- {item}"
                )

        with col2:

            st.subheader(
                "⚠️ Missing Skills"
            )

            for item in result.get(
                "missing_skills",
                []
            ):

                st.markdown(
                    f"- {item}"
                )

        col1, col2 = st.columns(2)

        with col1:

            st.subheader(
                "🔑 Matched Keywords"
            )

            for item in result.get(
                "matched_keywords",
                []
            ):

                st.markdown(
                    f"- {item}"
                )

        with col2:

            st.subheader(
                "🔑 Missing Keywords"
            )

            for item in result.get(
                "missing_keywords",
                []
            ):

                st.markdown(
                    f"- {item}"
                )

        st.subheader(
            "🎓 Education Alignment"
        )

        st.write(
            result.get(
                "education_alignment",
                ""
            )
        )

        st.subheader(
            "💼 Experience Alignment"
        )

        st.write(
            result.get(
                "experience_alignment",
                ""
            )
        )

        st.subheader(
            "🚀 Resume Improvements"
        )

        for item in result.get(
            "improvements",
            []
        ):

            st.markdown(
                f"- {item}"
            )


# ============================================================
# TAB 2 — SKILL GAP
# ============================================================

with tab2:

    st.header(
        "🧩 Skill Gap Analysis"
    )

    st.write(
        "Identify the skills you already have and "
        "the skills required for your target role."
    )

    if st.button(
        "🧠 Analyze Skill Gap",
        use_container_width=True
    ):

        if profile_ready():

            with st.spinner(
                "Analyzing your skills..."
            ):

                try:

                    st.session_state.skill_result = (
                        skill_gap_analysis(

                            st.session_state.resume_text,

                            st.session_state.job_description
                        )
                    )

                    st.success(
                        "Skill-gap analysis completed!"
                    )

                except Exception as e:

                    st.error(
                        f"Skill analysis failed: {e}"
                    )

    result = st.session_state.skill_result

    if result:

        match = score(
            result.get(
                "overall_match"
            )
        )

        st.subheader(
            f"Overall Role Match: {match}/100"
        )

        st.progress(
            match / 100
        )

        st.subheader(
            "💪 Your Strong Skills"
        )

        for item in result.get(
            "strong_skills",
            []
        ):

            st.markdown(
                f"- {item}"
            )

        st.subheader(
            "📈 Skills To Develop"
        )

        gaps = result.get(
            "skills_to_develop",
            []
        )

        if gaps:

            df = pd.DataFrame(
                gaps
            )

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

        st.subheader(
            "💻 Technical Gaps"
        )

        for item in result.get(
            "technical_gaps",
            []
        ):

            st.markdown(
                f"- {item}"
            )

        st.subheader(
            "🤝 Soft Skill Gaps"
        )

        for item in result.get(
            "soft_skill_gaps",
            []
        ):

            st.markdown(
                f"- {item}"
            )

        st.subheader(
            "💡 Recommended Projects"
        )

        for item in result.get(
            "recommended_projects",
            []
        ):

            st.markdown(
                f"- {item}"
            )

        st.subheader(
            "➡️ Next Steps"
        )

        for item in result.get(
            "next_steps",
            []
        ):

            st.markdown(
                f"- {item}"
            )


# ============================================================
# TAB 3 — MOCK INTERVIEW
# ============================================================

with tab3:

    st.header(
        "🎤 AI Mock Interview"
    )

    if not profile_ready():

        st.info(
            "Upload your resume and paste a job "
            "description to start."
        )

    else:

        col1, col2, col3 = st.columns(3)

        with col1:

            role = st.text_input(
                "Target Role",
                value="AI / ML Engineer"
            )

        with col2:

            difficulty = st.selectbox(
                "Difficulty",
                [
                    "Easy",
                    "Medium",
                    "Hard"
                ]
            )

        with col3:

            number = st.selectbox(
                "Number of Questions",
                [
                    5,
                    7,
                    10
                ]
            )

        if not st.session_state.interview_started:

            if st.button(
                "🎤 Start AI Interview",
                use_container_width=True
            ):

                with st.spinner(
                    "Preparing personalized interview..."
                ):

                    try:

                        questions = generate_questions(

                            st.session_state.resume_text,

                            st.session_state.job_description,

                            role,

                            difficulty,

                            number
                        )

                        if not questions:

                            raise ValueError(
                                "No questions were generated."
                            )

                        st.session_state.questions = (
                            questions
                        )

                        st.session_state.answers = []

                        st.session_state.current_question = 0

                        st.session_state.interview_started = True

                        st.session_state.interview_finished = False

                        st.rerun()

                    except Exception as e:

                        st.error(
                            f"Interview generation failed: {e}"
                        )

        # ----------------------------------------------------
        # ACTIVE INTERVIEW
        # ----------------------------------------------------

        if (
            st.session_state.interview_started
            and not st.session_state.interview_finished
        ):

            current = (
                st.session_state.current_question
            )

            questions = (
                st.session_state.questions
            )

            question = questions[current]

            st.progress(
                (current + 1)
                / len(questions)
            )

            st.caption(
                f"Question {current + 1} "
                f"of {len(questions)}"
            )

            st.subheader(
                question.get(
                    "question",
                    ""
                )
            )

            st.info(
                "Category: "
                + question.get(
                    "category",
                    "General"
                )
                + " | Difficulty: "
                + question.get(
                    "difficulty",
                    "Medium"
                )
            )

            answer = st.text_area(
                "Your Answer",
                height=200,
                key=f"answer_{current}",
                placeholder=(
                    "Type your answer as if "
                    "you are speaking to the interviewer..."
                )
            )

            if st.button(
                "➡️ Submit Answer",
                use_container_width=True
            ):

                if not answer.strip():

                    st.warning(
                        "Please enter your answer."
                    )

                else:

                    st.session_state.answers.append(
                        answer.strip()
                    )

                    st.session_state.current_question += 1

                    if (
                        st.session_state.current_question
                        >= len(questions)
                    ):

                        st.session_state.interview_finished = True

                    st.rerun()

        # ----------------------------------------------------
        # EVALUATION
        # ----------------------------------------------------

        if (
            st.session_state.interview_finished
            and not st.session_state.interview_result
        ):

            st.success(
                "🎉 Interview completed!"
            )

            if st.button(
                "📊 Evaluate My Interview",
                use_container_width=True
            ):

                with st.spinner(
                    "AI is evaluating your answers..."
                ):

                    try:

                        st.session_state.interview_result = (
                            evaluate_interview(

                                st.session_state.resume_text,

                                role,

                                st.session_state.questions,

                                st.session_state.answers
                            )
                        )

                        st.rerun()

                    except Exception as e:

                        st.error(
                            f"Evaluation failed: {e}"
                        )

        # ----------------------------------------------------
        # RESULTS
        # ----------------------------------------------------

        if st.session_state.interview_result:

            result = (
                st.session_state.interview_result
            )

            st.divider()

            st.subheader(
                "📊 Interview Performance"
            )

            c1, c2, c3, c4 = st.columns(4)

            with c1:

                st.metric(
                    "Overall",
                    f"{score(result.get('overall_score'))}/100"
                )

            with c2:

                st.metric(
                    "Technical",
                    f"{score(result.get('technical_score'))}/100"
                )

            with c3:

                st.metric(
                    "Communication",
                    f"{score(result.get('communication_score'))}/100"
                )

            with c4:

                st.metric(
                    "Relevance",
                    f"{score(result.get('relevance_score'))}/100"
                )

            st.subheader(
                "💪 Strengths"
            )

            for item in result.get(
                "strengths",
                []
            ):

                st.markdown(
                    f"- {item}"
                )

            st.subheader(
                "⚠️ Areas To Improve"
            )

            for item in result.get(
                "weaknesses",
                []
            ):

                st.markdown(
                    f"- {item}"
                )

            st.subheader(
                "📝 Question Feedback"
            )

            for item in result.get(
                "question_feedback",
                []
            ):

                with st.expander(
                    f"Question "
                    f"{item.get('question_number')} "
                    f"— "
                    f"{score(item.get('score'))}/100"
                ):

                    st.write(
                        item.get(
                            "feedback",
                            ""
                        )
                    )

                    st.markdown(
                        "**Better answer points:**"
                    )

                    for point in item.get(
                        "better_answer_points",
                        []
                    ):

                        st.markdown(
                            f"- {point}"
                        )

            st.subheader(
                "🎯 Final Feedback"
            )

            st.write(
                result.get(
                    "final_feedback",
                    ""
                )
            )

            st.subheader(
                "📚 Next Practice Topics"
            )

            for item in result.get(
                "next_practice_topics",
                []
            ):

                st.markdown(
                    f"- {item}"
                )

            if st.button(
                "🔄 Start New Interview",
                use_container_width=True
            ):

                reset_interview()

                st.rerun()


# ============================================================
# TAB 4 — PREPARATION
# ============================================================

with tab4:

    st.header(
        "📚 Personalized Preparation"
    )

    st.write(
        "Generate a four-week preparation roadmap "
        "based on your resume and target job."
    )

    if st.button(
        "🗺️ Generate Preparation Plan",
        use_container_width=True
    ):

        if profile_ready():

            try:

                # Automatically generate skill analysis
                # if the user hasn't done it yet.

                if not st.session_state.skill_result:

                    with st.spinner(
                        "Analyzing skill gaps..."
                    ):

                        st.session_state.skill_result = (
                            skill_gap_analysis(

                                st.session_state.resume_text,

                                st.session_state.job_description
                            )
                        )

                with st.spinner(
                    "Creating your personalized roadmap..."
                ):

                    st.session_state.roadmap_result = (
                        preparation_plan(

                            st.session_state.resume_text,

                            st.session_state.job_description,

                            st.session_state.skill_result
                        )
                    )

                st.success(
                    "Preparation plan created!"
                )

            except Exception as e:

                st.error(
                    f"Preparation plan failed: {e}"
                )

    plan = (
        st.session_state.roadmap_result
    )

    if plan:

        st.subheader(
            "🎯 Target Role"
        )

        st.write(
            plan.get(
                "target_role",
                ""
            )
        )

        st.subheader(
            "👤 Profile Summary"
        )

        st.write(
            plan.get(
                "profile_summary",
                ""
            )
        )

        weeks = [
            ("week_1", "📅 Week 1"),
            ("week_2", "📅 Week 2"),
            ("week_3", "📅 Week 3"),
            ("week_4", "📅 Week 4")
        ]

        for key, title in weeks:

            st.subheader(
                title
            )

            for item in plan.get(
                key,
                []
            ):

                st.markdown(
                    f"- {item}"
                )

        st.subheader(
            "⏰ Daily Routine"
        )

        for item in plan.get(
            "daily_routine",
            []
        ):

            st.markdown(
                f"- {item}"
            )

        st.subheader(
            "🎤 Interview Focus"
        )

        for item in plan.get(
            "interview_focus",
            []
        ):

            st.markdown(
                f"- {item}"
            )

        st.subheader(
            "💻 Recommended Projects"
        )

        for item in plan.get(
            "project_suggestions",
            []
        ):

            st.markdown(
                f"- {item}"
            )

        st.subheader(
            "✅ Final Checklist"
        )

        for item in plan.get(
            "final_checklist",
            []
        ):

            st.markdown(
                f"- {item}"
            )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "InterviewIQ AI | Python + Streamlit + OpenRouter | "
    "AI-powered placement preparation"
)
