import { useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { getMatchDetail } from "../api"

export default function ResultsPage() {
    const { state }        = useLocation()
    const navigate         = useNavigate()
    const { results }      = state || {}
    const [detail, setDetail] = useState(null)
    const [loading, setLoading] = useState(false)

    const handleViewDetail = async (resumeId, jdId) => {
        setLoading(true)
        const data = await getMatchDetail(resumeId, jdId)
        setDetail(data)
        setLoading(false)
    }

    const scoreColor = (score) => {
        if (score >= 70) return "text-green-600"
        if (score >= 50) return "text-yellow-500"
        return "text-red-500"
    }

    if (!results) return <p>No results found.</p>

    return (
        <div className="max-w-3xl mx-auto p-6 space-y-6">
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold">Match Results</h1>
                <button
                    onClick={() => navigate("/")}
                    className="text-sm text-blue-500 underline"
                >
                    ← Back
                </button>
            </div>

            {/* Ranked JD list */}
            <div className="space-y-4">
                {results.results.map((r, i) => (
                    <div key={r.jd_id} className="border rounded-lg p-4 space-y-3">

                        {/* Header */}
                        <div className="flex justify-between items-start">
                            <div>
                                <span className="text-gray-400 text-sm mr-2">
                                    #{i + 1}
                                </span>
                                <span className="font-semibold">{r.jd_title}</span>
                                <span className="text-gray-500 text-sm ml-2">
                                    {r.company}
                                </span>
                            </div>
                            <div className="text-right">
                                <span className={`text-2xl font-bold ${scoreColor(r.final_score)}`}>
                                    {r.final_score}%
                                </span>
                                <p className="text-xs text-gray-400">
                                    {r.total_matched}/{r.jd_skill_count} skills
                                </p>
                            </div>
                        </div>

                        {/* Layer breakdown */}
                        <div className="grid grid-cols-4 gap-2 text-center text-sm">
                            {[
                                { label: "Exact",      score: r.breakdown.exact_score },
                                { label: "Semantic",   score: r.breakdown.semantic_score },
                                { label: "Experience", score: r.breakdown.exp_score },
                                { label: "Context",    score: r.breakdown.ctx_score },
                            ].map(layer => (
                                <div key={layer.label} className="bg-gray-50 rounded p-2">
                                    <p className="text-gray-500 text-xs">{layer.label}</p>
                                    <p className="font-semibold">{layer.score}%</p>
                                </div>
                            ))}
                        </div>

                        {/* Missing skills */}
                        {r.missing_skills?.length > 0 && (
                            <div>
                                <p className="text-sm text-gray-500 mb-1">Missing skills:</p>
                                <div className="flex flex-wrap gap-1">
                                    {r.missing_skills.map(s => (
                                        <span key={s}
                                            className="bg-red-50 text-red-600 
                                                       text-xs px-2 py-0.5 rounded-full border 
                                                       border-red-200">
                                            {s}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* View detail button */}
                        <button
                            onClick={() => handleViewDetail(results.resume_id, r.jd_id)}
                            className="text-sm text-blue-500 underline"
                        >
                            View full breakdown →
                        </button>
                    </div>
                ))}
            </div>

            {/* Detail panel */}
            {loading && <p className="text-gray-400">Loading detail...</p>}
            {detail && (
                <div className="border rounded-lg p-4 space-y-4 bg-gray-50">
                    <h2 className="font-semibold text-lg">Full Breakdown</h2>

                    {/* Experience evidence */}
                    {detail.experience_matches?.length > 0 && (
                        <div>
                            <p className="font-medium text-sm mb-2">Experience Evidence</p>
                            <ul className="space-y-2">
                                {detail.experience_matches.map((m, i) => (
                                    <li key={i} className="bg-white rounded p-2 text-sm border">
                                        <span className="font-medium text-blue-600">
                                            {m.jd_skill}
                                        </span>
                                        <p className="text-gray-500 mt-1 text-xs">
                                            "{m.resume_evidence}"
                                        </p>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Extra skills */}
                    {detail.extra_skills?.length > 0 && (
                        <div>
                            <p className="font-medium text-sm mb-2">
                                Bonus Skills (not in JD)
                            </p>
                            <div className="flex flex-wrap gap-1">
                                {detail.extra_skills.map(s => (
                                    <span key={s}
                                        className="bg-blue-50 text-blue-600 text-xs 
                                                   px-2 py-0.5 rounded-full border border-blue-200">
                                        {s}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}