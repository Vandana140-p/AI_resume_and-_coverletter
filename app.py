from datetime import datetime
import streamlit as st
from groq import Groq
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.colors import HexColor
import tempfile
import os
import re

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(
    page_title="AI Resume Generator",
    page_icon="✨",
    layout="wide"
)

# ==============================
# SESSION STATE
# ==============================
if "step" not in st.session_state:
    st.session_state.step = 1

fields = [
    "name",
    "phone",
    "address",
    "job_role",
    "email",
    "company_name",
    "recipient_name",
    "recipient_address",
    "skills",
    "projects",
    "education",
    "internships"
]

for field in fields:
    if field not in st.session_state:
        st.session_state[field] = ""

# ==============================
# CUSTOM CSS
# ==============================
st.markdown("""
<style>

.stApp {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: white;
}

.main-container {
    background: rgba(255,255,255,0.05);
    padding: 2rem;
    border-radius: 25px;
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 10px 40px rgba(0,0,0,0.4);
}

.big-title {
    font-size: 3rem;
    text-align: center;
    font-weight: bold;
    margin-bottom: 0.5rem;
    background: linear-gradient(90deg,#60a5fa,#c084fc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.subtitle {
    text-align:center;
    color:#cbd5e1;
    margin-bottom:2rem;
    font-size:1.1rem;
}

.section-title {
    font-size:1.5rem;
    font-weight:700;
    color:#e2e8f0;
    margin-top:1rem;
    margin-bottom:1rem;
}

.stTextInput input,
.stTextArea textarea,
.stSelectbox select {
    background: rgba(15,23,42,0.8) !important;
    color: white !important;
    border-radius: 14px !important;
    border: 1px solid #334155 !important;
}

.stButton button {
    background: linear-gradient(90deg,#2563eb,#7c3aed) !important;
    color: white !important;
    border: none !important;
    border-radius: 30px !important;
    padding: 0.8rem 1.5rem !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
}

.generate-box {
    background: linear-gradient(135deg,#2563eb,#7c3aed);
    padding:20px;
    border-radius:20px;
    text-align:center;
    color:white;
    margin-bottom:20px;
    font-size:1.2rem;
    font-weight:600;
}

</style>
""", unsafe_allow_html=True)

# ==============================
# GROQ CLIENT
# ==============================
@st.cache_resource
def init_client():

    api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")

    if not api_key:
        st.error("Groq API Key Missing")
        st.stop()

    return Groq(api_key=api_key)

client = init_client()

# ==============================
# REMOVE HALLUCINATIONS
# ==============================
def clean_output(text):

    hallucination_patterns = [
        r"\b\d+\+?\s+years? of experience\b",
        r"\bproven track record\b",
        r"\bhighly experienced\b",
        r"\bexpert professional\b",
        r"\bseasoned professional\b"
    ]

    for pattern in hallucination_patterns:
        text = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE
        )

    return text

# ==============================
# RESUME GENERATOR
# ==============================
def generate_text(prompt):

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": """
You are a professional resume writer.

STRICT RULES:
- Use ONLY user information
- Never hallucinate
- Never add fake experience
- Use headings:
## Profile Summary
## Skills
## Projects
## Education
## Internships
## Strengths
"""
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.4,
        max_tokens=1200
    )

    text = response.choices[0].message.content

    return clean_output(text)

# ==============================
# COVER LETTER GENERATOR
# ==============================
def generate_cover_letter():

    current_date = datetime.now().strftime("%d %B %Y")

    prompt = f"""
Write a SIMPLE and PROFESSIONAL cover letter.

IMPORTANT:
- Add today's date at the top:
{current_date}

Candidate Details:
Name: {st.session_state.name}
Phone: {st.session_state.phone}
Email: {st.session_state.email}
Address: {st.session_state.address}

Hiring Manager Details:
Hiring Manager Name: {st.session_state.recipient_name}
Company Name: {st.session_state.company_name}
Company Address: {st.session_state.recipient_address}

Target Role:
{st.session_state.job_role}

Skills:
{st.session_state.skills}

