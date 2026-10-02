import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { LANGS, T } from "./i18n.js";
import { KoreaMap, Taegukgi } from "./Emblems.jsx";

function getUserId() {
  let id = localStorage.getItem("settle_user_id");
  if (!id) {
    id = "u" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("settle_user_id", id);
  }
  return id;
}

export default function App() {
  const [userId] = useState(getUserId);
  const [lang, setLang] = useState(localStorage.getItem("settle_lang") || "ko");
  const [messages, setMessages] = useState([]);
  const [roadmap, setRoadmap] = useState([]);
  const [dday, setDday] = useState(null);
  const [log, setLog] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef(null);
  const t = T[lang];

  // 저장된 대화를 먼저 복원하고, 재방문이면 에이전트가 먼저 말을 건다(능동 브리핑)
  useEffect(() => {
    (async () => {
      setBusy(true);
      try {
        const saved = await api.state(userId);
        const restored = saved.history.map((h) => ({ role: h.role, content: h.content }));
        setMessages(restored.length ? restored : [{ role: "assistant", content: T[lang].welcome }]);
        setRoadmap(saved.roadmap);
        setDday(saved.dday_label);
        const { briefing } = await api.briefing(userId, lang);
        if (briefing) applyResult(briefing, "briefing");
      } catch (e) {
        setMessages((m) => [...m, { role: "error", content: String(e) }]);
      } finally {
        setBusy(false);
      }
    })();
  }, [userId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  function applyResult(res, kind = "chat") {
    setMessages((m) => [...m, { role: "assistant", content: res.reply, files: res.files, kind }]);
    setLog((l) => [{ at: new Date().toLocaleTimeString(), ms: res.elapsed_ms, trace: res.trace }, ...l]);
    setRoadmap(res.state.roadmap);
    setDday(res.state.dday_label);
  }

  async function send(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    try {
      applyResult(await api.chat(userId, text, lang));
    } catch (err) {
      setMessages((m) => [...m, { role: "error", content: String(err) }]);
    } finally {
      setBusy(false);
    }
  }

  async function resetAll() {
    await api.reset(userId);
    setMessages([{ role: "assistant", content: t.welcome }]);
    setRoadmap([]);
    setDday(null);
    setLog([]);
  }

  function changeLang(l) {
    setLang(l);
    localStorage.setItem("settle_lang", l);
  }

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <Taegukgi className="flag" title={t.flag} />
          <div>
            <h1>{t.title}</h1>
            <p>{t.subtitle}</p>
          </div>
        </div>
        <div className="controls">
          <select id="lang" value={lang} onChange={(e) => changeLang(e.target.value)}>
            {Object.entries(LANGS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <button className="ghost" onClick={resetAll}>{t.reset}</button>
        </div>
      </header>

      <main className="grid">
        <section className="chat">
          <div className="messages">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role} ${m.kind || ""}`}>
                <div className="bubble">{m.content}</div>
                {m.files?.map((f) => (
                  <a key={f} className="file" href={f}>{t.download}</a>
                ))}
              </div>
            ))}
            {busy && <div className="msg assistant"><div className="bubble muted">{t.thinking}</div></div>}
            <div ref={bottomRef} />
          </div>
          <form className="composer" onSubmit={send}>
            <input id="message" value={input} onChange={(e) => setInput(e.target.value)} placeholder={t.placeholder} />
            <button disabled={busy}>{t.send}</button>
          </form>
        </section>

        <aside className="side">
          <div className="panel region">
            <KoreaMap className="map" title={t.mapLabel} />
            <div>
              <div className="region-name">{t.region}</div>
              <p className="muted small">{t.regionNote}</p>
            </div>
          </div>

          <div className="panel">
            <h2>
              {t.roadmap}
              {dday && <span className="dday">{dday}</span>}
            </h2>
            {roadmap.length === 0 ? (
              <p className="muted">{t.emptyRoadmap}</p>
            ) : (
              <ol className="roadmap">
                {roadmap.map((s) => (
                  <li key={s.id} className={s.done ? "done" : ""}>
                    <span>
                      <span className="cat">{t.categories?.[s.category] ?? s.category}</span>
                      {t.steps?.[s.id] ?? s.title}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="panel">
            <h2>{t.toolLog}</h2>
            {log.length === 0 ? (
              <p className="muted">{t.emptyLog}</p>
            ) : (
              log.map((turn, i) => (
                <div key={i} className="turn">
                  <div className="turn-head">{turn.at} · {turn.ms}ms</div>
                  {turn.trace.length === 0 && <div className="muted small">{t.noToolCall}</div>}
                  {turn.trace.map((c, j) => (
                    <details key={j} className="call">
                      <summary>
                        <code>{c.tool}</code>({Object.keys(c.args).join(", ")}) · {c.ms}ms
                      </summary>
                      <pre>{JSON.stringify({ args: c.args, result: c.result }, null, 2)}</pre>
                    </details>
                  ))}
                </div>
              ))
            )}
          </div>
        </aside>
      </main>
    </div>
  );
}
