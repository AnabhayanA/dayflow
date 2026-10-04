const API = import.meta.env.VITE_API_URL || "/api-server";

export const getToken = () => localStorage.getItem("tempo_token");
export const clearToken = () => localStorage.removeItem("tempo_token");

async function request(path, options = {}) {
  const token = getToken();
  const response = await fetch(API + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (response.status === 204) return null;
  const raw = await response.text();
  let data = {};
  try { data = raw ? JSON.parse(raw) : {}; } catch { data = { detail: raw }; }
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map(x => x.msg || JSON.stringify(x)).join("; ")
      : data.detail;
    throw new Error(detail || `Tempo request failed (HTTP ${response.status})`);
  }
  return data;
}

export async function signup(body) {
  const data = await request("/auth/signup", { method: "POST", body: JSON.stringify(body) });
  localStorage.setItem("tempo_token", data.token);
  return data;
}
export async function login(body) {
  const data = await request("/auth/login", { method: "POST", body: JSON.stringify(body) });
  localStorage.setItem("tempo_token", data.token);
  return data;
}
export const me = () => request("/auth/me");
export const events = () => request("/api/events");
export const createEvent = body => request("/api/events", { method: "POST", body: JSON.stringify(body) });
export const updateEvent = (id, body) => request(`/api/events/${id}`, { method: "PUT", body: JSON.stringify(body) });
export const removeEvent = id => request(`/api/events/${id}`, { method: "DELETE" });
export const tasks = () => request("/api/tasks");
export const createTask = body => request("/api/tasks", { method: "POST", body: JSON.stringify(body) });
export const removeTask = id => request(`/api/tasks/${id}`, { method: "DELETE" });

export const calendarConnections = () => request("/api/calendars");
export const googleCalendarConnect = () => request("/api/calendars/google/connect");
export const syncGoogleCalendar = () => request("/api/calendars/google/sync", { method: "POST" });

export const setTaskStatus = (id, completed) => request(`/api/tasks/${id}/status`, { method: "PATCH", body: JSON.stringify({ completed }) });
export const scheduleChanges = () => request("/api/changes");
export const searchTempoUsers = q => request(`/api/sharing/users?q=${encodeURIComponent(q)}`);
export const findSharedSlots = body => request("/api/sharing/find-slots", { method: "POST", body: JSON.stringify(body) });
export const createSharedMeeting = body => request("/api/sharing/meetings", { method: "POST", body: JSON.stringify(body) });
export const confirmSharedMeeting = (id, start) => request(`/api/sharing/meetings/${id}/confirm`, { method: "POST", body: JSON.stringify({ start }) });
export const sharedMeetings = () => request("/api/sharing/meetings");
export const tempoChat = (message, conversation = []) => request("/api/ai/chat", { method: "POST", body: JSON.stringify({ message, conversation, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone }) });

export const tempoApply = action => request("/api/ai/apply", { method: "POST", body: JSON.stringify(action) });
