// api.js — All backend API calls in one place
// WHY: Centralizing API calls makes it easy to change the base URL
//      for production vs development without touching components.

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Generic fetch helper with error handling
 */
async function apiFetch(endpoint, options = {}) {
    const response = await fetch(`${BASE_URL}${endpoint}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });

    if (!response.ok) {
        throw new Error(`API error ${response.status}: ${await response.text()}`);
    }

    return response.json();
}

/** Get full dashboard data (overs + spikes + recent messages) */
export const fetchDashboard = () => apiFetch("/dashboard");

/** Get per-over emotion summaries for the graph */
export const fetchEmotions = () => apiFetch("/emotions");

/** Get spike/viral moments */
export const fetchSpikes = () => apiFetch("/spikes");

/** Get recent messages, optionally by over number */
export const fetchMessages = (over = null) =>
    apiFetch(`/messages${over ? `?over=${over}` : ""}`);

/** Admin: reset match start time */
export const startMatch = () =>
    apiFetch("/admin/start-match", { method: "POST" });

/** Admin: set Telegram webhook */
export const setWebhook = (backendUrl) =>
    apiFetch(`/admin/set-webhook?backend_url=${encodeURIComponent(backendUrl)}`, {
        method: "POST",
    });