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





#---------------------- app.jsx ---------------------------------------
import { useState, useEffect, useRef } from "react";
import AuthPage from "./pages/AuthPage"
// ── Google Fonts ──────────────────────────────────────────────
const fontLink = document.createElement("link");
fontLink.rel = "stylesheet";
fontLink.href = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap";
document.head.appendChild(fontLink);

// ── Design tokens ─────────────────────────────────────────────
const C = {
  bg:         "#0a0f1e",
  surface:    "#111827",
  surfaceHi:  "#1a2235",
  border:     "#1e2d45",
  borderHi:   "#2d4060",
  accent:     "#6366f1",
  accentLo:   "#312e81",
  accentText: "#a5b4fc",
  textPri:    "#f1f5f9",
  textSec:    "#94a3b8",
  textMut:    "#4b5563",
  green:      "#10b981",
  greenBg:    "#052e16",
  greenBord:  "#065f46",
  yellow:     "#f59e0b",
  yellowBg:   "#1c1106",
  yellowBord: "#78350f",
  red:        "#ef4444",
  redBg:      "#1f0707",
  redBord:    "#7f1d1d",
  indigo:     "#818cf8",
  indigoBg:   "#1e1b4b",
  indigoBord: "#3730a3",
};

const T = {
  display: "'Inter', sans-serif",
  mono:    "'JetBrains Mono', monospace",
};

// ── Score ring component ───────────────────────────────────────
function ScoreRing({ score, size = 80 }) {
  const radius    = (size - 10) / 2;
  const circum    = 2 * Math.PI * radius;
  const [drawn, setDrawn] = useState(0);

  useEffect(() => {
    let frame;
    let start = null;
    const duration = 900;
    const animate  = (ts) => {
      if (!start) start = ts;
      const prog = Math.min((ts - start) / duration, 1);
      const ease = 1 - Math.pow(1 - prog, 3);
      setDrawn(ease * score);
      if (prog < 1) frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [score]);

  const color = score >= 70 ? C.green : score >= 50 ? C.yellow : C.red;
  const offset = circum - (drawn / 100) * circum;

  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size/2} cy={size/2} r={radius}
              fill="none" stroke={C.border} strokeWidth={6} />
      <circle cx={size/2} cy={size/2} r={radius}
              fill="none" stroke={color} strokeWidth={6}
              strokeDasharray={circum} strokeDashoffset={offset}
              strokeLinecap="round"
              style={{ transition: "none", filter: `drop-shadow(0 0 6px ${color})` }} />
      <text x={size/2} y={size/2}
            textAnchor="middle" dominantBaseline="central"
            fill={color} fontSize={size * 0.22} fontWeight={600}
            fontFamily={T.mono} style={{ transform: "rotate(90deg)", transformOrigin: `${size/2}px ${size/2}px` }}>
        {Math.round(drawn)}%
      </text>
    </svg>
  );
}

// ── Upload zone ────────────────────────────────────────────────
function UploadZone({ label, accept, onChange, uploaded, disabled }) {
  const inputRef   = useRef();
  const [drag, setDrag] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault(); setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f) onChange({ target: { files: [f] } });
  };

  return (
    <div
      onClick={() => !disabled && inputRef.current.click()}
      onDragOver={e => { e.preventDefault(); if (!disabled) setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
      style={{
        border: `1.5px dashed ${drag ? C.accent : uploaded ? C.greenBord : C.border}`,
        borderRadius: "10px",
        padding: "20px",
        textAlign: "center",
        cursor: disabled ? "default" : "pointer",
        background: drag ? C.accentLo : uploaded ? C.greenBg : C.surfaceHi,
        transition: "all 0.2s",
        position: "relative",
      }}
    >
      <input ref={inputRef} type="file" accept={accept}
             onChange={onChange} style={{ display: "none" }} />
      {uploaded ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}>
          <span style={{ color: C.green, fontSize: "18px" }}>✓</span>
          <span style={{ color: C.green, fontSize: "13px", fontFamily: T.mono }}>{uploaded}</span>
        </div>
      ) : (
        <div>
          <div style={{ fontSize: "28px", marginBottom: "6px" }}>📄</div>
          <div style={{ color: C.textSec, fontSize: "13px" }}>{label}</div>
          <div style={{ color: C.textMut, fontSize: "11px", marginTop: "4px" }}>PDF only</div>
        </div>
      )}
    </div>
  );
}

