from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import shutil
import pdfplumber
import psycopg2
from skills import SKILLS
import re

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


# shared skill matching function with word boundaries
def match_skills(text: str) -> list:
    matched = []
    for skill in SKILLS:
        pattern = r'\b' + re.escape(skill.lower()) + r'\b'
        if re.search(pattern, text):
            matched.append(skill)
    return list(set(matched))

#resume handling
@app.post("/upload-resume")
async def upload_file(file: UploadFile = File(...)):
    file_path = f"uploads/resumes/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # extracting text
    extracted_text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:                        
                extracted_text += text + "\n"

    cleaned_text = clean_text(extracted_text)  

    cur.execute(
        """
        INSERT INTO resumes(user_id, filename, extracted_text)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (1, file.filename, cleaned_text)
    )
    resume_id = cur.fetchone()[0]

    matched_skills = match_skills(cleaned_text)  

    for skill in matched_skills:
        cur.execute(
            "INSERT INTO resume_skills(resume_id, skill) VALUES(%s, %s)",
            (resume_id, skill)
        )

    conn.commit()
    return {
        "message": "File uploaded successfully",
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

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # extracting text
    extracted_text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:                        
                extracted_text += text + "\n"

    cleaned_text = clean_text(extracted_text)  

    cur.execute(
        """
        INSERT INTO job_descriptions(title, company, jd_text)
        VALUES(%s, %s, %s)
        RETURNING id
        """,
        (title, company, cleaned_text)
    )
    jd_id = cur.fetchone()[0]

    matched_skills = match_skills(cleaned_text)  

    for skill in matched_skills:
        cur.execute(
            "INSERT INTO jd_skills(jd_id, skill) VALUES(%s, %s)",
            (jd_id, skill)
        )

    conn.commit()
    return {
        "message": "JD stored successfully",
        "jd_id": jd_id,
        "skills": matched_skills
    }