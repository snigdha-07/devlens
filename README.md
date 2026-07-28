# DevLens

DevLens is a full-stack **resume - job description matching platform**. It lets students/candidates upload a resume and match it against job descriptions (or a whole batch of them), and lets recruiters upload a JD and rank every candidate resume against it with a transparent, multi-layer breakdown of *why* a match scored the way it did, not just a single black-box percentage.

---

## How matching works

Resumes and JDs are PDF-parsed, cleaned, and skill-tagged, then compared through four progressively "fuzzier" layers so a skill isn't marked missing just because the resume phrased it differently:

| Layer | What it checks | Method |
|---|---|---|
| 1. Exact match | Skill appears in both, via alias/fuzzy dictionary | `rapidfuzz` + curated skill-alias table (`skills.py`) |
| 2. Semantic skill match | Skill names are close in meaning even if wording differs | Sentence-transformer embeddings (`all-MiniLM-L6-v2`) |
| 3. Experience match | Skill is evidenced in a resume bullet/project, even if not listed as a "skill" | Asymmetric embeddings (`multi-qa-MiniLM-L6-cos-v1`) vs. experience/project bullets |
| 4. Full-context match | Skill is mentioned anywhere else in the resume | Same asymmetric model, run over the whole resume as a fallback |

Each layer's matches are weighted (1.00 / 0.90 / 0.80 / 0.70) into a **final score**, alongside a raw **coverage score**, and both are cached per resume-JD pair so repeat lookups are instant.

---

## Features (implemented)

- **Auth** - JWT-based register/login with bcrypt password hashing, role-based access (`student` vs `recruiter`)
- **Resume upload** - PDF parsing (`pdfplumber`) + automatic skill extraction and storage
- **JD upload** - same pipeline, tied to a title/company
- **4-layer resume-JD matching engine** (see above) with a persisted score breakdown
- **Batch matching** - match one resume against many JDs at once, sorted by score
- **Recruiter view** - upload a JD, rank every candidate resume against it
- **Match history** - past match results per resume, retrievable without recomputing
- **React (Vite) frontend** - student flow (upload → results, with per-layer score bars and evidence detail panels) and a separate recruiter flow

## Planned / not yet implemented

- Live GitHub integration (repo/activity analysis)
- Developer productivity & activity analytics
- ML-based recommendations beyond matching
- Real-time dashboard updates
- Docker + CI/CD (GitHub Actions)
- Team collaboration support

---

## Tech Stack

- **Frontend:** React 19, Vite, plain CSS
- **Backend:** Python, FastAPI, PostgreSQL (`psycopg2`)
- **Matching/NLP:** `sentence-transformers` (MiniLM models), `rapidfuzz`
- **Auth:** `python-jose` (JWT), `passlib` (bcrypt)
- **PDF parsing:** `pdfplumber`

---

## Project Structure

```
backend/
  main.py          # FastAPI app: auth, upload, matching, recruiter endpoints
  matcher.py        # 4-layer matching engine (semantic/experience/context)
  auth.py           # JWT + password hashing
  skills.py          # skill alias dictionary used for exact matching
  previous.py         # legacy/experimental matcher draft — not wired into the app
frontend/
  src/
    App.jsx           # main app shell + student view (upload, results, score UI)
    api/
      index.js         # API client
      pages/
        AuthPage.jsx
        UploadPage.jsx
        ResultsPage.jsx
        RecruiterView.jsx
    components/          # currently empty placeholder files (UI lives in App.jsx / api/pages instead)
```

> **Known cleanup item:** the files under `frontend/src/components/` (`ResumeUpload.jsx`, `ScoreCard.jsx`, etc.) are empty stubs - the working UI logic currently lives inline in `App.jsx` and `src/api/pages/`. `backend/previous.py` is an old draft of the matcher kept for reference and is not imported anywhere.


---

## Repository Status

DevLens is under active development. Core auth, upload, and the matching engine are functional end-to-end for both student and recruiter flows; GitHub integration, analytics, and deployment tooling are still on the roadmap.
