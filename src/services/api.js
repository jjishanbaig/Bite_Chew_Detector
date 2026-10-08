const API_URL = "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export const checkBackend = () => request("/api/health");
export const getSession = () => request("/api/session");
export const startSession = () => request("/api/session/start", { method: "POST" });
export const stopSession = () => request("/api/session/stop", { method: "POST" });
export const getHistory = () => request("/api/history");
export const getAnalytics = () => request("/api/analytics");
