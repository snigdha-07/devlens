import { useState } from "react"

const C={
  bg:"#0a0f1e",surface:"#111827",surfaceHi:"#1a2235",border:"#1e2d45",
  accent:"#6366f1",accentLo:"#312e81",textPri:"#f1f5f9",textSec:"#94a3b8",textMut:"#4b5563",
  red:"#ef4444",redBg:"#1f0707",redBord:"#7f1d1d",
  mono:"'JetBrains Mono', monospace",display:"'Inter', sans-serif",
}

export default function AuthPage({ onAuth }) {
  const [mode,setMode]=useState("login")
  const [email,setEmail]=useState("")
  const [password,setPassword]=useState("")
  const [role,setRole]=useState("student")
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState("")

  const handleSubmit=async()=>{
    if(!email||!password){setError("Email and password are required");return}
    setError("");setLoading(true)
    const endpoint=mode==="login"?"/login":"/register"
    const body=mode==="login"?{email,password}:{email,password,role}
    try{
      const res=await fetch(`http://127.0.0.1:8000${endpoint}`,{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)
      })
      const data=await res.json()
      if(!res.ok){setError(data.detail||"Something went wrong");return}
      localStorage.setItem("token",data.access_token)
      localStorage.setItem("user_id",data.user_id)
      localStorage.setItem("email",data.email)
      localStorage.setItem("role",data.role)
      onAuth(data)
    }catch{setError("Could not reach server. Is the backend running?")}
    finally{setLoading(false)}
  }

  const inputStyle={
    width:"100%",padding:"11px 14px",boxSizing:"border-box",
    background:"#1a2235",border:"1px solid #1e2d45",borderRadius:"8px",
    color:"#f1f5f9",fontSize:"14px",fontFamily:C.display,outline:"none",
  }

  return(
    <div style={{minHeight:"100vh",background:C.bg,display:"flex",alignItems:"center",
                 justifyContent:"center",fontFamily:C.display,padding:"24px"}}>
      <div style={{width:"100%",maxWidth:"380px",background:C.surface,
                   border:`1px solid ${C.border}`,borderRadius:"16px",padding:"36px 32px"}}>

        <div style={{fontFamily:C.mono,fontWeight:600,fontSize:"18px",
                     color:C.textPri,marginBottom:"28px",letterSpacing:"-0.02em"}}>
          dev<span style={{color:C.accent}}>lens</span>
        </div>

        <h2 style={{margin:"0 0 6px",fontSize:"20px",fontWeight:700,color:C.textPri}}>
          {mode==="login"?"Sign in":"Create account"}
        </h2>
        <p style={{margin:"0 0 24px",fontSize:"13px",color:C.textSec}}>
          {mode==="login"?"Welcome back.":"Start matching resumes to jobs."}
        </p>

        {mode==="register"&&(
          <div style={{marginBottom:"12px"}}>
            <div style={{fontSize:"10px",fontFamily:C.mono,color:C.textMut,
                         letterSpacing:"0.1em",marginBottom:"8px"}}>I AM A</div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"8px"}}>
              {[{value:"student",icon:"👨‍🎓",label:"Student"},
                {value:"recruiter",icon:"💼",label:"Recruiter"}].map(r=>(
                <button key={r.value} onClick={()=>setRole(r.value)} style={{
                  padding:"12px 8px",
                  background:role===r.value?C.accentLo:C.surfaceHi,
                  border:`1.5px solid ${role===r.value?C.accent:C.border}`,
                  borderRadius:"8px",color:role===r.value?"#c7d2fe":C.textSec,
                  fontSize:"13px",fontFamily:C.display,
                  fontWeight:role===r.value?600:400,cursor:"pointer",
                  transition:"all 0.15s",display:"flex",flexDirection:"column",
                  alignItems:"center",gap:"4px",
                }}>
                  <span style={{fontSize:"20px"}}>{r.icon}</span>
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div style={{display:"flex",flexDirection:"column",gap:"10px",marginBottom:"16px"}}>
          <input type="email" placeholder="Email address" value={email}
                 onChange={e=>setEmail(e.target.value)}
                 onKeyDown={e=>e.key==="Enter"&&handleSubmit()} style={inputStyle}/>
          <input type="password" placeholder="Password" value={password}
                 onChange={e=>setPassword(e.target.value)}
                 onKeyDown={e=>e.key==="Enter"&&handleSubmit()} style={inputStyle}/>
        </div>

        {error&&(
          <div style={{background:C.redBg,border:`1px solid ${C.redBord}`,borderRadius:"8px",
                       padding:"9px 12px",fontSize:"13px",color:C.red,marginBottom:"14px"}}>
            {error}
          </div>
        )}

        <button onClick={handleSubmit} disabled={loading} style={{
          width:"100%",padding:"12px",background:loading?C.accentLo:C.accent,
          border:"none",borderRadius:"8px",color:"white",fontSize:"14px",fontWeight:600,
          cursor:loading?"not-allowed":"pointer",marginBottom:"20px",
          boxShadow:loading?"none":`0 0 16px ${C.accent}44`,transition:"all 0.15s",
        }}>
          {loading
            ?(mode==="login"?"Signing in...":"Creating account...")
            :(mode==="login"?"Sign in":"Create account")}
        </button>

        <p style={{textAlign:"center",fontSize:"13px",color:C.textSec,margin:0}}>
          {mode==="login"?"No account? ":"Already have an account? "}
          <span onClick={()=>{setMode(mode==="login"?"register":"login");setError("")}}
                style={{color:"#818cf8",cursor:"pointer",textDecoration:"underline"}}>
            {mode==="login"?"Sign up":"Sign in"}
          </span>
        </p>
      </div>
    </div>
  )
}