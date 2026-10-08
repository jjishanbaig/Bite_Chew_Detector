import { useEffect, useMemo, useState } from "react";
import CameraPreview from "./components/CameraPreview";
import {
  checkBackend,
  getAnalytics,
  getHistory,
  startSession,
  stopSession,
} from "./services/api";

const EMPTY = {
  bites: 0,
  chews: 0,
  face_detected: false,
  hand_detected: false,
  mouth_opening: null,
  mouth_state: "UNKNOWN",
  hand_to_mouth_distance: null,
  hand_near_mouth: false,
  hand_approaching: false,
  bite_state: "IDLE",
  bite_detected: false,
  jaw_movement: 0,
  chew_state: "IDLE",
  chew_detected: false,
  bite_confidence: 0,
  jaw_amplitude: 0,
  selected_hand: null,
  hand_confidence: 0,
  fps: 0,
  processing_ms: 0,
};

function Card({ title, value, sub }) {
  return (
    <div className="rounded-2xl border border-black/5 bg-white p-5 shadow-sm">
      <p className="text-sm text-gray-500">{title}</p>
      <p className="mt-2 text-3xl font-bold">{value}</p>
      {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

function Row({ label, value, good }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-black/5 py-2 last:border-0">
      <span className="text-gray-500">{label}</span>
      <span className={good ? "font-semibold text-green-700" : "font-medium"}>
        {value}
      </span>
    </div>
  );
}

function Bar({ label, value, max }) {
  const width = max > 0 ? Math.max(3, Math.round((value / max) * 100)) : 3;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span>{label}</span>
        <span>{value}</span>
      </div>
      <div className="h-2 rounded-full bg-gray-100">
        <div className="h-2 rounded-full bg-green-600" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

export default function App() {
  const [running, setRunning] = useState(false);
  const [backend, setBackend] = useState("Checking");
  const [metrics, setMetrics] = useState(EMPTY);
  const [history, setHistory] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [startedAt, setStartedAt] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [message, setMessage] = useState("");

  async function refreshData() {
    try {
      const [h, a] = await Promise.all([getHistory(), getAnalytics()]);
      setHistory(h);
      setAnalytics(a);
    } catch {}
  }

  useEffect(() => {
    checkBackend()
      .then(() => setBackend("Online"))
      .catch(() => setBackend("Offline"));
    refreshData();
  }, []);

  useEffect(() => {
    if (!running || !startedAt) return;
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 500);
    return () => clearInterval(id);
  }, [running, startedAt]);

  const duration = useMemo(() => {
    const m = Math.floor(elapsed / 60).toString().padStart(2, "0");
    const s = (elapsed % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  }, [elapsed]);

  async function begin() {
    try {
      await startSession();
      setRunning(true);
      setStartedAt(Date.now());
      setElapsed(0);
      setMetrics(EMPTY);
      setMessage("Session started");
    } catch (e) {
      setMessage(e.message);
    }
  }

  async function finish() {
    try {
      const result = await stopSession();
      setRunning(false);
      setMessage(result.message || "Session saved");
      await refreshData();
    } catch (e) {
      setMessage(e.message);
    }
  }

  function handleMetrics(data) {
    setMetrics(data);
    if (data.bite_detected) setMessage("✓ Bite detected");
    else if (data.chew_detected) setMessage("✓ Chew detected");
  }

  const maxBites = Math.max(1, ...(history.map((x) => x.bites) || [1]));
  const maxChews = Math.max(1, ...(history.map((x) => x.chews) || [1]));

  return (
    <main className="min-h-screen">
      <nav className="border-b border-black/5 bg-white/90 px-6 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">Bite & Chew AI</h1>
            <p className="text-xs text-gray-500">Computer-vision eating activity analysis</p>
          </div>
          <span className="rounded-full bg-gray-100 px-3 py-1 text-xs">
            Backend: {backend}
          </span>
        </div>
      </nav>

      <section className="mx-auto max-w-7xl space-y-6 px-6 py-8">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="text-sm font-semibold text-green-700">LIVE ANALYSIS</p>
            <h2 className="mt-1 text-3xl font-bold">Track every bite and chew</h2>
            <p className="mt-2 max-w-3xl text-gray-500">
              Bite = detected hand near mouth + mouth opens + mouth closes. Chew = complete normalized jaw cycles.
            </p>
          </div>

          <button
            onClick={running ? finish : begin}
            className="rounded-xl bg-black px-6 py-3 font-semibold text-white hover:opacity-85"
          >
            {running ? "Stop Session" : "Start Session"}
          </button>
        </div>

        {message && (
          <div className="rounded-xl border border-black/5 bg-white px-4 py-3 text-sm">
            {message}
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-4">
          <Card title="Bites" value={metrics.bites} sub="Live session" />
          <Card title="Chews" value={metrics.chews} sub="Live session" />
          <Card title="Duration" value={duration} />
          <Card
            title="Bites / min"
            value={elapsed ? ((metrics.bites * 60) / elapsed).toFixed(1) : "0.0"}
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.45fr_1fr]">
          <div className="rounded-3xl border border-black/5 bg-white p-4 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-semibold">Camera & AI Detection</h3>
              <span className="text-xs text-gray-500">{running ? "Processing" : "Idle"}</span>
            </div>
            <CameraPreview running={running} onMetrics={handleMetrics} />
          </div>

          <div className="space-y-4">
            <div className="rounded-3xl border border-black/5 bg-white p-5 shadow-sm">
              <h3 className="font-semibold">Live CV diagnostics</h3>
              <div className="mt-3 text-sm">
                <Row label="Face detected" value={metrics.face_detected ? "Yes" : "No"} good={metrics.face_detected} />
                <Row label="Hand detected" value={metrics.hand_detected ? "Yes" : "No"} good={metrics.hand_detected} />
                <Row label="Selected hand" value={metrics.selected_hand || "—"} />
                <Row label="Hand confidence" value={percent(metrics.hand_confidence)} />
                <Row label="Hand near mouth" value={metrics.hand_near_mouth ? "YES" : "No"} good={metrics.hand_near_mouth} />
                <Row label="Hand approaching" value={metrics.hand_approaching ? "YES" : "No"} good={metrics.hand_approaching} />
                <Row label="Mouth" value={metrics.mouth_state} good={metrics.mouth_state === "OPEN"} />
                <Row label="Hand-mouth distance" value={num(metrics.hand_to_mouth_distance)} />
                <Row label="Bite state" value={metrics.bite_state} />
                <Row label="Bite confidence" value={percent(metrics.bite_confidence)} />
                <Row label="Jaw movement" value={num(metrics.jaw_movement)} />
                <Row label="Jaw amplitude" value={num(metrics.jaw_amplitude)} />
                <Row label="Chew state" value={metrics.chew_state} />
                <Row label="Processing" value={`${metrics.fps || 0} FPS / ${metrics.processing_ms || 0} ms`} />
              </div>
            </div>

            <div className="rounded-3xl border border-black/5 bg-white p-5 shadow-sm">
              <h3 className="font-semibold">Bite logic</h3>
              <div className="mt-3 space-y-2 text-sm text-gray-600">
                <p>✓ Hand must be detected</p>
                <p>✓ Hand must enter mouth zone</p>
                <p>✓ Mouth must open</p>
                <p>✓ Mouth must close</p>
                <p>✓ Timing + cooldown prevent duplicates</p>
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-3xl border border-black/5 bg-white p-5 shadow-sm">
          <h3 className="font-semibold">Analytics</h3>
          <div className="mt-4 grid gap-4 md:grid-cols-4">
            <Card title="Total sessions" value={analytics?.total_sessions ?? 0} />
            <Card title="Total bites" value={analytics?.total_bites ?? 0} />
            <Card title="Total chews" value={analytics?.total_chews ?? 0} />
            <Card title="Avg bites/session" value={analytics?.average_bites ?? "0.0"} />
            <Card title="Avg chews/bite" value={analytics?.average_chews_per_bite ?? "0.0"} />
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-3xl border border-black/5 bg-white p-5 shadow-sm">
            <h3 className="font-semibold">Bites by session</h3>
            <div className="mt-5 space-y-4">
              {history.length === 0 ? (
                <p className="text-sm text-gray-400">No completed sessions yet.</p>
              ) : history.slice(0, 8).map((item) => (
                <Bar key={item.id} label={item.started_at} value={item.bites} max={maxBites} />
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-black/5 bg-white p-5 shadow-sm">
            <h3 className="font-semibold">Chews by session</h3>
            <div className="mt-5 space-y-4">
              {history.length === 0 ? (
                <p className="text-sm text-gray-400">No completed sessions yet.</p>
              ) : history.slice(0, 8).map((item) => (
                <Bar key={item.id} label={item.started_at} value={item.chews} max={maxChews} />
              ))}
            </div>
          </div>
        </div>

        <div className="rounded-3xl border border-black/5 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">Session History</h3>
            <span className="text-xs text-gray-400">Latest 20</span>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b text-gray-500">
                <tr>
                  <th className="px-2 py-3">Started</th>
                  <th className="px-2 py-3">Duration</th>
                  <th className="px-2 py-3">Bites</th>
                  <th className="px-2 py-3">Chews</th>
                  <th className="px-2 py-3">Bites/min</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="px-2 py-6 text-center text-gray-400">
                      No completed sessions yet.
                    </td>
                  </tr>
                ) : history.map((item) => (
                  <tr key={item.id} className="border-b last:border-0">
                    <td className="px-2 py-3">{item.started_at}</td>
                    <td className="px-2 py-3">{Math.round(item.duration_seconds)}s</td>
                    <td className="px-2 py-3 font-semibold">{item.bites}</td>
                    <td className="px-2 py-3 font-semibold">{item.chews}</td>
                    <td className="px-2 py-3">
                      {item.duration_seconds > 0
                        ? ((item.bites * 60) / item.duration_seconds).toFixed(2)
                        : "0.00"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </main>
  );
}

function num(v) {
  return typeof v === "number" ? v.toFixed(3) : "—";
}

function percent(v) {
  return typeof v === "number" ? `${Math.round(v * 100)}%` : "—";
}
