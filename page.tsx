"use client";
import { useState } from "react";

export default function App() {
  const [data, setData] = useState({ jd: "", resume: "" });
  const [ui, setUi] = useState({ question: "", state: null as any, report: null as any, loading: false });
  const [ans, setAns] = useState("");

  async function call(path: string, body: any) {
    setUi(prev => ({ ...prev, loading: true }));
    try {
      const res = await fetch(`http://localhost:8000/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const result = await res.json();
      if (result.learning_plan) {
        setUi({ question: "", state: result.result, report: result.learning_plan, loading: false });
      } else {
        setUi({ ...ui, question: result.question, state: result.state, loading: false });
      }
    } catch (e) {
      alert("Error: Backend offline.");
      setUi(prev => ({ ...prev, loading: false }));
    }
  }

  return (
    <div style={{ padding: 40, maxWidth: 1000, margin: "auto", fontFamily: "system-ui" }}>
      {/* 1. SETUP VIEW */}
      {!ui.question && !ui.report && (
        <div style={{ display: "grid", gap: 20 }}>
          <h1>AI-Powered Skill Assessment & Personalised Learning Plan Agent</h1>
          <p>Go beyond the resume. Validate real proficiency and bridge technical gaps.</p>
          <textarea placeholder="Paste Job Description" rows={8} onChange={e => setData({...data, jd: e.target.value})} />
          <textarea placeholder="Paste Resume Text" rows={8} onChange={e => setData({...data, resume: e.target.value})} />
          <button style={{ padding: 15, background: "#0070f3", color: "white", border: "none", cursor: "pointer", fontWeight: "bold" }} onClick={() => call("start", { job_description: data.jd, resume: data.resume })} disabled={ui.loading}>
            {ui.loading ? "Analyzing..." : "Start Assessment"}
          </button>
        </div>
      )}

      {/* 2. QUESTION VIEW */}
      {ui.question && (
        <div style={{ background: "#f8f9fa", padding: 30, borderRadius: 12, border: "1px solid #dee2e6" }}>
          <p style={{ color: "#0070f3", fontWeight: "bold" }}>Auditing: {ui.state.skills[ui.state.current_idx].name}</p>
          <h2 style={{ margin: "20px 0" }}>{ui.question}</h2>
          <textarea style={{ width: "100%", padding: 10, borderRadius: 8 }} rows={4} value={ans} onChange={e => setAns(e.target.value)} />
          <div style={{ marginTop: 20, display: "flex", gap: 10 }}>
            <button style={{ padding: "12px 30px" }} onClick={() => { call("answer", { answer: ans, state: ui.state }); setAns(""); }}>Submit Answer</button>
            <button style={{ padding: "12px 20px", background: "#6c757d", color: "white", border: "none" }} onClick={() => { call("answer", { answer: "I don't know", state: ui.state }); setAns(""); }}>I don't know</button>
          </div>
        </div>
      )}

      {/* 3. FINAL REPORT VIEW */}
      {ui.report && (
        <div style={{ display: "grid", gap: 30 }}>
          <div style={{ background: "#343a40", color: "white", padding: 25, borderRadius: 12, textAlign: "center" }}>
             <h1 style={{ margin: 0, fontSize: "2.5rem" }}>{ui.report.weighted_total_score} / 5.0</h1>
             <p style={{ opacity: 0.8 }}>Final Weighted Evaluation Score</p>
          </div>

          <div style={{ overflowX: "auto" }}>
            <h3>Assessment Results</h3>
            <table border={1} style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
              <thead style={{ background: "#f1f3f5" }}>
                <tr><th>Skill</th><th>Importance</th><th>Initial</th><th>Final</th><th>Reasoning</th></tr>
              </thead>
              <tbody>
                {ui.state.skills.map((s: any, i: number) => (
                  <tr key={i}>
                    <td style={{ padding: 12 }}><b>{s.name}</b></td>
                    <td align="center">{s.importance}</td>
                    <td align="center">{s.initial_score}</td>
                    <td align="center" style={{ fontWeight: "bold", color: s.final_score <= 1 ? "#dc3545" : "#28a745" }}>{s.final_score.toFixed(1)}</td>
                    <td style={{ padding: 12, fontSize: "0.85rem" }}>{s.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ background: "#e7f3ff", padding: 30, borderRadius: 15, border: "1px solid #b8daff" }}>
            <h3 style={{ marginTop: 0 }}>🛠 Personalised Learning Plan</h3>
            <p style={{ marginBottom: 20 }}>{ui.report.overall_summary}</p>
            {ui.report.gaps.map((gap: any, i: number) => (
              <div key={i} style={{ marginBottom: 25, background: "white", padding: 20, borderRadius: 10 }}>
                <h4 style={{ color: "#0070f3", margin: 0 }}>{gap.skill_name}</h4>
                <p><b>Gap:</b> {gap.gap_description}</p>
                <ul>{gap.resources.map((res: any, j: number) => (
                  <li key={j}><a href={res.url} target="_blank">{res.title}</a> — <b>{res.time_estimate}</b></li>
                ))}</ul>
              </div>
            ))}
            <button onClick={() => window.location.reload()} style={{ width: "100%", padding: 15 }}>Restart</button>
          </div>
        </div>
      )}
    </div>
  );
}