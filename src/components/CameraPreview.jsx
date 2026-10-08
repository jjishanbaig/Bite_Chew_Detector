import { useEffect, useRef, useState } from "react";

const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17],
];

export default function CameraPreview({ running, onMetrics }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const overlayRef = useRef(null);
  const wsRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const lastMetricsRef = useRef(null);

  const [cameraReady, setCameraReady] = useState(false);
  const [cvReady, setCvReady] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function start() {
      if (!running) {
        cleanup();
        return;
      }

      try {
        setError("");
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 },
            facingMode: "user",
          },
          audio: false,
        });

        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamRef.current = stream;
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraReady(true);

        const ws = new WebSocket("ws://127.0.0.1:8000/ws/analyze");
        wsRef.current = ws;

        ws.onopen = () => {
          setCvReady(true);
          timerRef.current = setInterval(() => sendFrame(ws), 130);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            lastMetricsRef.current = data;
            onMetrics(data);
            drawOverlay(data);
          } catch {}
        };

        ws.onerror = () => setError("WebSocket connection to the CV backend failed.");
        ws.onclose = () => setCvReady(false);
      } catch (err) {
        setError(err.message || "Could not access the camera.");
      }
    }

    function sendFrame(ws) {
      if (!videoRef.current || !canvasRef.current || ws.readyState !== WebSocket.OPEN) return;
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const maxWidth = 960;
      const scale = Math.min(1, maxWidth / (video.videoWidth || 960));
      canvas.width = Math.max(1, Math.round((video.videoWidth || 960) * scale));
      canvas.height = Math.max(1, Math.round((video.videoHeight || 540) * scale));
      const ctx = canvas.getContext("2d", { willReadFrequently: false });
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(async (blob) => {
        if (!blob || ws.readyState !== WebSocket.OPEN) return;
        ws.send(await blob.arrayBuffer());
      }, "image/jpeg", 0.72);
    }

    function drawOverlay(data) {
      const video = videoRef.current;
      const overlay = overlayRef.current;
      if (!video || !overlay || !video.videoWidth) return;
      overlay.width = video.videoWidth;
      overlay.height = video.videoHeight;
      const ctx = overlay.getContext("2d");
      ctx.clearRect(0, 0, overlay.width, overlay.height);

      const sx = overlay.width;
      const sy = overlay.height;
      const points = data.hand_points || [];

      if (points.length) {
        ctx.lineWidth = Math.max(2, sx / 640);
        ctx.strokeStyle = "rgba(0, 220, 120, 0.9)";
        for (const [a, b] of HAND_CONNECTIONS) {
          if (!points[a] || !points[b]) continue;
          ctx.beginPath();
          ctx.moveTo(points[a].x * sx, points[a].y * sy);
          ctx.lineTo(points[b].x * sx, points[b].y * sy);
          ctx.stroke();
        }
        ctx.fillStyle = "rgba(255, 255, 255, 0.95)";
        points.forEach((p) => {
          ctx.beginPath();
          ctx.arc(p.x * sx, p.y * sy, Math.max(3, sx / 320), 0, Math.PI * 2);
          ctx.fill();
        });
      }

      if (data.mouth_center) {
        const m = data.mouth_center;
        const mx = m.x * sx;
        const my = m.y * sy;
        ctx.fillStyle = "rgba(255, 90, 90, 0.95)";
        ctx.beginPath();
        ctx.arc(mx, my, Math.max(5, sx / 220), 0, Math.PI * 2);
        ctx.fill();

        if (data.index_tip) {
          const ix = data.index_tip.x * sx;
          const iy = data.index_tip.y * sy;
          ctx.strokeStyle = data.hand_near_mouth ? "rgba(255, 190, 0, 0.95)" : "rgba(255,255,255,0.7)";
          ctx.lineWidth = Math.max(2, sx / 500);
          ctx.beginPath();
          ctx.moveTo(ix, iy);
          ctx.lineTo(mx, my);
          ctx.stroke();
        }
      }
    }

    start();
    return () => {
      cancelled = true;
      cleanup();
    };
  }, [running]);

  function cleanup() {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    if (wsRef.current) wsRef.current.close();
    wsRef.current = null;
    if (streamRef.current) streamRef.current.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setCameraReady(false);
    setCvReady(false);
  }

  return (
    <div className="relative aspect-video overflow-hidden rounded-3xl bg-black">
      <video ref={videoRef} muted playsInline className="h-full w-full object-cover" />
      <canvas ref={canvasRef} className="hidden" />
      <canvas ref={overlayRef} className="pointer-events-none absolute inset-0 h-full w-full" />

      {!running && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-white/70">
          Start a session to activate the camera
        </div>
      )}

      {running && (
        <div className="absolute left-4 top-4 flex flex-wrap gap-2">
          <span className="rounded-full bg-black/65 px-3 py-1 text-xs text-white">
            Camera: {cameraReady ? "ON" : "STARTING"}
          </span>
          <span className="rounded-full bg-black/65 px-3 py-1 text-xs text-white">
            AI: {cvReady ? "CONNECTED" : "CONNECTING"}
          </span>
        </div>
      )}

      {error && (
        <div className="absolute bottom-3 left-3 right-3 rounded-xl bg-red-600/90 p-3 text-xs text-white">
          {error}
        </div>
      )}
    </div>
  );
}