// ── Skill tag ──────────────────────────────────────────────────
function Tag({ label, variant = "default" }) {
  const styles = {
    default: { bg: C.surfaceHi,  text: C.textSec,    border: C.border    },
    green:   { bg: C.greenBg,    text: C.green,       border: C.greenBord },
    red:     { bg: C.redBg,      text: C.red,         border: C.redBord   },
    indigo:  { bg: C.indigoBg,   text: C.accentText,  border: C.indigoBord },
    yellow:  { bg: C.yellowBg,   text: C.yellow,      border: C.yellowBord },
  };
  const s = styles[variant] || styles.default;
  return (
    <span style={{
      background: s.bg, color: s.text, border: `1px solid ${s.border}`,
      borderRadius: "999px", padding: "2px 10px",
      fontSize: "11px", fontFamily: T.mono, whiteSpace: "nowrap",
    }}>{label}</span>
  );
}

// ── Layer bar ──────────────────────────────────────────────────
function LayerBar({ label, score, color }) {
  const [width, setWidth] = useState(0);
  useEffect(() => { setTimeout(() => setWidth(score), 100); }, [score]);
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between",
                    marginBottom: "4px", alignItems: "center" }}>
        <span style={{ fontSize: "11px", color: C.textSec, fontFamily: T.mono }}>{label}</span>
        <span style={{ fontSize: "11px", color, fontFamily: T.mono, fontWeight: 600 }}>
          {score}%
        </span>
      </div>
      <div style={{ height: "4px", background: C.border, borderRadius: "2px", overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${width}%`, background: color,
          borderRadius: "2px", transition: "width 0.8s cubic-bezier(0.4,0,0.2,1)",
          boxShadow: `0 0 8px ${color}66`,
        }} />
      </div>
    </div>
  );
}

// ── Result card ────────────────────────────────────────────────
function ResultCard({ result, rank, onViewDetail, isSelected }) {
  const scoreColor = result.final_score >= 70 ? C.green
                   : result.final_score >= 50 ? C.yellow : C.red;

  return (
    <div style={{
      border: `1px solid ${isSelected ? C.accent : C.border}`,
      borderRadius: "12px", padding: "20px",
      background: isSelected ? "#0f1729" : C.surface,
      transition: "all 0.2s",
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
            <span style={{
              fontSize: "10px", fontFamily: T.mono, color: C.textMut,
              border: `1px solid ${C.border}`, borderRadius: "4px",
              padding: "1px 6px",
            }}>#{rank}</span>
            <span style={{ fontSize: "15px", fontWeight: 600, color: C.textPri,
                           overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {result.jd_title}
            </span>
          </div>
          <div style={{ fontSize: "12px", color: C.textSec }}>{result.company}</div>
          <div style={{ fontSize: "11px", color: C.textMut, fontFamily: T.mono, marginTop: "2px" }}>
            {result.total_matched}/{result.jd_skill_count} skills matched
          </div>
        </div>
        <div style={{ marginLeft: "16px", flexShrink: 0 }}>
          <ScoreRing score={result.final_score} size={72} />
        </div>
      </div>

      {/* Layer bars */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "16px" }}>
        <LayerBar label="Exact"      score={result.breakdown?.exact_score || 0}    color={C.green}  />
        <LayerBar label="Semantic"   score={result.breakdown?.semantic_score || 0}  color={C.indigo} />
        <LayerBar label="Experience" score={result.breakdown?.exp_score || 0}       color={C.yellow} />
        <LayerBar label="Context"    score={result.breakdown?.ctx_score || 0}       color={C.accent} />
      </div>

      {/* Missing skills */}
      {result.missing_skills?.length > 0 && (
        <div style={{ marginBottom: "12px" }}>
          <div style={{ fontSize: "11px", color: C.textMut, marginBottom: "6px", fontFamily: T.mono }}>
            MISSING SKILLS
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
            {result.missing_skills.map(s => <Tag key={s} label={s} variant="red" />)}
          </div>
        </div>
      )}

      <button onClick={() => onViewDetail(result.jd_id)}
              style={{
                background: "none", border: `1px solid ${C.borderHi}`,
                borderRadius: "6px", color: C.accentText,
                fontSize: "12px", fontFamily: T.mono,
                padding: "6px 12px", cursor: "pointer",
                transition: "all 0.15s",
              }}
              onMouseEnter={e => e.target.style.borderColor = C.accent}
              onMouseLeave={e => e.target.style.borderColor = C.borderHi}
      >
        full breakdown →
      </button>
    </div>
  );
}

// ── Detail panel ───────────────────────────────────────────────
function DetailPanel({ result, onClose }) {
  if (!result) return null;

  const Section = ({ title, children }) => (
    <div style={{ marginBottom: "16px" }}>
      <div style={{
        fontSize: "10px", fontFamily: T.mono, color: C.textMut,
        letterSpacing: "0.1em", marginBottom: "8px",
        borderBottom: `1px solid ${C.border}`, paddingBottom: "6px",
      }}>{title}</div>
      {children}
    </div>
  );

  const EvidenceItem = ({ skill, evidence, color, border, bg }) => (
    <div style={{
      background: bg, border: `1px solid ${border}`,
      borderRadius: "8px", padding: "10px 12px", marginBottom: "6px",
    }}>
      <span style={{ fontFamily: T.mono, fontSize: "12px", color, fontWeight: 600 }}>{skill}</span>
      {evidence && (
        <p style={{ color: C.textSec, fontSize: "12px", margin: "4px 0 0", lineHeight: "1.5",
                    fontStyle: "italic" }}>
          "{evidence}"
        </p>
      )}
    </div>
  );

  return (
    <div style={{
      border: `1px solid ${C.accent}`, borderRadius: "12px",
      padding: "20px", background: "#0c1220",
      boxShadow: `0 0 30px ${C.accent}22`,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <span style={{ fontSize: "13px", fontWeight: 600, color: C.textPri }}>Full Breakdown</span>
        <button onClick={onClose} style={{
          background: "none", border: "none", color: C.textMut,
          cursor: "pointer", fontSize: "18px", lineHeight: 1, padding: "2px 6px",
        }}>×</button>
      </div>

      {result.exact_matches?.length > 0 && (
        <Section title="EXACT MATCHES">
          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
            {result.exact_matches.map(s => <Tag key={s} label={s} variant="green" />)}
          </div>
        </Section>
      )}

      {result.semantic_matches?.length > 0 && (
        <Section title="SEMANTIC MATCHES">
          {result.semantic_matches.map((m, i) => (
            <EvidenceItem key={i}
                          skill={`${m.resume_skill} → ${m.jd_skill}`}
                          evidence={null}
                          color={C.green} border={C.greenBord} bg={C.greenBg} />
          ))}
        </Section>
      )}

      {result.experience_matches?.length > 0 && (
        <Section title="EXPERIENCE EVIDENCE">
          {result.experience_matches.map((m, i) => (
            <EvidenceItem key={i} skill={m.jd_skill} evidence={m.resume_evidence}
                          color={C.yellow} border={C.yellowBord} bg={C.yellowBg} />
          ))}
        </Section>
      )}

      {result.context_matches?.length > 0 && (
        <Section title="CONTEXT MATCHES">
          {result.context_matches.map((m, i) => (
            <EvidenceItem key={i} skill={m.jd_skill} evidence={m.resume_evidence}
                          color={C.accentText} border={C.indigoBord} bg={C.indigoBg} />
          ))}
        </Section>
      )}      

      {result.extra_skills?.length > 0 && (
        <Section title="BONUS SKILLS (not required by JD)">
          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
            {result.extra_skills.map(s => <Tag key={s} label={s} variant="indigo" />)}
          </div>
        </Section>
      )}
      
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────
function App() {
  const [authUser, setAuthUser] = useState(() => {
    // restore session from localStorage on page load
    const token = localStorage.getItem("token")
    const uid   = localStorage.getItem("user_id")
    const email = localStorage.getItem("email")
    return token ? { token, user_id: uid, email } : null
  })
  const [resumeFile, setResumeFile]   = useState(null);
  const [jdFile, setJdFile]           = useState(null);
  const [title, setTitle]             = useState("");
  const [company, setCompany]         = useState("");
  const [resumeSkills, setResumeSkills] = useState([]);
  const [resumeId, setResumeId]       = useState(null);
  const [resumeName, setResumeName]   = useState("");
  const [jdList, setJdList]           = useState([]);
  const [jdSkills, setJdSkills]       = useState([]);
  const [matching, setMatching]       = useState(false);
  const [matchResults, setMatchResults] = useState(null);
  const [selectedResult, setSelectedResult] = useState(null);
  const [selectedJdId, setSelectedJdId]     = useState(null);
  const [uploading, setUploading]     = useState({ resume: false, jd: false });
  const [error, setError]             = useState("");

const handleAuth = (data) => {
    setAuthUser({ token: data.access_token, user_id: data.user_id, email: data.email })
  }

  const handleLogout = () => {
    localStorage.removeItem("token")
    localStorage.removeItem("user_id")
    localStorage.removeItem("email")
    setAuthUser(null)
  }

  const handleResumeUpload = async () => {
    if (!resumeFile) { setError("Select a resume PDF first"); return; }
    setError("");
    setUploading(u => ({ ...u, resume: true }));
    try {
      const form = new FormData();
      form.append("file", resumeFile);
      const res  = await fetch("http://127.0.0.1:8000/upload-resume", { method: "POST", body: form });
      const data = await res.json();
      setResumeSkills(data.skills || []);
      setResumeId(data["resume id"]);
      setResumeName(resumeFile.name);
    } catch (e) {
      setError("Resume upload failed. Is the backend running?");
    } finally {
      setUploading(u => ({ ...u, resume: false }));
    }
  };

  const handleJDUpload = async () => {
    if (!jdFile || !title || !company) {
      setError("Fill in title, company, and select a JD PDF");
      return;
    }
    setError("");
    setUploading(u => ({ ...u, jd: true }));
    try {
      const form = new FormData();
      form.append("title", title);
      form.append("company", company);
      form.append("file", jdFile);
      const res  = await fetch("http://127.0.0.1:8000/add-jd", { method: "POST", body: form });
      const data = await res.json();
      setJdSkills(data.skills || []);
      setJdList(prev => [...prev, { id: data.jd_id, title, company, skills: data.skills || [] }]);
      setTitle(""); setCompany(""); setJdFile(null);
    } catch (e) {
      setError("JD upload failed.");
    } finally {
      setUploading(u => ({ ...u, jd: false }));
    }
  };

  const handleMatch = async () => {
    if (!resumeId || jdList.length === 0) {
      setError("Upload a resume and at least one JD first");
      return;
    }
    setError("");
    setMatching(true);
    setMatchResults(null);
    setSelectedResult(null);
    try {
      const res  = await fetch("http://127.0.0.1:8000/match/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume_id: resumeId, jd_ids: jdList.map(j => j.id) })
      });
      const data = await res.json();
      setMatchResults(data);
    } catch (e) {
      setError("Matching failed. Check the backend.");
    } finally {
      setMatching(false);
    }
  };

  const handleViewDetail = async (jd_id) => {
    if (selectedJdId === jd_id) {
      setSelectedResult(null); setSelectedJdId(null); return;
    }
    try {
      const res  = await fetch(`http://127.0.0.1:8000/match/${resumeId}/${jd_id}`);
      const data = await res.json();
      setSelectedResult(data);
      setSelectedJdId(jd_id);
    } catch (e) {
      setError("Could not load detail.");
    }
  };

  // ── Input style ──
  const inputStyle = {
    width: "100%", padding: "9px 12px",
    background: C.surfaceHi, border: `1px solid ${C.border}`,
    borderRadius: "8px", color: C.textPri,
    fontSize: "13px", fontFamily: T.display,
    outline: "none", boxSizing: "border-box",
  };

  const btnStyle = (primary) => ({
    padding: "10px 18px", borderRadius: "8px",
    border: primary ? "none" : `1px solid ${C.border}`,
    background: primary ? C.accent : C.surfaceHi,
    color: primary ? "white" : C.textSec,
    fontSize: "13px", fontWeight: 500, fontFamily: T.display,
    cursor: "pointer", transition: "all 0.15s",
  });

  return (
    <div style={{
      minHeight: "100vh", background: C.bg,
      fontFamily: T.display, color: C.textPri,
      padding: "0 0 80px",
    }}>

      {/* Nav */}
      <div style={{
        borderBottom: `1px solid ${C.border}`, padding: "0 24px",
        display: "flex", alignItems: "center", height: "52px",
        position: "sticky", top: 0, background: `${C.bg}ee`,
        backdropFilter: "blur(12px)", zIndex: 10,
      }}>
        <span style={{
          fontFamily: T.mono, fontWeight: 600, fontSize: "15px",
          color: C.textPri, letterSpacing: "-0.02em",
        }}>
          dev<span style={{ color: C.accent }}>lens</span>
        </span>
        {resumeId && (
          <span style={{
            marginLeft: "16px", fontSize: "11px", fontFamily: T.mono,
            color: C.textMut, background: C.surfaceHi,
            border: `1px solid ${C.border}`, borderRadius: "4px", padding: "2px 8px",
          }}>
            resume #{resumeId}
          </span>
          
        )}
      </div>

      {/* Main */}
      <div style={{ maxWidth: "660px", margin: "0 auto", padding: "32px 24px" }}>

        {/* Hero */}
        <div style={{ marginBottom: "36px" }}>
          <h1 style={{
            fontSize: "28px", fontWeight: 700, letterSpacing: "-0.03em",
            color: C.textPri, margin: "0 0 8px",
          }}>
            Match your resume to any job.
          </h1>
          <p style={{ fontSize: "14px", color: C.textSec, margin: 0, lineHeight: "1.6" }}>
            Upload your resume and one or more job descriptions.
            DevLens scores compatibility across four semantic layers.
          </p>
        </div>

        {/* Step 1 — Resume */}
        <div style={{
          background: C.surface, border: `1px solid ${C.border}`,
          borderRadius: "12px", padding: "20px", marginBottom: "12px",
        }}>
          <div style={{
            fontSize: "10px", fontFamily: T.mono, color: C.textMut,
            letterSpacing: "0.1em", marginBottom: "14px",
          }}>01 — RESUME</div>

          <UploadZone
            label="Drop your resume here or click to browse"
            accept="application/pdf"
            onChange={e => setResumeFile(e.target.files[0])}
            uploaded={resumeName}
          />

          {!resumeId && (
            <button onClick={handleResumeUpload} disabled={uploading.resume}
                    style={{ ...btnStyle(true), marginTop: "12px", width: "100%",
                             opacity: uploading.resume ? 0.6 : 1 }}>
              {uploading.resume ? "Uploading..." : "Upload Resume"}
            </button>
          )}

          {resumeSkills.length > 0 && (
            <div style={{ marginTop: "14px" }}>
              <div style={{ fontSize: "11px", color: C.textMut, fontFamily: T.mono, marginBottom: "8px" }}>
                {resumeSkills.length} SKILLS DETECTED
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                {resumeSkills.map(s => <Tag key={s} label={s} variant="green" />)}
              </div>
            </div>
          )}
        </div>

        {/* Step 2 — JDs */}
        <div style={{
          background: C.surface, border: `1px solid ${C.border}`,
          borderRadius: "12px", padding: "20px", marginBottom: "12px",
        }}>
          <div style={{
            fontSize: "10px", fontFamily: T.mono, color: C.textMut,
            letterSpacing: "0.1em", marginBottom: "14px",
          }}>02 — JOB DESCRIPTIONS</div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "10px" }}>
            <input placeholder="Job Title" value={title}
                   onChange={e => setTitle(e.target.value)} style={inputStyle} />
            <input placeholder="Company" value={company}
                   onChange={e => setCompany(e.target.value)} style={inputStyle} />
          </div>

          <UploadZone
            label="Drop JD PDF here or click to browse"
            accept="application/pdf"
            onChange={e => setJdFile(e.target.files[0])}
            uploaded={jdFile?.name}
          />

          <button onClick={handleJDUpload} disabled={uploading.jd}
                  style={{ ...btnStyle(false), marginTop: "10px", width: "100%",
                           opacity: uploading.jd ? 0.6 : 1 }}>
            {uploading.jd ? "Adding..." : "+ Add JD"}
          </button>

          {/* JD list */}
          {jdList.length > 0 && (
            <div style={{ marginTop: "14px", display: "flex", flexDirection: "column", gap: "6px" }}>
              {jdList.map(jd => (
                <div key={jd.id} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  background: C.greenBg, border: `1px solid ${C.greenBord}`,
                  borderRadius: "8px", padding: "8px 12px",
                }}>
                  <div>
                    <span style={{ fontSize: "13px", color: C.textPri, fontWeight: 500 }}>
                      {jd.title}
                    </span>
                    <span style={{ fontSize: "12px", color: C.textSec }}> — {jd.company}</span>
                  </div>
                  <span style={{ fontSize: "11px", fontFamily: T.mono, color: C.green }}>
                    {jd.skills.length} skills
                  </span>
                </div>
              ))}
            </div>
          )}

          {jdSkills.length > 0 && (
            <div style={{ marginTop: "12px" }}>
              <div style={{ fontSize: "11px", color: C.textMut, fontFamily: T.mono, marginBottom: "6px" }}>
                LAST JD SKILLS
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                {jdSkills.map(s => <Tag key={s} label={s} variant="indigo" />)}
              </div>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div style={{
            background: C.redBg, border: `1px solid ${C.redBord}`,
            borderRadius: "8px", padding: "10px 14px",
            fontSize: "13px", color: C.red, marginBottom: "12px",
          }}>
            {error}
          </div>
        )}

        {/* Match button */}
        <button
          onClick={handleMatch}
          disabled={!resumeId || jdList.length === 0 || matching}
          style={{
            width: "100%", padding: "14px",
            background: (!resumeId || jdList.length === 0 || matching)
              ? C.surfaceHi : C.accent,
            border: "none", borderRadius: "10px",
            color: (!resumeId || jdList.length === 0 || matching)
              ? C.textMut : "white",
            fontSize: "15px", fontWeight: 600, fontFamily: T.display,
            cursor: (!resumeId || jdList.length === 0 || matching)
              ? "not-allowed" : "pointer",
            transition: "all 0.2s",
            marginBottom: "24px",
            boxShadow: (!resumeId || jdList.length === 0 || matching)
              ? "none" : `0 0 20px ${C.accent}44`,
          }}
        >
          {matching
            ? "Analysing..."
            : !resumeId
              ? "Upload a resume to continue"
              : jdList.length === 0
                ? "Add at least one JD"
                : `Analyse ${jdList.length} JD${jdList.length > 1 ? "s" : ""}`}
        </button>

        {/* Results */}
        {matchResults && (
          <div>
            <div style={{
              display: "flex", justifyContent: "space-between",
              alignItems: "baseline", marginBottom: "16px",
            }}>
              <span style={{ fontSize: "16px", fontWeight: 600, color: C.textPri }}>
                Results
              </span>
              <span style={{ fontSize: "11px", fontFamily: T.mono, color: C.textMut }}>
                {matchResults.total_jds} JD{matchResults.total_jds > 1 ? "s" : ""} · best fit first
              </span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {matchResults.results?.map((r, i) => (
                <div key={r.jd_id}>
                  <ResultCard
                    result={r}
                    rank={i + 1}
                    onViewDetail={handleViewDetail}
                    isSelected={selectedJdId === r.jd_id}
                  />
                  {selectedJdId === r.jd_id && selectedResult && (
                    <div style={{ marginTop: "8px" }}>
                      <DetailPanel
                        result={selectedResult}
                        onClose={() => { setSelectedResult(null); setSelectedJdId(null); }}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}