from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import shutil
import pdfplumber
import psycopg2
from skills import SKILL_ALIASES
from rapidfuzz import fuzz
import re
import os
from matcher import semantic_skill_match, experience_match,get_jd_requirement_sentences, chunk_text, full_context_match


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

conn = psycopg2.connect(
    host="localhost",
    database="devlens",
    user="postgres",
    password="Snigdha@2006"
)
cur = conn.cursor()


# shared clean text function
def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[•\-–—►▪●|]', ' ', text)
    text = re.sub(r'[^\w\s\+\#\.]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

#sections extraction
def extract_sections(text: str) -> dict:
    sections = {
        "skills": "",
        "experience": "",
        "projects": "",
        "education": "",
        "full": text
    }
    section_patterns = {
        "skills":     r'^(technical skills|skills|core competencies|technologies|tech stack)$',
        "experience": r'^(work experience|experience|employment history|professional experience)$',
        "projects":   r'^(projects|personal projects|key projects|academic projects)$',
        "education":  r'^(education|academic background|qualifications|academics)$'
    }
    lines = text.split('\n')
    current_section = None

    for line in lines:
        line_clean = line.strip().lower()
        matched_section = None
        for section, pattern in section_patterns.items():
            if re.search(pattern, line_clean):
                matched_section = section
                break
        if matched_section:
            current_section = matched_section
        elif current_section:
            sections[current_section] += line + "\n"

    return sections


# shared skill matching function along with rapidfuzz
def match_skills(text: str):
    matched = set()
    words = text.split()
    for canonical_skill, aliases in SKILL_ALIASES.items():
        found = False
        for alias in aliases:
            alias = alias.lower()
            pattern = rf'\b{re.escape(alias)}\b'

            # exact match
            if re.search(pattern, text):
                matched.add(canonical_skill)
                found = True
                break

            # fuzzy match
            for word in words:
                score = fuzz.ratio(alias, word)
                if score >= 90:
                    matched.add(canonical_skill)
                    found = True
                    break
            if found:
                break
    return list(matched)

#resume handling
@app.post("/upload-resume")
async def upload_file(file: UploadFile = File(...)):
    file_path = f"uploads/resumes/{file.filename}"
    os.makedirs("uploads/resumes", exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # extracting text
    extracted_text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:                        
                extracted_text += text + "\n"
    raw_text    = extracted_text   
    cleaned_text = clean_text(extracted_text)  

    cur.execute(
        """
        INSERT INTO resumes(user_id, filename, extracted_text,raw_text)
        VALUES (%s, %s, %s,%s)
        RETURNING id
        """,
        (1, file.filename, cleaned_text,raw_text)
    )
    resume_id = cur.fetchone()[0]

    matched_skills = match_skills(cleaned_text)  

    for skill in matched_skills:
        cur.execute(
            "INSERT INTO resume_skills(resume_id, skill) VALUES(%s, %s)",
            (resume_id, skill)
        )

    conn.commit()
    print("Matched Skills in Resume:", matched_skills)
    return {
        "resume id": resume_id,
        "filename": file.filename,
        "skills": matched_skills
    }

#jd handling
@app.post("/add-jd")
async def add_jd(
    title: str = Form(...),
    company: str = Form(...),
    file: UploadFile = File(...)
):
    file_path = f"uploads/jds/{file.filename}"
    os.makedirs("uploads/jds", exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # extracting text
    extracted_text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:                        
                extracted_text += text + "\n"
    raw_text    = extracted_text   
    cleaned_text = clean_text(extracted_text)  

    cur.execute(
        """
        INSERT INTO job_descriptions(title, company, jd_text,raw_jd_text)
        VALUES(%s, %s, %s,%s)
        RETURNING id
        """,
        (title, company, cleaned_text,raw_text)
    )
    jd_id = cur.fetchone()[0]

    matched_skills = match_skills(cleaned_text)  

    for skill in matched_skills:
        cur.execute(
            "INSERT INTO jd_skills(jd_id, skill) VALUES(%s, %s)",
            (jd_id, skill)
        )

    conn.commit()
    print("Matched Skills in JD:", matched_skills)
    return {
        "message": "JD stored successfully",
        "jd_id": jd_id,
        "skills": matched_skills
    }

#matching and scoring


@app.get("/match/{resume_id}/{jd_id}")
async def match_resume_jd(resume_id: int, jd_id: int):

    # ── fetch skill lists ─────────────────────────────────────────
    cur.execute("SELECT skill FROM resume_skills WHERE resume_id = %s", (resume_id,))
    resume_skills = {row[0] for row in cur.fetchall()}

    cur.execute("SELECT skill FROM jd_skills WHERE jd_id = %s", (jd_id,))
    jd_skills = {row[0] for row in cur.fetchall()}

    # ── layer 1: exact match ──────────────────────────────────────
    exact_matched = resume_skills & jd_skills
    extra_skills  = resume_skills - jd_skills
    exact_score   = round(len(exact_matched) / len(jd_skills) * 100, 2) if jd_skills else 0

    # ── fetch texts ───────────────────────────────────────────────
    cur.execute("SELECT extracted_text, raw_text FROM resumes WHERE id = %s", (resume_id,))
    row = cur.fetchone()
    resume_text, resume_raw = row[0], row[1]

    cur.execute("SELECT jd_text, raw_jd_text FROM job_descriptions WHERE id = %s", (jd_id,))
    row = cur.fetchone()
    jd_text, jd_raw = row[0], row[1]

    resume_sections = extract_sections(resume_raw.lower())
    jd_sections     = extract_sections(jd_raw.lower())

    # ── layer 2: semantic skill match ─────────────────────────────
    semantic_matches, unmatched_l2 = semantic_skill_match(
        resume_skills = list(resume_skills),
        jd_skills     = list(jd_skills),
        exact_matched = exact_matched,
    )
    semantic_score = round(len(semantic_matches) / len(jd_skills) * 100, 2) if jd_skills else 0

    # ── layer 3: experience & project matching ────────────────────
    exp_matches, unmatched_l3 = experience_match(
        resume_sections     = resume_sections,
        jd_sections         = jd_sections,
        unmatched_jd_skills = unmatched_l2,
    )


    print("exp_matches:", exp_matches)
    print("unmatched_l3:", unmatched_l3)


    exp_score = round(len(exp_matches) / len(jd_skills) * 100, 2) if jd_skills else 0

    # ── layer 4: entire resume matching ────────────────────
    ctx_matches, missing_skills = full_context_match(
        resume_sections     = resume_sections,
        jd_sections         = jd_sections,
        unmatched_jd_skills = unmatched_l3,
    )
    ctx_score = round(len(ctx_matches) / len(jd_skills) * 100, 2) if jd_skills else 0

    # ── combined score (L1 + L2 + L3 + L4) ───────────────────────────
    total_matched  = len(exact_matched) + len(semantic_matches) + len(exp_matches) + len(ctx_matches)
    combined_score = round(total_matched / len(jd_skills) * 100, 2) if jd_skills else 0

    return {
        "resume_id":          resume_id,
        "jd_id":              jd_id,
        "exact_matches":      list(exact_matched),
        "exact_score":        exact_score,
        "semantic_matches":   semantic_matches,
        "semantic_score":     semantic_score,
        "experience_matches": exp_matches,
        "experience_score":   exp_score,
        "context_matches":     ctx_matches,  
        "context_score":       ctx_score, 
        "combined_score":     combined_score,
        "missing_skills":     unmatched_l3,
        "extra_skills":       list(extra_skills),
        "jd_skill_count":     len(jd_skills),
        "total_matched":      total_matched

    }