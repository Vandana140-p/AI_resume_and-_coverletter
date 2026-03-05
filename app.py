import streamlit as st
from groq import Groq
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.colors import HexColor
from datetime import datetime
import tempfile
import os
import re

# ==============================
# Initialize Groq Client
# ==============================
@st.cache_resource
def init_client():
    api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("🚫 Groq API key not found. Please set it in secrets or environment.")
        st.stop()
    return Groq(api_key=api_key)

client = init_client()

# ==============================
# Text Generation Function (Strict)
# ==============================
def generate_text(prompt):
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a professional resume and cover letter writer. Use ONLY the information provided in the prompt. Do NOT invent any details. If a field is missing, use the exact placeholder shown (e.g., [Company Name]). For cover letters, use plain text only – do NOT use any markdown symbols like # or ##. For emphasis, you may use **bold** sparingly. Do NOT include any standalone titles like 'Resume Summary' – start directly with the ## heading for resumes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800,
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"❌ API call failed: {e}")
        return ""

# ==============================
# Custom Canvas to draw border
# ==============================
def border_canvas(canv, doc):
    canv.saveState()
    canv.setStrokeColor(HexColor('#0A4D8C'))
    canv.setLineWidth(3)
    w, h = doc.pagesize
    margin = 20
    canv.rect(margin, margin, w - 2*margin, h - 2*margin, stroke=1, fill=0)
    canv.setStrokeColor(HexColor('#5F9EA0'))
    canv.setLineWidth(1)
    canv.rect(margin+3, margin+3, w - 2*margin -6, h - 2*margin -6, stroke=1, fill=0)
    canv.restoreState()

# ==============================
# Helper to clean AI output (remove stray markdown)
# ==============================
def clean_ai_output(text, doc_type):
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('#') and doc_type == "Cover Letter":
            line = re.sub(r'^#+\s*', '', line)
        cleaned.append(line)
    return '\n'.join(cleaned)

# ==============================
# PDF Generator – Name & Contact Separate (Address excluded for resume)
# ==============================
def create_professional_pdf(content, name, job_role, doc_type, phone="", email="", address=""):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    
    doc = SimpleDocTemplate(
        temp_file.name,
        pagesize=A4,
        rightMargin=90,
        leftMargin=90,
        topMargin=90,
        bottomMargin=90,
    )
    elements = []

    styles = getSampleStyleSheet()
    
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
        spaceBefore=18,
        spaceAfter=8,
        textColor=HexColor('#1E3A8A'),
        fontName='Helvetica-Bold',
    )
    normal_style = ParagraphStyle(
        'NormalJustified',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        textColor=HexColor('#2D3748'),
    )
    bullet_style = ParagraphStyle(
        'BulletPoint',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        leftIndent=20,
        firstLineIndent=-10,
        spaceAfter=6,
        bulletFontName='Helvetica',
        bulletFontSize=11,
        textColor=HexColor('#2D3748'),
    )

    # ===== RESUME SUMMARY =====
    if doc_type == "Resume Summary":
        # Name style – large, blue, centered
        name_style = ParagraphStyle(
            'NameHeader',
            parent=styles['Heading1'],
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=4,
            textColor=HexColor('#0A4D8C'),
            fontName='Helvetica-Bold',
        )
        # Contact style – smaller, lighter blue, centered (only phone & email)
        contact_style = ParagraphStyle(
            'ContactHeader',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            textColor=HexColor('#2C5282'),
            spaceAfter=8,
        )
        elements.append(Paragraph(name, name_style))
        contact_parts = []
        if phone:
            contact_parts.append(phone)
        if email:
            contact_parts.append(email)
        # Address is deliberately excluded from resume header
        if contact_parts:
            elements.append(Paragraph(" | ".join(contact_parts), contact_style))
        elements.append(Spacer(1, 0.05 * inch))

    # ===== Process content (common) =====
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        raw_line = lines[i].strip()
        if not raw_line:
            elements.append(Spacer(1, 0.05 * inch))
            i += 1
            continue

        # Remove any stray "Resume Summary" line (for resume only)
        if doc_type == "Resume Summary" and re.match(r'^resume\s+summary$', raw_line, re.IGNORECASE):
            i += 1
            continue

        # Headings (only for resume)
        if doc_type == "Resume Summary" and raw_line.startswith('##'):
            heading_text = raw_line.lstrip('#').strip()
            elements.append(Paragraph(heading_text, heading_style))
            i += 1
            continue

        # All-caps headings (only for resume)
        if doc_type == "Resume Summary" and ((raw_line.isupper() and len(raw_line) > 3 and '**' not in raw_line) or raw_line.endswith(':')):
            clean = re.sub(r'^[-*]\s*', '', raw_line)
            clean = re.sub(r'\*+$', '', clean).strip()
            elements.append(Paragraph(clean, heading_style))
            i += 1
            continue

        # Bullet points (for both)
        bullet_match = re.match(r'^(\s*[-*•]|\s*\d+\.)\s+(.*)', raw_line)
        if bullet_match:
            bullet_text = bullet_match.group(2).strip()
            bullet_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', bullet_text)
            bullet_text = re.sub(r'\*(.*?)\*', r'<b>\1</b>', bullet_text)
            elements.append(Paragraph(f"• {bullet_text}", bullet_style))
            i += 1
            continue

        # Regular paragraph with inline bold
        para_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', raw_line)
        para_text = re.sub(r'\*(.*?)\*', r'<b>\1</b>', para_text)
        elements.append(Paragraph(para_text, normal_style))
        i += 1

    doc.build(elements, onFirstPage=border_canvas, onLaterPages=border_canvas)
    return temp_file.name

