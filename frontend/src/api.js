async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  chat: (userId, message, language) =>
    request("/chat", { method: "POST", body: JSON.stringify({ user_id: userId, message, language }) }),
  briefing: (userId, language) => request(`/briefing/${userId}?language=${language}`),
  state: (userId) => request(`/state/${userId}`),
  reset: (userId) => request(`/state/${userId}`, { method: "DELETE" }),
  i18n: (language, source) => request("/i18n", { method: "POST", body: JSON.stringify({ language, source }) }),
};
