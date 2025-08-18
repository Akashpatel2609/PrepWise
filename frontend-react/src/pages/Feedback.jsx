// src/pages/Feedback.jsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { fetchReport } from "../lib/api";
import Chart from "chart.js/auto";

export default function Feedback() {
  const params = useParams();
  const nav = useNavigate();
  const sessionId = params.sessionId || localStorage.getItem("last_session_id");

  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  // chart refs
  const fillerRef = useRef(null);
  const postureRef = useRef(null);
  const radarRef = useRef(null);
  const chartsRef = useRef({});

  useEffect(() => {
    if (!sessionId) {
      nav("/waiting");
      return;
    }
    (async () => {
      try {
        const r = await fetchReport(sessionId);
        setData(r);
      } catch (e) {
        console.error(e);
        setErr("Report not found yet. Try ending the interview again.");
      }
    })();
  }, [sessionId, nav]);

  // derive safe values
  const fillerTotals = useMemo(() => {
    const fw = data?.filler_totals || {};
    return {
      um: Number(fw.um || 0),
      uh: Number(fw.uh || 0),
      like: Number(fw.like || 0),
    };
  }, [data]);

  const postureDist = useMemo(() => {
    const arr = Array.isArray(data?.posture_summary) ? data.posture_summary : [];
    const labels = arr.map((x) => x.label);
    const counts = arr.map((x) => x.count);
    return {labels, counts};
  }, [data]);

  const radarMetrics = useMemo(() => {
    return {
      labels: ["Overall", "Speech", "Posture", "Content", "Confidence"],
      values: [
        Number(data?.overall_score ?? 0),
        Number(data?.speech_score ?? 0),
        Number(data?.posture_score ?? 0),
        Number(data?.content_score ?? 0),
        Number(data?.confidence_score ?? 0),
      ],
      avg: [70, 70, 65, 68, 72],
    };
  }, [data]);

  // draw charts
  useEffect(() => {
    // clean up existing charts
    Object.values(chartsRef.current).forEach((c) => c?.destroy());

    if (data) {
      // Filler donut
      if (fillerRef.current) {
        chartsRef.current.fw = new Chart(fillerRef.current, {
          type: "doughnut",
          data: {
            labels: ["Um", "Uh", "Like"],
            datasets: [{data: [fillerTotals.um, fillerTotals.uh, fillerTotals.like]}],
          },
          options: {
            responsive: true,
            plugins: {legend: {position: "bottom"}},
          },
        });
      }

      // Posture donut
      if (postureRef.current) {
        chartsRef.current.posture = new Chart(postureRef.current, {
          type: "doughnut",
          data: {
            labels: postureDist.labels.length ? postureDist.labels : ["No Data"],
            datasets: [{data: postureDist.counts.length ? postureDist.counts : [1]}],
          },
          options: {
            responsive: true,
            plugins: {legend: {position: "bottom"}},
          },
        });
      }

      // Radar
      if (radarRef.current) {
        chartsRef.current.radar = new Chart(radarRef.current, {
          type: "radar",
          data: {
            labels: radarMetrics.labels,
            datasets: [
              {
                label: "Your Scores",
                data: radarMetrics.values,
                fill: true,
                pointRadius: 3,
              },
              {
                label: "Average",
                data: radarMetrics.avg,
                fill: true,
                pointRadius: 3,
              },
            ],
          },
          options: {
            responsive: true,
            plugins: {legend: {position: "top"}},
            scales: {
              r: {
                beginAtZero: true,
                suggestedMax: 100,
                ticks: {stepSize: 20, showLabelBackdrop: false, callback: (v) => `${v}%`},
              },
            },
          },
        });
      }
    }

    return () => {
      Object.values(chartsRef.current).forEach((c) => c?.destroy());
      chartsRef.current = {};
    };
  }, [data, fillerTotals, postureDist, radarMetrics]);

  if (err) {
    return (
      <div className="app-wrap">
        <div className="card">
          <h2>Feedback</h2>
          <p className="err">{err}</p>
          <div className="row">
            <Link to="/waiting" className="btn">Back</Link>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="app-wrap">
        <div className="card"><h2>Feedback</h2><p>Loading…</p></div>
      </div>
    );
  }

  const ring = (label, val) => (
    <div className="ring">
      <div className="ring-fill" style={{"--val": `${Math.min(100, Math.max(0, +val || 0))}%`}}/>
      <div className="ring-inner">
        <div className="ring-score">{val ?? "-"}</div>
        <div className="ring-label">{label}</div>
      </div>
    </div>
  );

  return (
    <div className="app-wrap">
      <div className="card">
        <div className="fx between center">
          <div>
            <h2 style={{marginBottom: 4}}>Interview Analytics & Feedback</h2>
            <p className="muted">Session: {data.session_id}</p>
          </div>
          <div className="badge big">Overall: <b>{data.overall_score ?? "-"}</b>/100</div>
        </div>

        {/* Rings */}
        <div className="rings">
          {ring("Speech", data.speech_score)}
          {ring("Posture", data.posture_score)}
          {ring("Confidence", data.confidence_score)}
          {ring("Content", data.content_score)}
        </div>

        {/* Charts */}
        <div className="charts">
          <div className="chart-card">
            <h4>Filler Words</h4>
            <canvas ref={fillerRef} height="180"/>
          </div>
          <div className="chart-card">
            <h4>Posture Distribution</h4>
            <canvas ref={postureRef} height="180"/>
          </div>
          <div className="chart-card">
            <h4>Performance Radar</h4>
            <canvas ref={radarRef} height="180"/>
          </div>
        </div>

        <h3 style={{marginTop: 24}}>Per-Question Feedback</h3>
        {!(data.per_questions?.length) && <p className="muted">No per-question items.</p>}
        {data.per_questions?.filter(pq => (pq.transcript?.trim()?.length || pq.how_to_improve?.length || pq.what_to_fix?.length)).map((pq) => (
          <div key={pq.question_number} className="panel">
            <div className="panel-head">
              <div><b>Q{pq.question_number}.</b> {pq.question}</div>
              <div className="muted">
                Filler: um {pq.filler?.um ?? 0} • uh {pq.filler?.uh ?? 0} • like {pq.filler?.like ?? 0}
              </div>
            </div>

            <div className="qa">
              <div className="qa-label">Your answer</div>
              <div className="qa-body">{pq.transcript?.trim() || "(no transcript)"}</div>
            </div>

            {(pq.how_to_improve?.length || pq.what_to_fix?.length) && (
              <div className="grid2">
                {pq.how_to_improve?.length ? (
                  <div>
                    <div className="subhead">How to improve</div>
                    <ul className="list">
                      {pq.how_to_improve.map((t, i) => <li key={i}>{t}</li>)}
                    </ul>
                  </div>
                ) : null}
                {pq.what_to_fix?.length ? (
                  <div>
                    <div className="subhead">What to fix</div>
                    <ul className="list">
                      {pq.what_to_fix.map((t, i) => <li key={i}>{t}</li>)}
                    </ul>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        ))}

        <div className="row" style={{marginTop: 12}}>
          <a className="btn" href="/setup">🔄 Take Another Interview</a>
        </div>
      </div>
    </div>
  );
}