Projects:
{st.session_state.projects}

Education:
{st.session_state.education}

Internships:
{st.session_state.internships}

STRICT RULES:
- Simple professional format
- Add current date
- Greeting and closing required
- No bullet points
- No resume headings
- No fake experience
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": """
You are a professional cover letter writer.

FORMAT:
- Current Date
- Hiring Manager Info
- Greeting
- 2-3 paragraphs
- Closing
"""
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.5,
        max_tokens=700
    )

    text = response.choices[0].message.content

    return clean_output(text)

# ==============================
# PDF BORDER
# ==============================
def border_canvas(canv, doc):

    canv.saveState()

    canv.setStrokeColor(HexColor('#0A4D8C'))
    canv.setLineWidth(3)

    w, h = doc.pagesize
    margin = 20

    canv.rect(
        margin,
        margin,
        w - 2 * margin,
        h - 2 * margin,
        stroke=1,
        fill=0
    )

    canv.restoreState()

# ==============================
# PDF GENERATOR
# ==============================
def create_pdf(content, name, phone, email):

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf"
    )

    doc = SimpleDocTemplate(
        temp_file.name,
        pagesize=A4,
        rightMargin=80,
        leftMargin=80,
        topMargin=80,
        bottomMargin=80,
    )

    elements = []

    styles = getSampleStyleSheet()

    name_style = ParagraphStyle(
        'NameHeader',
        parent=styles['Heading1'],
        fontSize=22,
        leading=28,
        alignment=TA_CENTER,
        spaceAfter=6,
        textColor=HexColor('#0A4D8C'),
        fontName='Helvetica-Bold',
    )

    contact_style = ParagraphStyle(
        'ContactStyle',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_CENTER,
        textColor=HexColor('#4B5563'),
        spaceAfter=18,
    )

    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=16,
        leading=22,
        spaceBefore=18,
        spaceAfter=10,
        textColor=HexColor('#1D4ED8'),
        fontName='Helvetica-Bold',
        backColor=HexColor('#EFF6FF')
    )

    normal_style = ParagraphStyle(
        'NormalJustified',
        parent=styles['Normal'],
        fontSize=11,
        leading=18,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        textColor=HexColor('#1F2937'),
    )

    bullet_style = ParagraphStyle(
        'BulletPoint',
        parent=styles['Normal'],
        fontSize=11,
        leading=17,
        leftIndent=18,
        firstLineIndent=-8,
        spaceAfter=6,
        textColor=HexColor('#1F2937'),
    )

    # ==============================
    # HEADER
    # ==============================
    elements.append(
        Paragraph(name, name_style)
    )

    contact_text = f"""
    <b>Phone:</b> {phone}
    &nbsp;&nbsp;&nbsp;&nbsp;
    <b>Email:</b> {email}
    """

    elements.append(
        Paragraph(contact_text, contact_style)
    )

    elements.append(
        Spacer(1, 0.08 * inch)
    )

    # ==============================
    # CONTENT
    # ==============================
    lines = content.split('\n')

    for line in lines:

        line = line.strip()

        line = line.replace("*", "")

        if not line:
            elements.append(
                Spacer(1, 0.05 * inch)
            )
            continue

        # headings
        if (
            "Profile Summary" in line
            or "Skills" in line
            or "Projects" in line
            or "Education" in line
            or "Internships" in line
            or "Strengths" in line
        ):

            heading_text = (
                line.replace("##", "")
                .replace(":", "")
                .strip()
            )

            elements.append(
                Paragraph(
                    f"<b>{heading_text}</b>",
                    heading_style
                )
            )

            continue

        # bullets
        if (
            line.startswith("-")
            or line.startswith("•")
        ):

            bullet_text = (
                line.replace("-", "")
                .replace("•", "")
                .strip()
            )

            elements.append(
                Paragraph(
                    f"• {bullet_text}",
                    bullet_style
                )
            )

            continue

        elements.append(
            Paragraph(
                line,
                normal_style
            )
        )

    doc.build(
        elements,
        onFirstPage=border_canvas,
        onLaterPages=border_canvas
    )

    return temp_file.name

# ==============================
# MAIN UI
# ==============================
st.markdown('<div class="main-container">', unsafe_allow_html=True)

st.markdown(
    '<div class="big-title">✨ AI Resume Generator</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">Interactive Multi-Step Resume Builder</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="generate-box">
    🚀 Create Professional AI Resume & Cover Letters
    </div>
    """,
    unsafe_allow_html=True
)

