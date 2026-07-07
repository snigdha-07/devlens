#before changing layer2 from context to word matching
    #matcher.py
def semantic_skill_match(
    resume_text: str,
    jd_text: str,
    resume_skills: list,
    jd_skills: list,
    exact_matched: set,
    resume_sections: dict,
    jd_sections: dict,
    threshold: float = 0.68,        # lowered from 0.72
    name_prefilter: float = 0.35    # skill names must have minimum similarity
) -> tuple[list, list]:

    if not resume_skills or not jd_skills:
        return [], [s for s in jd_skills if s not in exact_matched]

    resume_contexts = extract_skill_contexts(resume_text, resume_skills, resume_sections)
    jd_contexts     = extract_skill_contexts(jd_text, jd_skills, jd_sections)

    # encode context phrases
    resume_ctx_emb  = model.encode(list(resume_contexts.values()), convert_to_tensor=True)
    jd_ctx_emb      = model.encode(list(jd_contexts.values()),     convert_to_tensor=True)

    # encode bare skill names for pre-filter
    resume_name_emb = model.encode(list(resume_contexts.keys()), convert_to_tensor=True)
    jd_name_emb     = model.encode(list(jd_contexts.keys()),     convert_to_tensor=True)

    ctx_scores  = util.cos_sim(resume_ctx_emb,  jd_ctx_emb)
    name_scores = util.cos_sim(resume_name_emb, jd_name_emb)

    r_skills = list(resume_contexts.keys())
    j_skills = list(jd_contexts.keys())

    matched_pairs = []
    matched_jd    = set()

    for j, jd_skill in enumerate(j_skills):

        # skip already exact-matched JD skills
        if jd_skill in exact_matched:
            continue

        best_score        = -1
        best_resume_skill = None

        for i, r_skill in enumerate(r_skills):
            # pre-filter: skip pairs where skill names are totally unrelated
            # this kills false positives like flask ↔ css (name_sim ~0.21)
            if name_scores[i][j].item() < name_prefilter:
                continue

            score = ctx_scores[i][j].item()
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
        s for s in j_skills
        if s not in exact_matched and s not in matched_jd
    ]
    return matched_pairs, still_unmatched

    #main.py matcher endpoint
    semantic_matches, unmatched_l2 = semantic_skill_match(
        resume_text     = resume_text,
        jd_text         = jd_text,
        resume_skills   = list(resume_skills),
        jd_skills       = list(jd_skills),
        exact_matched   = exact_matched,
        resume_sections = resume_sections,
        jd_sections     = jd_sections,
    )




#matcher before adding layer3

from sentence_transformers import SentenceTransformer, util
import re

model = SentenceTransformer('all-MiniLM-L6-v2')


def extract_skill_contexts(text: str, skills: list, sections: dict, window: int = 12) -> dict:
    """
    For each skill, extract surrounding words as context.
    Searches skills section first, falls back to full text, then bare skill.
    Uses re.search on full string — handles multi-word skills correctly.
    """
    contexts = {}
    search_text = sections.get("skills", "").strip() or text

    for skill in skills:
        skill_lower = skill.lower()
        pattern     = r'\b' + re.escape(skill_lower) + r'\b'
        context     = None

        # try skills section first
        match = re.search(pattern, search_text)
        if match:
            words    = search_text.split()
            word_idx = len(search_text[:match.start()].split())
            start    = max(0, word_idx - window)
            end      = min(len(words), word_idx + window)
            context  = " ".join(words[start:end])

        # fall back to full text
        if not context:
            match = re.search(pattern, text)
            if match:
                words    = text.split()
                word_idx = len(text[:match.start()].split())
                start    = max(0, word_idx - window)
                end      = min(len(words), word_idx + window)
                context  = " ".join(words[start:end])

        contexts[skill] = context if context else skill_lower

    return contexts


def semantic_skill_match(
    resume_skills: list,
    jd_skills: list,
    exact_matched: set,
    threshold: float = 0.60,        # lower — bare names need less threshold
    name_prefilter: float = 0.40    # slightly higher since we're comparing names directly
) -> tuple[list, list]:
    """
    Layer 2: compare bare skill names semantically.
    Transformer already understands skill relationships without context.
    Context windows add noise at this level — save them for Layer 3.
    """

    if not resume_skills or not jd_skills:
        return [], [s for s in jd_skills if s not in exact_matched]

    # encode bare skill names directly
    resume_embeddings = model.encode(resume_skills, convert_to_tensor=True)
    jd_embeddings     = model.encode(jd_skills,     convert_to_tensor=True)

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
            if score < name_prefilter:      # filter unrelated skill pairs
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
