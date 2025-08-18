import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useInterviewStore } from "../store/useInterviewStore";
import { useRecorder } from "../hooks/useRecorder";
import {
  generateQuestion,
  uploadSpeechBlob,
  completeSession,
  sendVideoFrame,
  gradeAnswer,
  getPostureSummary, // must call GET /api/analysis/posture-summary/:sessionId
} from "../lib/api";

const MINI_REVIEW_MS = 1800; // quick “analyzing…” pause

export default function Interview() {
  const nav = useNavigate();
  const {
    jobDescription,
    minutesPerQuestion,
    asked,
    addQuestion,
    addTranscript,
    sessionId: storeSessionId,
  } = useInterviewStore();

  // pick up from store or localStorage
  const [sessionId] = useState(() => {
    const sid = storeSessionId || localStorage.getItem("session_id");
    return sid || "";
  });

  useEffect(() => {
    if (!sessionId) nav("/waiting");
  }, [sessionId, nav]);

  const [current, setCurrent] = useState("");
  const [hint, setHint] = useState("");
  const [busy, setBusy] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [miniReview, setMiniReview] = useState(null); // {summary, metrics, suggestions}

  // video preview + frame push
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const frameTimer = useRef(null);

  // per-question timer (auto-stop)
  const qTimer = useRef(null);
  const secondsPerQuestion = Math.max(60, (minutesPerQuestion || 1) * 60);

  // allow awaiting until onBlob finishes
  const uploadResolver = useRef(null);

  // ----- Recorder: sends blob -> speech-analysis -> grade-answer -----
  const { start, stop, recording, error } = useRecorder({
    onBlob: async (blob, mime) => {
      try {
        // figure out a reasonable extension for the filename
        const ext = mime?.includes("webm")
          ? "webm"
          : mime?.includes("mp4") || mime?.includes("mpeg") || mime?.includes("m4a")
          ? "m4a"
          : "wav";

        // use 1-based question number
        const questionNumber = (asked?.length || 0) + 1;

        // 1) upload speech for transcription + basic analysis (fillers, duration…)
        const up = await uploadSpeechBlob(
          blob,
          `answer_q${questionNumber}.wav`,
          sessionId,
          questionNumber
        );

        const transcript =
          up?.analysis?.transcript || up?.text || up?.transcript || "";
        const confidence =
          up?.analysis?.confidence ?? up?.confidence ?? 0.8;
        const duration =
          up?.analysis?.duration ?? up?.duration ?? 0;
        const fillers = {
          um: up?.analysis?.filler_count?.um ?? 0,
          uh: up?.analysis?.filler_count?.uh ?? 0,
          like: up?.analysis?.filler_count?.like ?? 0,
        };

        // store transcript for history
        addTranscript({
          question: current,
          responseText: transcript,
          duration,
          confidence,
          timestamp: new Date().toISOString(),
        });

        // brief loader while grading
        setAnalyzing(true);

        // 2) grade with Gemini (backend wraps it); NOTE: camelCase keys to avoid 422
        const grade = await gradeAnswer({
          sessionId,
          questionText: current,
          transcript,
          jobDescription:
            jobDescription || localStorage.getItem("job_description") || "",
          fillerCounts: fillers,
          durationSeconds: duration,
        });

        // 3) snapshot posture distribution and convert to %
        let posturePercent = null;
        try {
          const posture = await getPostureSummary(sessionId);
          const dist = posture?.distribution || {};
          const total = Object.values(dist).reduce((a, b) => a + b, 0);
          if (total > 0) {
            posturePercent = Object.fromEntries(
              Object.entries(dist).map(([k, v]) => [k, Math.round((v * 100) / total)])
            );
          }
        } catch {
          // ignore posture errors
        }

        setMiniReview({
          summary:
            grade?.summary || "Here’s how to improve your next answer.",
          metrics: {
            ...(grade?.metrics || {}),
            posture: posturePercent || null,
          },
          suggestions: grade?.suggestions || [],
        });

        // hold the mini review briefly
        await new Promise((r) => setTimeout(r, MINI_REVIEW_MS));
      } catch (e) {
        console.warn("analyze error", e);
      } finally {
        setAnalyzing(false);
        if (typeof uploadResolver.current === "function") {
          uploadResolver.current(); // release waiter
          uploadResolver.current = null;
        }
      }
    },
  });

  // ----- Camera init + push frames to backend -----
  useEffect(() => {
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true, // recorder may also request audio; keeping this true simplifies permissions UX
          video: { width: 640, height: 360 },
        });
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;

        // ~1 fps is enough for posture stats; increase if you want smoother stats
        frameTimer.current = setInterval(async () => {
          if (!canvasRef.current || !videoRef.current || !sessionId) return;
          const v = videoRef.current;
          if (!v.videoWidth) return; // not ready yet

          const c = canvasRef.current;
          const w = (c.width = v.videoWidth || 640);
          const h = (c.height = v.videoHeight || 360);
          const ctx = c.getContext("2d");
          ctx.drawImage(v, 0, 0, w, h);

          const blob = await new Promise((res) => c.toBlob(res, "image/jpeg", 0.75));
          if (blob) {
            // soft-fail inside API helper
            await sendVideoFrame(sessionId, blob);
          }
        }, 1000);
      } catch (e) {
        console.error("video init failed", e);
      }
    })();

    return () => {
      if (frameTimer.current) clearInterval(frameTimer.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [sessionId]);

  // ----- Get first question and auto-start recording -----
  useEffect(() => {
    (async () => {
      if (!current && sessionId) {
        await fetchNextQuestionAndRecord();
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // auto-stop after allotted time
  useEffect(() => {
    if (!recording) return;
    clearTimeout(qTimer.current);
    qTimer.current = setTimeout(() => {
      onNext();
    }, secondsPerQuestion * 1000);
    return () => clearTimeout(qTimer.current);
  }, [recording, secondsPerQuestion]);

  async function fetchNextQuestionAndRecord() {
    setMiniReview(null);
    setBusy(true);
    try {
      const jd =
        jobDescription ||
        localStorage.getItem("job_description") ||
        "Software Developer";
      const res = await generateQuestion({
        job_description: jd,
        num_questions: 1,
      });
      const q = res?.question || "Tell me about yourself.";
      const h = res?.hint || "Use STAR.";

      addQuestion(q);
      setCurrent(q);
      setHint(h);

      // small delay to ensure devices are hot before starting
      setTimeout(() => start?.(), 100);
    } catch (e) {
      console.error("generateQuestion failed:", e);
      const q = "Tell me about yourself.";
      addQuestion(q);
      setCurrent(q);
      setHint("Use STAR.");
      setTimeout(() => start?.(), 100);
    } finally {
      setBusy(false);
    }
  }

  function stopAndAnalyze() {
    return new Promise((resolve) => {
      uploadResolver.current = resolve;
      stop?.(); // triggers onBlob -> upload -> grade -> miniReview
    });
  }

  async function onNext() {
    if (!recording) {
      await fetchNextQuestionAndRecord();
      return;
    }
    await stopAndAnalyze();
    await fetchNextQuestionAndRecord();
  }

  async function onEnd() {
    // ensure last answer is captured
    if (recording) await stopAndAnalyze();

    try {
      await completeSession(sessionId);
    } catch (e) {
      console.warn("completeSession failed; continuing to feedback", e?.message);
    }

    localStorage.setItem("last_session_id", sessionId);
    // support both styles of feedback routes
    try {
      nav(`/feedback/${sessionId}`);
    } catch {
      nav("/feedback");
    }
  }

  return (
    <div className="app-wrap">
      <div className="toolbar">
        <div className="row">
          <span className={`pill ${recording ? "live" : ""}`}>
            <span className={`dot ${recording ? "live" : ""}`} />
            {recording ? "Recording" : analyzing ? "Analyzing…" : "Idle"}
          </span>
          <span className="pill">
            Session: {sessionId ? `${sessionId.slice(0, 8)}…` : "—"}
          </span>
        </div>
        <div className="row">
          <button className="btn danger" onClick={onEnd} disabled={busy || analyzing}>
            End Interview
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Interview</h2>

        <div className="row" style={{ alignItems: "flex-start" }}>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="preview"
            style={{ maxWidth: 360, borderRadius: 12 }}
          />

          <div style={{ flex: 1, position: "relative" }}>
            <div className="question">{current || "Loading question…"}</div>
            {hint && <span className="hint">Hint: {hint}</span>}

            <div style={{ height: 12 }} />

            <div className="row">
              <button
                className="btn primary"
                onClick={onNext}
                disabled={busy || analyzing}
                title={analyzing ? "Analyzing…" : "Finish and go to the next question"}
              >
                {analyzing ? "Analyzing…" : "Next Question"}
              </button>
            </div>

            {/* Loader overlay */}
            {analyzing && (
              <div className="overlay">
                <div className="loader" />
                <div style={{ marginTop: 8 }}>Analyzing your answer…</div>
              </div>
            )}

            {/* Mini review after each answer */}
            {!!miniReview && !analyzing && (
              <div className="mini-review">
                <div className="mr-title">Quick Review</div>
                <div className="mr-summary">{miniReview.summary}</div>
                <div className="mr-grid">
                  <div>
                    <b>Content</b>{" "}
                    {miniReview.metrics?.content_score ?? "-"} / 100
                  </div>
                  <div>
                    <b>Relevance</b>{" "}
                    {miniReview.metrics?.relevance ?? "-"} / 100
                  </div>
                  <div>
                    <b>Clarity</b>{" "}
                    {miniReview.metrics?.clarity ?? "-"} / 100
                  </div>
                  <div>
                    <b>Structure</b>{" "}
                    {miniReview.metrics?.structure ?? "-"} / 100
                  </div>
                  <div>
                    <b>Length OK</b>{" "}
                    {String(miniReview.metrics?.length_ok ?? false)}
                  </div>
                  <div>
                    <b>Pace</b> {miniReview.metrics?.pace ?? "-"}
                  </div>
                </div>

                {miniReview.metrics?.posture && (
                  <div className="mr-posture">
                    <b>Posture snapshot:</b>{" "}
                    {Object.entries(miniReview.metrics.posture)
                      .map(([k, v]) => `${k} ${v}%`)
                      .join(" • ")}
                  </div>
                )}

                {miniReview.suggestions?.length ? (
                  <ul className="mr-list">
                    {miniReview.suggestions.slice(0, 3).map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            )}
          </div>
        </div>

        {error && <p className="err">{error}</p>}
      </div>

      <canvas ref={canvasRef} style={{ display: "none" }} />
    </div>
  );
}
