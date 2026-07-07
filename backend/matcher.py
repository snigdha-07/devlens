from sentence_transformers import SentenceTransformer, util
import re

# Layer 2 — symmetric skill-to-skill comparison
symmetric_model = SentenceTransformer('all-MiniLM-L6-v2')

# Layer 3/4 — asymmetric short query vs long passage
asymmetric_model = SentenceTransformer('multi-qa-MiniLM-L6-cos-v1')


# ═══════════════════════════════════════════════════════════════
# SHARED HELPER — used by Layer 3 and Layer 4
# ═══════════════════════════════════════════════════════════════

def chunk_text(text: str) -> list:
    """
    Extracts complete bullet points from experience/project sections.
    
    Key fix: PDF line wrapping splits one bullet across multiple lines.
    Only the first line has the (cid:127) marker — subsequent lines are
    plain text continuations. We detect these and rejoin them.
    """
    lines = text.split('\n')
    bullets = []
    current_bullet = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        is_bullet = '(cid:127)' in line or re.match(r'^[•●▪►\-–]', line)

        if is_bullet:
            # save previous bullet before starting new one
            if current_bullet and len(current_bullet) > 20:
                bullets.append(current_bullet)
            # start new bullet, strip the marker
            current_bullet = re.sub(r'\(cid:\d+\)', '', line).strip()
            current_bullet = re.sub(r'^[•●▪►\-–]\s*', '', current_bullet).strip()

        elif current_bullet is not None:
            # this is a continuation of the previous bullet — check it's not
            # a header/date line before appending
            is_header = re.search(
                r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec'
                r'|january|february|march|april|june|july|august'
                r'|september|october|november|december|present|\d{4})\b'
                r'|intern|engineer|developer|analyst',
                line.lower()
            )
            if not is_header:
                current_bullet += ' ' + line   # ← rejoin continuation

    # don't forget the last bullet
    if current_bullet and len(current_bullet) > 20:
        bullets.append(current_bullet)

    # fallback if no bullet markers found at all
    if not bullets:
        text = re.sub(r'\(cid:\d+\)', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        bullets = [
            s.strip() for s in re.split(r'[.!?]', text)
            if len(s.strip()) > 20
        ]

    return bullets

# ═══════════════════════════════════════════════════════════════
# LAYER 2 — skill word vs skill word
# ═══════════════════════════════════════════════════════════════

def semantic_skill_match(
    resume_skills: list,
    jd_skills: list,
    exact_matched: set,
    threshold: float = 0.60,
    name_prefilter: float = 0.40
) -> tuple[list, list]:

    if not resume_skills or not jd_skills:
        return [], [s for s in jd_skills if s not in exact_matched]

    resume_embeddings = symmetric_model.encode(resume_skills, convert_to_tensor=True)
    jd_embeddings     = symmetric_model.encode(jd_skills,     convert_to_tensor=True)

    scores = util.cos_sim(resume_embeddings, jd_embeddings)

    matched_pairs = []
    matched_jd    = set()

    for j, jd_skill in enumerate(jd_skills):
        if jd_skill in exact_matched:
            continue

        best_score        = -1
        best_resume_skill = None

        for i, r_skill in enumerate(resume_skills):
            score = scores[i][j].item()
            if score < name_prefilter:
                continue
            if score > best_score:
                best_score        = score
                best_resume_skill = r_skill

        if best_score >= threshold:
            matched_pairs.append({
                "resume_skill": best_resume_skill,
                "jd_skill":     jd_skill,
                "score":        round(best_score, 3),
                "match_type":   "semantic_skill"
            })
            matched_jd.add(jd_skill)

    still_unmatched = [
        s for s in jd_skills
        if s not in exact_matched and s not in matched_jd
    ]
    return matched_pairs, still_unmatched


# ═══════════════════════════════════════════════════════════════
# LAYER 3 — JD skill phrase vs resume experience/project sentences
# ═══════════════════════════════════════════════════════════════

def get_jd_requirement_sentences(jd_sections: dict) -> dict:
    """
    Extract full requirement sentences from JD responsibilities/skills sections.
    Maps each unmatched skill back to its parent JD sentence for use as query.
    
    Returns: {skill: best_matching_jd_sentence}
    """
    # combine JD sections that contain requirements
    jd_content = (
        jd_sections.get("experience", "") + " " +
        jd_sections.get("skills", "")    + " " +
        jd_sections.get("full", "")
    )

    # extract bullet sentences from JD
    jd_sentences = []
    for line in jd_content.split('\n'):
        line = line.strip()
        clean = re.sub(r'\(cid:\d+\)', '', line).strip()
        clean = re.sub(r'^[•●▪►\-–]\s*', '', clean).strip()
        clean = re.sub(r'\s+', ' ', clean).strip()
        if len(clean) > 20:
            jd_sentences.append(clean)

    return jd_sentences


def build_query(jd_skill: str, jd_sents: list) -> str:
    """
    Build a focused query by combining the skill name with the most
    relevant part of the JD sentence — stripped of company/product noise.
    """
    skill_lower = jd_skill.lower()

    # find the most relevant JD sentence for this skill
    relevant = [
        s for s in jd_sents
        if skill_lower in s.lower()
        or any(w in s.lower() for w in skill_lower.split('/'))
    ]

    if not relevant:
        return jd_skill  # fallback to bare skill

    # take the shortest relevant sentence — least noise
    best_sent = min(relevant, key=len)

    # strip company/product noise patterns from the sentence
    best_sent = re.sub(
        r'\b(our|your|we|the team|nexastack|company name|\w+ technologies)\b',
        '', best_sent, flags=re.IGNORECASE
    )
    best_sent = re.sub(r'\s+', ' ', best_sent).strip()

    # combine: "skill: cleaned requirement context"
    return f"{jd_skill}: {best_sent}"


def experience_match(
    resume_sections: dict,
    jd_sections: dict,
    unmatched_jd_skills: list,
    threshold: float = 0.50
) -> tuple[list, list]:

    if not unmatched_jd_skills:
        return [], []

    resume_exp = (
        resume_sections.get("experience", "") + " " +
        resume_sections.get("projects", "")
    ).strip()

    if not resume_exp:
        return [], unmatched_jd_skills

    resume_bullets = chunk_text(resume_exp)
    if not resume_bullets:
        return [], unmatched_jd_skills

    jd_sents          = get_jd_requirement_sentences(jd_sections)
    bullet_embeddings = asymmetric_model.encode(resume_bullets, convert_to_tensor=True)

    matched       = []
    still_missing = []

    for jd_skill in unmatched_jd_skills:

        # build focused query — skill + cleaned JD context
        query    = build_query(jd_skill, jd_sents)
        q_emb    = asymmetric_model.encode(query, convert_to_tensor=True)
        scores   = util.cos_sim(q_emb, bullet_embeddings)[0]

        best_score  = scores.max().item()
        best_bullet = resume_bullets[scores.argmax().item()]

        if best_score >= threshold:
            matched.append({
                "jd_skill":        jd_skill,
                "resume_evidence": best_bullet,
                "score":           round(best_score, 3),
                "match_type":      "experience_match"
            })
        else:
            still_missing.append(jd_skill)

    return matched, still_missing

# ═══════════════════════════════════════════════════════════════
# LAYER 4 — Entire resume vs jd skills
# ═══════════════════════════════════════════════════════════════

# def chunk_full_text(text: str) -> list:
#     """
#     For Layer 4 — extracts ALL meaningful lines from the full resume,
#     not just bullet points. This catches implied skills from skill lists,
#     project titles, and other non-bullet content.
#     """
#     # strip artifacts
#     text = re.sub(r'\(cid:\d+\)', ' ', text)

#     lines = text.split('\n')
#     chunks = []

#     for line in lines:
#         line = line.strip()
#         line = re.sub(r'\s+', ' ', line).strip()

#         # skip very short lines — names, dates, locations
#         if len(line) < 15:
#             continue

#         # skip pure date lines
#         if re.search(
#             r'^\d{4}|^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
#             line.lower()
#         ):
#             continue

#         chunks.append(line)

#     return chunks
def chunk_full_text(text: str) -> list:
    text = re.sub(r'\(cid:\d+\)', ' ', text)
    lines = text.split('\n')
    chunks = []

    for line in lines:
        line = line.strip()
        line = re.sub(r'\s+', ' ', line).strip()

        if len(line) < 20:          # was 15 — cuts "technical skills" header
            continue

        # skip contact/email lines
        if re.search(r'@|linkedin|github|http', line.lower()):
            continue

        # skip pure date lines
        if re.search(
            r'^\d{4}|^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
            line.lower()
        ):
            continue

        # skip single-word section headers
        if re.match(r'^(education|skills|experience|projects|achievements)$', line.lower()):
            continue

        chunks.append(line)

    return chunks


def full_context_match(
    resume_sections: dict,
    jd_sections: dict,
    unmatched_jd_skills: list,
    threshold: float = 0.40
) -> tuple[list, list]:

    if not unmatched_jd_skills:
        return [], []

    # use entire resume text — not just experience/projects
    full_text = resume_sections.get("full", "")


    # ── ADD THIS ─────────────────────────────────────────────
    print(f"\nfull_text length: {len(full_text)}")
    print(f"full_text preview: {full_text[:200]}")
    # ─────────────────────────────────────────────────────────

    if not full_text:
        return [], unmatched_jd_skills

    resume_chunks= chunk_full_text(full_text)

    # ── ADD THIS ─────────────────────────────────────────────
    print(f"bullets from full text: {len(resume_chunks)}")
    for b in resume_chunks[:3]:
        print(f"  • {b[:100]}")
    
    jd_sents = get_jd_requirement_sentences(jd_sections)
    for skill in ["html", "css"]:
        query = build_query(skill, jd_sents)
        q_emb = asymmetric_model.encode(query, convert_to_tensor=True)
        b_emb = asymmetric_model.encode(resume_chunks, convert_to_tensor=True)
        scores = util.cos_sim(q_emb, b_emb)[0]
        print(f"\n'{skill}' score: {scores.max().item():.3f}")
        print(f"  query: {query}")
        print(f"  bullet: {resume_chunks[scores.argmax().item()][:100]}")
    # ─────────────────────────────────────────────────────────


    if not resume_chunks:
        return [], unmatched_jd_skills

    jd_sents          = get_jd_requirement_sentences(jd_sections)
    chunk_embeddings = asymmetric_model.encode(resume_chunks, convert_to_tensor=True)

    skill_embeddings = symmetric_model.encode(
        unmatched_jd_skills, convert_to_tensor=True
    )

    matched       = []
    still_missing = []

    for idx, jd_skill in enumerate(unmatched_jd_skills):
        query  = build_query(jd_skill, jd_sents)
        q_emb  = asymmetric_model.encode(query, convert_to_tensor=True)
        scores = util.cos_sim(q_emb, chunk_embeddings)[0]

        # check top 5 chunks instead of just rank 1
        top_indices = scores.topk(min(5, len(resume_chunks))).indices

        best_score = -1
        best_chunk = None

        for chunk_idx in top_indices:
            score = scores[chunk_idx].item()

            if score < threshold:
                break  # sorted descending — no point checking further

            chunk     = resume_chunks[chunk_idx]
            chunk_emb = symmetric_model.encode(chunk, convert_to_tensor=True)
            name_sim  = util.cos_sim(skill_embeddings[idx], chunk_emb).item()

            # ─────────────────────────────────────────

            if jd_skill == "html":
                print(f"  html top chunk | score:{score:.3f} name_sim:{name_sim:.3f} | {chunk[:80]}")
            # ─────────────────────────────────────────

            if name_sim >= 0.10 and score > best_score:
                best_score = score
                best_chunk = chunk

        if best_chunk:
            matched.append({
                "jd_skill":        jd_skill,
                "resume_evidence": best_chunk,
                "score":           round(best_score, 3),
                "match_type":      "context_match"
            })
        else:
            still_missing.append(jd_skill)

    return matched, still_missing