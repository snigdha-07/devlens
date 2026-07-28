import { useState } from "react"

const C={
  bg:"#0a0f1e",surface:"#111827",surfaceHi:"#1a2235",border:"#1e2d45",borderHi:"#2d4060",
  accent:"#6366f1",accentLo:"#312e81",accentText:"#a5b4fc",textPri:"#f1f5f9",textSec:"#94a3b8",
  textMut:"#4b5563",green:"#10b981",greenBg:"#052e16",greenBord:"#065f46",yellow:"#f59e0b",
  yellowBg:"#1c1106",yellowBord:"#78350f",red:"#ef4444",redBg:"#1f0707",redBord:"#7f1d1d",
  indigo:"#818cf8",indigoBg:"#1e1b4b",indigoBord:"#3730a3",
  mono:"'JetBrains Mono', monospace",display:"'Inter', sans-serif",
}

function Tag({label,variant="default"}){
  const s={default:{bg:C.surfaceHi,text:C.textSec,border:C.border},
    green:{bg:C.greenBg,text:C.green,border:C.greenBord},
    red:{bg:C.redBg,text:C.red,border:C.redBord},
    indigo:{bg:C.indigoBg,text:C.accentText,border:C.indigoBord},
    yellow:{bg:C.yellowBg,text:C.yellow,border:C.yellowBord}}[variant]||{}
  return<span style={{background:s.bg,color:s.text,border:`1px solid ${s.border}`,
    borderRadius:"999px",padding:"2px 10px",fontSize:"11px",
    fontFamily:C.mono,whiteSpace:"nowrap"}}>{label}</span>
}

function DetailPanel({result,onClose}){
  if(!result)return null
  const Section=({title,children})=>(
    <div style={{marginBottom:"14px"}}>
      <div style={{fontSize:"10px",fontFamily:C.mono,color:C.textMut,letterSpacing:"0.1em",
                   marginBottom:"8px",borderBottom:`1px solid ${C.border}`,paddingBottom:"5px"}}>
        {title}
      </div>
      {children}
    </div>
  )
  const EvidenceItem=({skill,evidence,color,border,bg})=>(
    <div style={{background:bg,border:`1px solid ${border}`,borderRadius:"7px",
                 padding:"9px 11px",marginBottom:"5px"}}>
      <span style={{fontFamily:C.mono,fontSize:"12px",color,fontWeight:600}}>{skill}</span>
      {evidence&&<p style={{color:C.textSec,fontSize:"12px",margin:"4px 0 0",
                            lineHeight:"1.5",fontStyle:"italic"}}>"{evidence}"</p>}
    </div>
  )
  return(
    <div style={{border:`1px solid ${C.accent}`,borderRadius:"12px",padding:"18px",
                 background:"#0c1220",boxShadow:`0 0 24px ${C.accent}22`,marginTop:"8px"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"14px"}}>
        <span style={{fontSize:"13px",fontWeight:600,color:C.textPri}}>Full Breakdown</span>
        <button onClick={onClose} style={{background:"none",border:"none",color:C.textMut,
                                          cursor:"pointer",fontSize:"18px",padding:"2px 6px"}}>×</button>
      </div>
      {result.exact_matches?.length>0&&(
        <Section title="EXACT MATCHES">
          <div style={{display:"flex",flexWrap:"wrap",gap:"4px"}}>
            {result.exact_matches.map(s=><Tag key={s} label={s} variant="green"/>)}
          </div>
        </Section>
      )}
      {result.semantic_matches?.length>0&&(
        <Section title="SEMANTIC MATCHES">
          {result.semantic_matches.map((m,i)=>(
            <EvidenceItem key={i} skill={`${m.resume_skill} → ${m.jd_skill}`}
                          color={C.green} border={C.greenBord} bg={C.greenBg}/>
          ))}
        </Section>
      )}
      {result.experience_matches?.length>0&&(
        <Section title="EXPERIENCE EVIDENCE">
          {result.experience_matches.map((m,i)=>(
            <EvidenceItem key={i} skill={m.jd_skill} evidence={m.resume_evidence}
                          color={C.yellow} border={C.yellowBord} bg={C.yellowBg}/>
          ))}
        </Section>
      )}
      {result.context_matches?.length>0&&(
        <Section title="CONTEXT MATCHES">
          {result.context_matches.map((m,i)=>(
            <EvidenceItem key={i} skill={m.jd_skill} evidence={m.resume_evidence}
                          color={C.accentText} border={C.indigoBord} bg={C.indigoBg}/>
          ))}
        </Section>
      )}
      {result.missing_skills?.length>0&&(
        <Section title="MISSING SKILLS">
          <div style={{display:"flex",flexWrap:"wrap",gap:"4px"}}>
            {result.missing_skills.map(s=><Tag key={s} label={s} variant="red"/>)}
          </div>
        </Section>
      )}
      {result.extra_skills?.length>0&&(
        <Section title="BONUS SKILLS">
          <div style={{display:"flex",flexWrap:"wrap",gap:"4px"}}>
            {result.extra_skills.map(s=><Tag key={s} label={s} variant="indigo"/>)}
          </div>
        </Section>
      )}
    </div>
  )
}

