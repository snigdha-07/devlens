import { useState } from "react"
import { uploadResume, uploadJD, matchBatch } from "../api"
import { useNavigate } from "react-router-dom"

export default function UploadPage() {
    const navigate   = useNavigate()
    const [resumeId, setResumeId]       = useState(null)
    const [resumeName, setResumeName]   = useState("")
    const [jdIds, setJdIds]             = useState([])
    const [jdList, setJdList]           = useState([])   // {id, title, company}
    const [matching, setMatching]       = useState(false)
    const [error, setError]             = useState("")

    // JD form state
    const [jdTitle, setJdTitle]     = useState("")
    const [jdCompany, setJdCompany] = useState("")
    const [jdFile, setJdFile]       = useState(null)

    const handleResumeUpload = async (e) => {
        const file = e.target.files[0]
        if (!file) return
        const data = await uploadResume(file)
        setResumeId(data["resume id"])
        setResumeName(file.name)
    }

    const handleJDUpload = async () => {
        if (!jdTitle || !jdCompany || !jdFile) {
            setError("Fill all JD fields")
            return
        }
        setError("")
        const data = await uploadJD(jdTitle, jdCompany, jdFile)
        setJdIds(prev => [...prev, data.jd_id])
        setJdList(prev => [...prev, {
            id:      data.jd_id,
            title:   jdTitle,
            company: jdCompany
        }])
        setJdTitle("")
        setJdCompany("")
        setJdFile(null)
    }

    const handleMatch = async () => {
        if (!resumeId || jdIds.length === 0) {
            setError("Upload a resume and at least one JD first")
            return
        }
        setMatching(true)
        const results = await matchBatch(resumeId, jdIds)
        setMatching(false)
        navigate("/results", { state: { results, resumeId } })
    }

    return (
        <div className="max-w-2xl mx-auto p-6 space-y-8">
            <h1 className="text-2xl font-bold">DevLens</h1>

            {/* Resume Upload */}
            <section className="border rounded-lg p-4 space-y-3">
                <h2 className="font-semibold text-lg">Resume</h2>
                {resumeId ? (
                    <p className="text-green-600">
                        ✓ {resumeName} uploaded (id: {resumeId})
                    </p>
                ) : (
                    <input
                        type="file"
                        accept=".pdf"
                        onChange={handleResumeUpload}
                        className="block"
                    />
                )}
            </section>

            {/* JD Upload */}
            <section className="border rounded-lg p-4 space-y-3">
                <h2 className="font-semibold text-lg">Job Descriptions</h2>

                <input
                    placeholder="Job Title"
                    value={jdTitle}
                    onChange={e => setJdTitle(e.target.value)}
                    className="border rounded px-3 py-1 w-full"
                />
                <input
                    placeholder="Company"
                    value={jdCompany}
                    onChange={e => setJdCompany(e.target.value)}
                    className="border rounded px-3 py-1 w-full"
                />
                <input
                    type="file"
                    accept=".pdf"
                    onChange={e => setJdFile(e.target.files[0])}
                    className="block"
                />
                <button
                    onClick={handleJDUpload}
                    className="bg-blue-500 text-white px-4 py-2 rounded"
                >
                    Add JD
                </button>

                {/* JD list */}
                {jdList.length > 0 && (
                    <ul className="mt-3 space-y-1">
                        {jdList.map(jd => (
                            <li key={jd.id} className="text-green-600 text-sm">
                                ✓ {jd.title} — {jd.company} (id: {jd.id})
                            </li>
                        ))}
                    </ul>
                )}
            </section>

            {error && <p className="text-red-500 text-sm">{error}</p>}

            {/* Match Button */}
            <button
                onClick={handleMatch}
                disabled={!resumeId || jdIds.length === 0 || matching}
                className="w-full bg-green-600 text-white py-3 rounded-lg 
                           font-semibold text-lg disabled:opacity-40"
            >
                {matching ? "Matching..." : `Match Resume against ${jdIds.length} JD(s)`}
            </button>
        </div>
    )
}