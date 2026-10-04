const API = import.meta.env.VITE_API_URL || "/api-server";

export const getToken = () => localStorage.getItem("dayflow_token");
export const clearToken = () => localStorage.removeItem("dayflow_token");

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
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "DayFlow request failed");
  return data;
}

export async function signup(body) {
  const data = await request("/auth/signup", { method: "POST", body: JSON.stringify(body) });
  localStorage.setItem("dayflow_token", data.token);
  return data;
}
export async function login(body) {
  const data = await request("/auth/login", { method: "POST", body: JSON.stringify(body) });
  localStorage.setItem("dayflow_token", data.token);
  return data;
}
export const me = () => request("/auth/me");
export const events = () => request("/api/events");
export const createEvent = body => request("/api/events", { method: "POST", body: JSON.stringify(body) });
export const removeEvent = id => request(`/api/events/${id}`, { method: "DELETE" });
export const tasks = () => request("/api/tasks");
export const createTask = body => request("/api/tasks", { method: "POST", body: JSON.stringify(body) });
export const removeTask = id => request(`/api/tasks/${id}`, { method: "DELETE" });
