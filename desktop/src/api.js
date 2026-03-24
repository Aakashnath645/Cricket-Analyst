const API_BASE = "http://127.0.0.1:8000";

async function parseJson(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data?.detail || data?.message || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

export async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`);
  return parseJson(response);
}

export async function apiPost(path, payload) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return parseJson(response);
}

