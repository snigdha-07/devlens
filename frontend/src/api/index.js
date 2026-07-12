const BASE = "http://localhost:8000"

export const uploadResume = async (file) => {
    const form = new FormData()
    form.append("file", file)
    const res = await fetch(`${BASE}/upload-resume`, { method: "POST", body: form })
    return res.json()
}

export const uploadJD = async (title, company, file) => {
    const form = new FormData()
    form.append("title", title)
    form.append("company", company)
    form.append("file", file)
    const res = await fetch(`${BASE}/add-jd`, { method: "POST", body: form })
    return res.json()
}

export const matchBatch = async (resume_id, jd_ids) => {
    const res = await fetch(`${BASE}/match/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume_id, jd_ids })
    })
    return res.json()
}

export const getMatchDetail = async (resume_id, jd_id) => {
    const res = await fetch(`${BASE}/match/${resume_id}/${jd_id}`)
    return res.json()
}