progress = st.session_state.step / 3
st.progress(progress)

st.write(f"### Step {st.session_state.step} of 3")

# ==============================
# STEP 1
# ==============================
if st.session_state.step == 1:

    st.markdown(
        '<div class="section-title">👤 Personal Information</div>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    with col1:

        st.session_state.name = st.text_input("Full Name *")
        st.session_state.phone = st.text_input("Phone Number *")
        st.session_state.address = st.text_input("Address")

    with col2:

        st.session_state.job_role = st.text_input("Target Job Role *")
        st.session_state.email = st.text_input("Email *")

    st.markdown(
        '<div class="section-title">🏢 Hiring Manager Information</div>',
        unsafe_allow_html=True
    )

    col3, col4 = st.columns(2)

    with col3:

        st.session_state.recipient_name = st.text_input("Hiring Manager Name")
        st.session_state.company_name = st.text_input("Company Name")

    with col4:

        st.session_state.recipient_address = st.text_input("Company Address")

    if st.button("Next ➜"):

        st.session_state.step = 2
        st.rerun()

# ==============================
# STEP 2
# ==============================
elif st.session_state.step == 2:

    st.markdown(
        '<div class="section-title">📄 Resume Details</div>',
        unsafe_allow_html=True
    )

    st.session_state.skills = st.text_area("Skills")
    st.session_state.projects = st.text_area("Projects")
    st.session_state.education = st.text_area("Education")
    st.session_state.internships = st.text_area("Internships")

    col1, col2 = st.columns(2)

    with col1:

        if st.button("⬅ Back"):
            st.session_state.step = 1
            st.rerun()

    with col2:

        if st.button("Next ➜"):
            st.session_state.step = 3
            st.rerun()

# ==============================
# STEP 3
# ==============================
elif st.session_state.step == 3:

    st.markdown(
        '<div class="section-title">⚙️ Generate Resume & Cover Letter</div>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    with col1:
        generate_resume = st.checkbox(
            "Generate Resume",
            value=True
        )

    with col2:
        generate_cover = st.checkbox(
            "Generate Cover Letter",
            value=True
        )

    if st.button("🚀 Generate Documents"):

        resume_prompt = f"""
Name: {st.session_state.name}

Role:
{st.session_state.job_role}

Skills:
{st.session_state.skills}

Projects:
{st.session_state.projects}

Education:
{st.session_state.education}

Internships:
{st.session_state.internships}
"""

        with st.spinner("Generating..."):

            if generate_resume:
                output = generate_text(
                    resume_prompt
                )

            if generate_cover:
                cover_letter = generate_cover_letter()

        st.success("✅ Generated Successfully!")

        # Resume
        if generate_resume:

            st.subheader("📄 Resume")

            st.write(output)

            pdf_path = create_pdf(
                output,
                st.session_state.name,
                st.session_state.phone,
                st.session_state.email
            )

            with open(pdf_path, "rb") as f:

                st.download_button(
                    "⬇ Download Resume PDF",
                    data=f,
                    file_name=f"{st.session_state.name}_Resume.pdf",
                    mime="application/pdf"
                )

        # Cover Letter
        if generate_cover:

            st.subheader("✉ Cover Letter")

            st.write(cover_letter)

            cover_pdf = create_pdf(
                cover_letter,
                st.session_state.name,
                st.session_state.phone,
                st.session_state.email
            )

            with open(cover_pdf, "rb") as f:

                st.download_button(
                    "⬇ Download Cover Letter PDF",
                    data=f,
                    file_name=f"{st.session_state.name}_CoverLetter.pdf",
                    mime="application/pdf"
                )

st.markdown("</div>", unsafe_allow_html=True)
