import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useInterviewStore } from "../store/useInterviewStore";

export default function Setup() {
  const nav = useNavigate();
  const initFromSetup = useInterviewStore((s) => s.initFromSetup);

  const [name, setName] = useState("");
  const [job, setJob] = useState("Software Developer");
  const [mpq, setMpq] = useState(1);
  const [total, setTotal] = useState(1);

  function onSubmit(e) {
    e.preventDefault();
    const minutesPerQuestion = Math.max(1, mpq | 0);
    const totalTime = Math.max(1, total | 0);
    const numQuestions = Math.max(1, Math.floor(totalTime / minutesPerQuestion));
    initFromSetup({
      name,
      jobDescription: job,
      minutesPerQuestion,
      totalTime,
      numQuestions,
    });
    nav("/waiting");
  }

  return (
    <div className="app-wrap">
      <div className="card">
        <h1>Interview Setup</h1>
        <p className="muted">Minimum is 1 minute and 1 question.</p>
        <form onSubmit={onSubmit} className="form-grid" style={{ display: "grid", gap: 12 }}>
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>

          <label>
            Job Description
            <textarea value={job} onChange={(e) => setJob(e.target.value)} rows={6} required />
          </label>

          <div className="row">
            <label>
              Minutes per question
              <input
                type="number"
                value={mpq}
                onChange={(e) => setMpq(Math.max(1, +e.target.value))}
                min={1}
              />
            </label>

            <label>
              Total time (minutes)
              <input
                type="number"
                value={total}
                onChange={(e) => setTotal(Math.max(1, +e.target.value))}
                min={1}
              />
            </label>
          </div>

          <button className="btn primary" type="submit">
            Continue
          </button>
        </form>
      </div>
    </div>
  );
}