# ==============================
# Streamlit UI – Full Width Glass
# ==============================
st.set_page_config(page_title="AI Resume Generator", page_icon="✨", layout="wide")

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(145deg, #0f172a 0%, #1e293b 100%);
        padding: 1.5rem;
    }
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 32px;
        padding: 2.5rem;
        width: 100%;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.1) inset;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .big-title {
        font-size: 3.2rem;
        font-weight: 800;
        text-align: center;
        background: linear-gradient(135deg, #94a3b8, #cbd5e1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        text-shadow: 0 0 30px rgba(148, 163, 184, 0.3);
        letter-spacing: -0.5px;
    }
    .subtitle {
        text-align: center;
        font-size: 1.2rem;
        color: #94a3b8;
        margin-bottom: 2.5rem;
        font-weight: 400;
        letter-spacing: 0.3px;
    }
    .section-header {
        font-size: 1.4rem;
        font-weight: 600;
        color: #e2e8f0;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #3b82f6;
        display: inline-block;
        text-shadow: 0 2px 5px rgba(0,0,0,0.5);
    }
    .stTextInput label, .stTextArea label, .stSelectbox label, .stRadio label {
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        color: #cbd5e1 !important;
        margin-bottom: 0.2rem !important;
    }
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        background: rgba(15, 23, 42, 0.6) !important;
        color: #f1f5f9 !important;
        border-radius: 16px !important;
        border: 1px solid rgba(59, 130, 246, 0.3) !important;
        backdrop-filter: blur(4px) !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 6px -2px rgba(0, 0, 0, 0.3) !important;
    }
    .stButton button {
        background: linear-gradient(145deg, #2563eb, #1e40af) !important;
        color: white !important;
        font-size: 1.2rem !important;
        font-weight: 600 !important;
        padding: 0.8rem 2.5rem !important;
        border-radius: 40px !important;
        border: none !important;
        box-shadow: 0 10px 25px -5px #1e3a8a80, 0 0 0 1px #60a5fa inset !important;
    }
    .stDownload button {
        background: linear-gradient(145deg, #7c3aed, #5b21b6) !important;
    }
    hr {
        margin: 2rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="glass-card">', unsafe_allow_html=True)

st.markdown('<div class="big-title">✨ AI Resume & Cover Letter Generator</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Glass Edition • Groq API • No Hallucinations</div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["👤 Personal & Company", "📄 Resume Content", "⚙️ Generate"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name", placeholder="e.g., John Doe")
        phone = st.text_input("Phone Number", placeholder="e.g., +1 234 567 890")
        address = st.text_input("Your Address", placeholder="e.g., 123 Main St, City, Country")
    with col2:
        job_role = st.text_input("Target Job Role", placeholder="e.g., Software Engineer")
        email = st.text_input("Email Address", placeholder="e.g., john.doe@example.com")
    
    st.markdown("---")
    st.markdown('<div class="section-header">🏢 Target Company</div>', unsafe_allow_html=True)
    col3, col4 = st.columns(2)
    with col3:
        company_name = st.text_input("Company Name", placeholder="e.g., Acme Corp")
        recipient_name = st.text_input("Recipient Name", placeholder="e.g., Jane Smith")
    with col4:
        recipient_address = st.text_input("Recipient Address", placeholder="e.g., 456 Business Rd, City")
        recipient_title = st.selectbox("Recipient Title", ["Mr.", "Ms.", "Mrs.", "Dr.", "Prof."])

with tab2:
    st.markdown('<div class="section-header">📄 Your Information</div>', unsafe_allow_html=True)
    skills = st.text_area("Skills (comma separated)", placeholder="e.g., Python, Project Management, Data Analysis", height=80)
    projects = st.text_area("Projects (describe briefly)", placeholder="e.g., Developed a mobile app for task management using Flutter", height=100)
    education = st.text_area("Education", placeholder="e.g., B.Sc. Computer Science, University of Technology, 2025, GPA 3.8", height=80)
    internships = st.text_area("Internships", placeholder="e.g., Software Intern at Tech Solutions Inc. – worked on backend APIs", height=80)

with tab3:
    st.markdown('<div class="section-header">⚙️ Generation Settings</div>', unsafe_allow_html=True)
    col7, col8 = st.columns(2)
    with col7:
        tone = st.selectbox("Select Tone", ["Professional", "Confident", "Formal", "Creative"])
    with col8:
        generate_type = st.radio("Generate", ["Resume Summary", "Cover Letter"], horizontal=True)
    
    st.divider()
    
    if st.button("🚀 Generate Content", use_container_width=True):
        if not name or not job_role:
            st.error("Please fill at least Name and Job Role.")
        else:
            if generate_type == "Resume Summary":
                tone_instructions = {
                    "Professional": "Use a polished, achievement‑focused tone. Highlight results and skills clearly.",
                    "Confident": "Use assertive language. Emphasize strengths and unique value with confidence.",
                    "Formal": "Use traditional, respectful business language. Maintain a formal structure.",
                    "Creative": "Use engaging, slightly unconventional language. Show personality while staying professional."
                }
                prompt = f"""
You are writing a concise resume summary for {name}. Use ONLY the information below. Keep it short (under 150 words). Do NOT add any fictional details.

Name: {name}
Target Role: {job_role}

Education:
{education if education.strip() else "No education information provided."}

Skills:
{skills if skills.strip() else "No skills provided."}

Projects:
{projects if projects.strip() else "No projects provided."}

Internships:
{internships if internships.strip() else "No internships provided."}

Tone: {tone}.
Tone instruction: {tone_instructions[tone]}

Format the summary using markdown:
- Start directly with a "## Profile Summary" heading (do NOT include any separate title like "Resume Summary").
- Then write a brief summary paragraph using the provided details.
- Then include sections for Education, Skills, Projects, Internships using ## headings.
- Use bullet points (-) for listing multiple items.
- Use **bold** for institutions or company names.

Output only the markdown content, no extra commentary.
"""
            else:
                tone_instructions = {
                    "Professional": "Use a polished, enthusiastic tone. Focus on how your skills match the role.",
                    "Confident": "Use assertive, self‑assured language. Emphasize your qualifications and eagerness.",
                    "Formal": "Use traditional, respectful business language. Keep the structure formal.",
                    "Creative": "Use engaging, slightly unique language. Show personality while maintaining professionalism."
                }
                prompt = f"""
You are writing a professional cover letter for {name} applying for the {job_role} position at {company_name if company_name.strip() else "[Company Name]"}. Use ONLY the information provided below. Follow the EXACT format shown.

SENDER INFORMATION (use exactly as given):
{name}
{address if address.strip() else "[Your Address]"}
{phone if phone.strip() else "[Your Phone Number]"}
{email if email.strip() else "[Your Email Address]"}

RECIPIENT INFORMATION:
{recipient_name if recipient_name.strip() else "[Recipient Name]"}
{recipient_address if recipient_address.strip() else "[Recipient Address]"}

COMPANY: {company_name if company_name.strip() else "[Company Name]"}

EDUCATION:
{education if education.strip() else "No education information provided."}

SKILLS:
{skills if skills.strip() else "No skills provided."}

PROJECTS:
{projects if projects.strip() else "No projects provided."}

INTERNSHIPS:
{internships if internships.strip() else "No internships provided."}

TONE: {tone}
Tone instruction: {tone_instructions[tone]}

Now write the cover letter in plain text only. Do NOT use any markdown symbols like # or ##. If you need to emphasize, use **bold** sparingly. Follow this structure exactly:

[Name]
[Address]
[Phone]
[Email]

[Recipient Name]
[Recipient Address]

Dear {recipient_title if recipient_title else "Mr./Ms."} [Recipient Last Name or "Hiring Manager"],

I am writing to express my strong interest in the {job_role} position at {company_name if company_name.strip() else "[Company Name]"}. [Write a brief opening paragraph expressing enthusiasm and mentioning your relevant background.]

[Second paragraph: Discuss your education and key skills relevant to the role. Use the provided education and skills. Be specific but concise.]

[Third paragraph: Highlight your projects and internship experiences. Use the provided projects and internships. Explain how they prepared you for this role.]

[Fourth paragraph: Explain why you are interested in {company_name if company_name.strip() else "[Company Name]"} and what you can contribute to the team.]

[Fifth paragraph: Closing paragraph. Reiterate your interest, mention your attached resume, and express your desire for an interview. Thank the reader for their time and consideration.]

Sincerely,
{name}

IMPORTANT:
- The sender block MUST have each piece of information on a separate line: Name, Address, Phone, Email.
- The recipient block also separate lines.
- Use the exact email and phone as provided.
- Do NOT use any markdown symbols like # or ##.
- Do NOT invent any details.
- If any field is empty, use the placeholder in brackets.
"""

            with st.spinner("Generating AI content with strict instructions..."):
                output = generate_text(prompt)

            if output:
                output = clean_ai_output(output, generate_type)

                st.success("✅ Content Generated Successfully!")
                st.subheader("📄 Generated Output")
                st.write(output)

                if generate_type == "Cover Letter":
                    lines = output.split('\n')
                    new_lines = []
                    date_inserted = False
                    for line in lines:
                        if not date_inserted and line.strip().startswith("Dear"):
                            new_lines.append(f"{datetime.today().strftime('%B %d, %Y')}\n")
                            new_lines.append(line)
                            date_inserted = True
                        else:
                            new_lines.append(line)
                    if not date_inserted:
                        new_lines.insert(0, f"{datetime.today().strftime('%B %d, %Y')}\n")
                    output = '\n'.join(new_lines)

                pdf_path = create_professional_pdf(output, name, job_role, generate_type, phone, email, address)
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="⬇ Download Professional PDF",
                        data=f,
                        file_name=f"{name.replace(' ', '_')}_{generate_type.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )
                os.unlink(pdf_path)

st.markdown('</div>', unsafe_allow_html=True)