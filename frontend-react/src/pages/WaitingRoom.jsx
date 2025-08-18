import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useInterviewStore } from "../store/useInterviewStore";
import { createSession, startSession } from "../lib/api";

export default function WaitingRoom() {
  const nav = useNavigate();
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const { name, jobDescription, minutesPerQuestion, totalTime, numQuestions } =
    useInterviewStore();

  const [micOn, setMicOn] = useState(true);
  const [camOn, setCamOn] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: { width: 640, height: 360 },
        });
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
      } catch (e) {
        console.error("getUserMedia failed", e);
      }
    })();
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  useEffect(() => {
    const s = streamRef.current;
    if (!s) return;
    s.getAudioTracks().forEach((t) => (t.enabled = micOn));
    s.getVideoTracks().forEach((t) => (t.enabled = camOn));
  }, [micOn, camOn]);

  async function startInterview() {
    setBusy(true);
    try {
      const payload = {
        name: name || "Candidate",
        job_description: jobDescription || "Software Developer",
        minutes_per_question: Math.max(1, minutesPerQuestion || 1),
        total_time: Math.max(1, totalTime || 1),
      };
      const session = await createSession(payload);
      await startSession(session.session_id);

      localStorage.setItem("session_id", session.session_id);
      localStorage.setItem("job_description", payload.job_description);

      nav("/interview");
    } catch (e) {
      console.error(e);
      alert("Could not start session");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-wrap">
      <div className="card">
        <h2 style={{ marginBottom: 12 }}>Waiting Room</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Check your mic & camera. You can toggle them before you begin.
        </p>

        <video ref={videoRef} autoPlay playsInline muted className="preview" />

        <div style={{ height: 12 }} />

        <div className="row">
          <label className="switch">
            <input
              type="checkbox"
              checked={micOn}
              onChange={() => setMicOn((v) => !v)}
            />
            Mic {micOn ? "On" : "Off"}
          </label>

          <label className="switch">
            <input
              type="checkbox"
              checked={camOn}
              onChange={() => setCamOn((v) => !v)}
            />
            Camera {camOn ? "On" : "Off"}
          </label>
        </div>

        <ul className="kv">
          <li>
            <span>Role</span>
            <b>
              {(jobDescription || "Software Developer").slice(0, 60)}
              {(jobDescription || "").length > 60 ? "…" : ""}
            </b>
          </li>
          <li>
            <span>Minutes per question</span>
            <b>{minutesPerQuestion}</b>
          </li>
          <li>
            <span>Total time</span>
            <b>{totalTime} min</b>
          </li>
          <li>
            <span>Questions</span>
            <b>{numQuestions}</b>
          </li>
        </ul>

        <div className="row">
          <button className="btn primary" onClick={startInterview} disabled={busy}>
            Start Interview
          </button>
          <button
            className="btn ghost"
            onClick={() => {
              streamRef.current?.getTracks().forEach((t) => t.stop());
              navigator.mediaDevices
                .getUserMedia({ audio: true, video: true })
                .then((s) => {
                  streamRef.current = s;
                  if (videoRef.current) videoRef.current.srcObject = s;
                })
                .catch((e) => console.error(e));
            }}
          >
            Recheck Devices
          </button>
        </div>
      </div>
    </div>
  );
}