export default function RecruiterView({authUser,onLogout}){
  const [jdFile,setJdFile]=useState(null)
  const [title,setTitle]=useState("")
  const [company,setCompany]=useState("")
  const [jdId,setJdId]=useState(null)
  const [jdTitle,setJdTitle]=useState("")
  const [resumes,setResumes]=useState([])
  const [selected,setSelected]=useState([])
  const [results,setResults]=useState(null)
  const [matching,setMatching]=useState(false)
  const [uploading,setUploading]=useState(false)
  const [error,setError]=useState("")
  const [detailId,setDetailId]=useState(null)
  const [detailData,setDetailData]=useState(null)

  const authFetch=(url,opts={})=>fetch(url,{
    ...opts,headers:{...opts.headers,Authorization:`Bearer ${authUser.token}`}
  })

  const handleJDUpload=async()=>{
    if(!jdFile||!title||!company){setError("Fill in title, company, and select a JD PDF");return}
    setError("");setUploading(true)
    try{
      const form=new FormData()
      form.append("title",title);form.append("company",company);form.append("file",jdFile)
      const res=await authFetch("http://127.0.0.1:8000/add-jd",{method:"POST",body:form})
      const data=await res.json()
      setJdId(data.jd_id);setJdTitle(title)
      const r2=await authFetch("http://127.0.0.1:8000/recruiter/resumes")
      setResumes((await r2.json()).resumes||[])
    }catch{setError("JD upload failed. Is the backend running?")}
    finally{setUploading(false)}
  }

  const toggleResume=id=>setSelected(prev=>
    prev.includes(id)?prev.filter(x=>x!==id):[...prev,id])

  const selectAll=()=>setSelected(
    selected.length===resumes.length?[]:resumes.map(r=>r.resume_id))

  const handleMatch=async()=>{
    if(selected.length===0){setError("Select at least one candidate");return}
    setError("");setMatching(true);setResults(null);setDetailId(null);setDetailData(null)
    try{
      const res=await authFetch("http://127.0.0.1:8000/recruiter/match",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({jd_id:jdId,resume_ids:selected})
      })
      setResults(await res.json())
    }catch{setError("Matching failed.")}
    finally{setMatching(false)}
  }

  const handleViewDetail=async(resume_id)=>{
    if(detailId===resume_id){setDetailId(null);setDetailData(null);return}
    try{
      const res=await authFetch(`http://127.0.0.1:8000/match/${resume_id}/${jdId}`)
      setDetailData(await res.json());setDetailId(resume_id)
    }catch{setError("Could not load detail.")}
  }

  const inputStyle={width:"100%",padding:"9px 12px",boxSizing:"border-box",
    background:C.surfaceHi,border:`1px solid ${C.border}`,borderRadius:"8px",
    color:C.textPri,fontSize:"13px",fontFamily:C.display,outline:"none"}

  const scoreColor=s=>s>=70?C.green:s>=50?C.yellow:C.red

  return(
    <div style={{minHeight:"100vh",background:C.bg,fontFamily:C.display,
                 color:C.textPri,paddingBottom:"80px"}}>

      {/* Nav */}
      <div style={{borderBottom:`1px solid ${C.border}`,padding:"0 24px",
                   display:"flex",alignItems:"center",height:"52px",position:"sticky",
                   top:0,background:`${C.bg}ee`,backdropFilter:"blur(12px)",zIndex:10}}>
        <span style={{fontFamily:C.mono,fontWeight:600,fontSize:"15px",letterSpacing:"-0.02em"}}>
          dev<span style={{color:C.accent}}>lens</span>
        </span>
        <span style={{marginLeft:"10px",fontSize:"10px",fontFamily:C.mono,color:C.accentText,
                      background:C.indigoBg,border:`1px solid ${C.indigoBord}`,
                      borderRadius:"4px",padding:"2px 7px"}}>recruiter</span>
        {jdId&&<span style={{marginLeft:"10px",fontSize:"10px",fontFamily:C.mono,color:C.textMut,
                              background:C.surfaceHi,border:`1px solid ${C.border}`,
                              borderRadius:"4px",padding:"2px 7px"}}>
          jd #{jdId} · {jdTitle}
        </span>}
        <div style={{marginLeft:"auto",display:"flex",alignItems:"center",gap:"10px"}}>
          <span style={{fontSize:"12px",color:C.textMut}}>{authUser.email}</span>
          <button onClick={onLogout} style={{background:"none",border:`1px solid ${C.border}`,
                                             borderRadius:"6px",color:C.textSec,fontSize:"12px",
                                             fontFamily:C.mono,padding:"4px 10px",cursor:"pointer"}}>
            sign out
          </button>
        </div>
      </div>

      <div style={{maxWidth:"680px",margin:"0 auto",padding:"32px 24px"}}>

        <div style={{marginBottom:"32px"}}>
          <h1 style={{fontSize:"26px",fontWeight:700,letterSpacing:"-0.03em",margin:"0 0 8px"}}>
            Find your best candidates.
          </h1>
          <p style={{fontSize:"14px",color:C.textSec,margin:0,lineHeight:"1.6"}}>
            Upload a job description, select candidates, and rank them by fit score.
          </p>
        </div>

        {/* Step 1 — JD */}
        <div style={{background:C.surface,border:`1px solid ${jdId?C.greenBord:C.border}`,
                     borderRadius:"12px",padding:"20px",marginBottom:"12px"}}>
          <div style={{fontSize:"10px",fontFamily:C.mono,color:C.textMut,
                       letterSpacing:"0.1em",marginBottom:"14px"}}>01 — JOB DESCRIPTION</div>
          {jdId?(
            <div style={{display:"flex",alignItems:"center",gap:"10px"}}>
              <span style={{color:C.green,fontSize:"16px"}}>✓</span>
              <span style={{fontSize:"13px",color:C.green,fontFamily:C.mono}}>
                {jdTitle} (id: {jdId})
              </span>
              <button onClick={()=>{setJdId(null);setJdTitle("");setResumes([]);
                                    setSelected([]);setResults(null);
                                    setTitle("");setCompany("");setJdFile(null)}}
                      style={{marginLeft:"auto",background:"none",border:`1px solid ${C.border}`,
                              borderRadius:"6px",color:C.textMut,fontSize:"11px",
                              fontFamily:C.mono,padding:"3px 8px",cursor:"pointer"}}>
                change
              </button>
            </div>
          ):(
            <>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",
                           gap:"8px",marginBottom:"10px"}}>
                <input placeholder="Job Title" value={title}
                       onChange={e=>setTitle(e.target.value)} style={inputStyle}/>
                <input placeholder="Company" value={company}
                       onChange={e=>setCompany(e.target.value)} style={inputStyle}/>
              </div>
              <label style={{display:"block",border:`1.5px dashed ${jdFile?C.greenBord:C.border}`,
                             borderRadius:"10px",padding:"18px",textAlign:"center",cursor:"pointer",
                             background:jdFile?C.greenBg:C.surfaceHi,transition:"all 0.2s"}}>
                <input type="file" accept="application/pdf"
                       onChange={e=>setJdFile(e.target.files[0])} style={{display:"none"}}/>
                {jdFile
                  ?<span style={{color:C.green,fontSize:"13px",fontFamily:C.mono}}>✓ {jdFile.name}</span>
                  :<><div style={{fontSize:"24px",marginBottom:"4px"}}>📄</div>
                     <div style={{color:C.textSec,fontSize:"13px"}}>Drop JD PDF here or click to browse</div></>
                }
              </label>
              <button onClick={handleJDUpload} disabled={uploading} style={{
                width:"100%",marginTop:"10px",padding:"10px",
                background:uploading?C.accentLo:C.accent,border:"none",borderRadius:"8px",
                color:"white",fontSize:"13px",fontWeight:600,
                cursor:uploading?"not-allowed":"pointer",transition:"all 0.15s",
              }}>
                {uploading?"Uploading...":"Upload JD + Load Candidates"}
              </button>
            </>
          )}
        </div>

        {/* Step 2 — Candidates */}
        {resumes.length>0&&(
          <div style={{background:C.surface,border:`1px solid ${C.border}`,
                       borderRadius:"12px",padding:"20px",marginBottom:"12px"}}>
            <div style={{display:"flex",justifyContent:"space-between",
                         alignItems:"center",marginBottom:"14px"}}>
              <div style={{fontSize:"10px",fontFamily:C.mono,color:C.textMut,letterSpacing:"0.1em"}}>
                02 — CANDIDATES
                <span style={{marginLeft:"8px",color:C.accent}}>
                  {selected.length}/{resumes.length} selected
                </span>
              </div>
              <button onClick={selectAll} style={{background:"none",border:`1px solid ${C.border}`,
                                                  borderRadius:"6px",color:C.textSec,fontSize:"11px",
                                                  fontFamily:C.mono,padding:"3px 8px",cursor:"pointer"}}>
                {selected.length===resumes.length?"deselect all":"select all"}
              </button>
            </div>
            <div style={{display:"flex",flexDirection:"column",gap:"6px"}}>
              {resumes.map(r=>{
                const isSel=selected.includes(r.resume_id)
                return(
                  <div key={r.resume_id} onClick={()=>toggleResume(r.resume_id)} style={{
                    display:"flex",justifyContent:"space-between",alignItems:"center",
                    padding:"10px 12px",background:isSel?C.indigoBg:C.surfaceHi,
                    border:`1px solid ${isSel?C.accent:C.border}`,
                    borderRadius:"8px",cursor:"pointer",transition:"all 0.15s",
                  }}>
                    <div>
                      <span style={{fontSize:"13px",fontWeight:500,color:C.textPri}}>
                        {r.candidate}
                      </span>
                      <span style={{fontSize:"11px",color:C.textMut,
                                    fontFamily:C.mono,marginLeft:"8px"}}>{r.filename}</span>
                    </div>
                    <div style={{width:"18px",height:"18px",borderRadius:"4px",flexShrink:0,
                                  border:`1.5px solid ${isSel?C.accent:C.borderHi}`,
                                  background:isSel?C.accent:"transparent",display:"flex",
                                  alignItems:"center",justifyContent:"center",
                                  fontSize:"11px",color:"white"}}>
                      {isSel&&"✓"}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {error&&(
          <div style={{background:C.redBg,border:`1px solid ${C.redBord}`,borderRadius:"8px",
                       padding:"10px 14px",fontSize:"13px",color:C.red,marginBottom:"12px"}}>
            {error}
          </div>
        )}

        {resumes.length>0&&(
          <button onClick={handleMatch} disabled={selected.length===0||matching} style={{
            width:"100%",padding:"14px",marginBottom:"24px",
            background:(selected.length===0||matching)?C.surfaceHi:C.accent,
            border:"none",borderRadius:"10px",
            color:(selected.length===0||matching)?C.textMut:"white",
            fontSize:"15px",fontWeight:600,
            cursor:(selected.length===0||matching)?"not-allowed":"pointer",
            transition:"all 0.2s",
            boxShadow:(selected.length===0||matching)?"none":`0 0 20px ${C.accent}44`,
          }}>
            {matching?"Ranking candidates..."
              :selected.length===0?"Select candidates to rank"
              :`Rank ${selected.length} candidate${selected.length>1?"s":""}`}
          </button>
        )}

        {/* Results */}
        {results&&(
          <div>
            <div style={{display:"flex",justifyContent:"space-between",
                         alignItems:"baseline",marginBottom:"16px"}}>
              <span style={{fontSize:"16px",fontWeight:600}}>Candidate Rankings</span>
              <span style={{fontSize:"11px",fontFamily:C.mono,color:C.textMut}}>
                {results.total_candidates} candidate{results.total_candidates>1?"s":""} · best fit first
              </span>
            </div>
            <div style={{display:"flex",flexDirection:"column",gap:"10px"}}>
              {results.candidates?.map((c,i)=>(
                <div key={c.resume_id}>
                  <div style={{background:C.surface,
                               border:`1px solid ${i===0?C.accent:detailId===c.resume_id?C.indigoBord:C.border}`,
                               borderRadius:"12px",padding:"18px",transition:"all 0.2s"}}>
                    <div style={{display:"flex",justifyContent:"space-between",
                                 alignItems:"flex-start",marginBottom:"14px"}}>
                      <div style={{flex:1,minWidth:0}}>
                        <div style={{display:"flex",alignItems:"center",gap:"8px",marginBottom:"3px"}}>
                          <span style={{fontSize:"10px",fontFamily:C.mono,color:C.textMut,
                                        border:`1px solid ${C.border}`,borderRadius:"4px",
                                        padding:"1px 6px"}}>#{i+1}</span>
                          {i===0&&<span style={{fontSize:"10px",background:C.accent,color:"white",
                                                borderRadius:"4px",padding:"1px 6px",
                                                fontFamily:C.mono}}>TOP MATCH</span>}
                          <span style={{fontWeight:600,fontSize:"14px"}}>{c.candidate}</span>
                        </div>
                        <div style={{fontSize:"11px",color:C.textMut,fontFamily:C.mono}}>
                          {c.filename} · {c.total_matched}/{c.jd_skill_count} skills
                        </div>
                      </div>
                      <span style={{fontSize:"26px",fontWeight:700,fontFamily:C.mono,
                                    color:scoreColor(c.final_score),
                                    textShadow:`0 0 12px ${scoreColor(c.final_score)}66`}}>
                        {c.final_score}%
                      </span>
                    </div>

                    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr 1fr",
                                 gap:"6px",marginBottom:"12px"}}>
                      {[{l:"EXACT",s:c.breakdown.exact_score,c:C.green},
                        {l:"SEMANTIC",s:c.breakdown.semantic_score,c:C.indigo},
                        {l:"EXPERIENCE",s:c.breakdown.exp_score,c:C.yellow},
                        {l:"CONTEXT",s:c.breakdown.ctx_score,c:C.accent}].map(x=>(
                        <div key={x.l} style={{background:C.surfaceHi,borderRadius:"6px",
                                               padding:"8px 6px",textAlign:"center"}}>
                          <div style={{fontSize:"9px",color:C.textMut,fontFamily:C.mono,
                                       letterSpacing:"0.08em",marginBottom:"3px"}}>{x.l}</div>
                          <div style={{fontSize:"13px",fontWeight:600,
                                       fontFamily:C.mono,color:x.c}}>{x.s}%</div>
                        </div>
                      ))}
                    </div>

                    {c.missing_skills?.length>0&&(
                      <div style={{marginBottom:"12px"}}>
                        <span style={{fontSize:"10px",color:C.textMut,fontFamily:C.mono}}>GAPS · </span>
                        <span style={{fontSize:"11px",color:C.red}}>
                          {c.missing_skills.join(", ")}
                        </span>
                      </div>
                    )}

                    <button onClick={()=>handleViewDetail(c.resume_id)} style={{
                      background:"none",border:`1px solid ${C.borderHi}`,borderRadius:"6px",
                      color:C.accentText,fontSize:"12px",fontFamily:C.mono,
                      padding:"5px 12px",cursor:"pointer",transition:"all 0.15s",
                    }}
                      onMouseEnter={e=>e.target.style.borderColor=C.accent}
                      onMouseLeave={e=>e.target.style.borderColor=C.borderHi}>
                      {detailId===c.resume_id?"close breakdown ×":"full breakdown →"}
                    </button>
                  </div>

                  {detailId===c.resume_id&&detailData&&(
                    <DetailPanel result={detailData}
                                 onClose={()=>{setDetailId(null);setDetailData(null)}}/>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}