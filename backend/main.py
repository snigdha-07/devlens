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
import json
from pydantic import BaseModel


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


#-- shared clean text function -----------
def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[•\-–—►▪●|]', ' ', text)
    text = re.sub(r'[^\w\s\+\#\.]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

#-- sections extraction ------------------
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


#-- shared skill matching function along with rapidfuzz -------------
def match_skills(text: str):
    matched = set()
    words = text.split()
    for canonical_skill, aliases in SKILL_ALIASES.items():
        found = False
        for alias in aliases:
            alias = alias.lower()
            pattern = rf'\b{re.escape(alias)}\b'

            #-- exact match --------------
            if re.search(pattern, text):
                matched.add(canonical_skill)
                found = True
                break

            #-- fuzzy match --------------
            for word in words:
                score = fuzz.ratio(alias, word)
                if score >= 90:
                    matched.add(canonical_skill)
                    found = True
                    break
            if found:
                break
    return list(matched)

# -- resume handling --------------------------------
@app.post("/upload-resume")
async def upload_file(file: UploadFile = File(...)):
    file_path = f"uploads/resumes/{file.filename}"
    os.makedirs("uploads/resumes", exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    #-- extracting text ------------------------------
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

#-- jd handling ----------------------------------------
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

    #-- extracting text ------------------------
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


class BatchMatchRequest(BaseModel):
    resume_id: int
    jd_ids: list[int]

#-- total shared matching logic -------------------------

async def run_match(resume_id: int, jd_id: int) -> dict:

    # fetch skill lists
    cur.execute("SELECT skill FROM resume_skills WHERE resume_id = %s", (resume_id,))
    resume_skills = {row[0] for row in cur.fetchall()}

    cur.execute("SELECT skill FROM jd_skills WHERE jd_id = %s", (jd_id,))
    jd_skills = {row[0] for row in cur.fetchall()}

    # layer 1
    exact_matched = resume_skills & jd_skills
    extra_skills  = resume_skills - jd_skills

    # fetch texts
    cur.execute("SELECT extracted_text, raw_text FROM resumes WHERE id = %s", (resume_id,))
    row = cur.fetchone()
    resume_text, resume_raw = row[0], row[1]

    cur.execute("SELECT jd_text, raw_jd_text FROM job_descriptions WHERE id = %s", (jd_id,))
    row = cur.fetchone()
    jd_text, jd_raw = row[0], row[1]

    resume_sections = extract_sections(resume_raw.lower())
    jd_sections     = extract_sections(jd_raw.lower())

    # layer 2
    semantic_matches, unmatched_l2 = semantic_skill_match(
        resume_skills = list(resume_skills),
        jd_skills     = list(jd_skills),
        exact_matched = exact_matched,
    )

    # layer 3
    exp_matches, unmatched_l3 = experience_match(
        resume_sections     = resume_sections,
        jd_sections         = jd_sections,
        unmatched_jd_skills = unmatched_l2,
    )

    # layer 4
    ctx_matches, missing_skills = full_context_match(
        resume_sections     = resume_sections,
        jd_sections         = jd_sections,
        unmatched_jd_skills = unmatched_l3,
    )

    # scoring
    total = len(jd_skills) or 1

    exact_score    = round(len(exact_matched)    / total * 100, 2)
    semantic_score = round(len(semantic_matches) / total * 100, 2)
    exp_score      = round(len(exp_matches)      / total * 100, 2)
    ctx_score      = round(len(ctx_matches)      / total * 100, 2)

    weighted_matched = (
        len(exact_matched)    * 1.00 +
        len(semantic_matches) * 0.90 +
        len(exp_matches)      * 0.80 +
        len(ctx_matches)      * 0.70
    )
    final_score    = round(weighted_matched / total * 100, 2)
    coverage_score = round(
        (len(exact_matched) + len(semantic_matches) +
         len(exp_matches)   + len(ctx_matches)) / total * 100, 2
    )
    total_matched = (
        len(exact_matched) + len(semantic_matches) +
        len(exp_matches)   + len(ctx_matches)
    )

    # store in DB
    try:
        cur.execute(
            """
            INSERT INTO match_results (
                resume_id, jd_id,
                final_score, coverage_score,
                exact_score, semantic_score, exp_score, ctx_score,
                exact_matches, semantic_matches, experience_matches, context_matches,
                missing_skills, extra_skills,
                total_matched, jd_skill_count
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                resume_id, jd_id,
                final_score, coverage_score,
                exact_score, semantic_score, exp_score, ctx_score,
                json.dumps(list(exact_matched)),
                json.dumps(semantic_matches),
                json.dumps(exp_matches),
                json.dumps(ctx_matches),
                json.dumps(missing_skills),
                json.dumps(list(extra_skills)),
                total_matched,
                len(jd_skills)
            )
        )
        conn.commit()
    except Exception as e:
        print(f"match_results INSERT failed: {e}")
        conn.rollback()

    return {
    "resume_id":          resume_id,
    "jd_id":              jd_id,

    # layer scores
    "exact_score":        exact_score,
    "semantic_score":     semantic_score,
    "experience_score":   exp_score,
    "context_score":      ctx_score,

    # final
    "coverage_score":  coverage_score,
    "final_score":        final_score,

    # matches per layer
    "exact_matches":      list(exact_matched),
    "semantic_matches":   semantic_matches,
    "experience_matches": exp_matches,
    "context_matches":    ctx_matches,

    # gaps
    "missing_skills":     missing_skills,
    "extra_skills":       list(extra_skills),

    # meta
    "jd_skill_count":     len(jd_skills),
    "total_matched":      total_matched
}



#-- batch matching endpoint--------------------------------
@app.post("/match/batch")
async def match_batch(request: BatchMatchRequest):
    resume_id = request.resume_id
    jd_ids    = request.jd_ids

    if not jd_ids:
        return {"error": "no jd_ids provided"}

    results = []

    for jd_id in jd_ids:

        # check cache — don't re-run if already matched
        cur.execute(
            """
            SELECT 
                mr.id, mr.final_score, mr.coverage_score,
                mr.exact_score, mr.semantic_score, mr.exp_score, mr.ctx_score,
                mr.missing_skills, mr.total_matched, mr.jd_skill_count,
                mr.created_at
            FROM match_results mr
            WHERE mr.resume_id = %s AND mr.jd_id = %s
            ORDER BY mr.created_at DESC LIMIT 1
            """,
            (resume_id, jd_id)
        )
        cached = cur.fetchone()

        cur.execute(
            "SELECT title, company FROM job_descriptions WHERE id = %s",
            (jd_id,)
        )
        jd_row = cur.fetchone()
        if not jd_row:
            continue

        jd_title, company = jd_row

        if cached:
            results.append({
                "jd_id":          jd_id,
                "jd_title":       jd_title,
                "company":        company,
                "final_score":    cached[1],
                "coverage_score": cached[2],
                "breakdown": {
                    "exact_score":    cached[3],
                    "semantic_score": cached[4],
                    "exp_score":      cached[5],
                    "ctx_score":      cached[6],
                },
                "missing_skills": cached[7],
                "total_matched":  cached[8],
                "jd_skill_count": cached[9],
                "matched_at":     cached[10].isoformat(),
                "cached":         True
            })
        else:
            # run fresh match
            result = await run_match(resume_id, jd_id)
            results.append({
                "jd_id":          jd_id,
                "jd_title":       jd_title,
                "company":        company,
                "final_score":    result["final_score"],
                "coverage_score": result["coverage_score"],
                "breakdown": {
                    "exact_score":    result["exact_score"],
                    "semantic_score": result["semantic_score"],
                    "exp_score":      result["experience_score"],
                    "ctx_score":      result["context_score"],
                },
                "missing_skills":   result["missing_skills"],
                "total_matched":    result["total_matched"],
                "jd_skill_count":   result["jd_skill_count"],
                "cached":           False
            })

    # rank by final_score
    results.sort(key=lambda x: x["final_score"], reverse=True)

    return {
        "resume_id":  resume_id,
        "total_jds":  len(results),
        "best_match": results[0] if results else None,
        "results":    results
    }



#-- single match endpoint -------------------------------------
@app.get("/match/{resume_id}/{jd_id}")
async def match_resume_jd(resume_id: int, jd_id: int):
    return await run_match(resume_id, jd_id)



# -- endpoint to fetch match history --------------------------
@app.get("/results/{resume_id}")
async def get_resume_results(resume_id: int):
    cur.execute(
        """
        SELECT 
            mr.id, mr.jd_id, jd.title, jd.company,
            mr.final_score, mr.coverage_score,
            mr.exact_score, mr.semantic_score, 
            mr.exp_score, mr.ctx_score,
            mr.missing_skills, mr.total_matched,
            mr.jd_skill_count, mr.created_at
        FROM match_results mr
        JOIN job_descriptions jd ON mr.jd_id = jd.id
        WHERE mr.resume_id = %s
        ORDER BY mr.final_score DESC
        """,
        (resume_id,)
    )
    rows = cur.fetchall()

    if not rows:
        return {"resume_id": resume_id, "matches": []}

    return {
        "resume_id":        resume_id,
        "total_jds":        len(rows),
        "best_match":       {"title": rows[0][2], "company": rows[0][3], "score": rows[0][4]},
        "matches": [
            {
                "match_id":       r[0],
                "jd_id":          r[1],
                "jd_title":       r[2],
                "company":        r[3],
                "final_score":    r[4],
                "coverage_score": r[5],
                "exact_score":    r[6],
                "semantic_score": r[7],
                "exp_score":      r[8],
                "ctx_score":      r[9],
                "missing_skills": r[10],
                "total_matched":  r[11],
                "jd_skill_count": r[12],
                "matched_at":     r[13].isoformat() if r[13] else None
            }
            for r in rows
        ]
    }