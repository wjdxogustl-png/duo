import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { KO, LANGS, LOCALES, TRANSLATIONS, hasMissing, mergeStrings } from "./i18n.js";
import { KoreaMap, Taegukgi } from "./Emblems.jsx";

function getUserId() {
  let id = localStorage.getItem("settle_user_id");
  if (!id) {
    id = "u" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("settle_user_id", id);
  }
  return id;
}

// 저장된 선택이 없으면 운영체제 설정(라이트/다크)을 따른다
function getTheme() {
  const saved = localStorage.getItem("settle_theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

const WELCOME = { role: "assistant", kind: "welcome" }; // 내용은 현재 언어의 t.welcome 으로 그린다

// 번역된 화면 문구는 원본(KO)이 같을 때만 브라우저에 저장해 둔 것을 다시 쓴다
function cachedStrings(lang, sig) {
  try {
    const c = JSON.parse(localStorage.getItem(`settle_i18n_${lang}`));
    return c?.sig === sig ? c.strings : null;
  } catch {
    return null;
  }
}

export default function App() {
  const [userId] = useState(getUserId);
  const [lang, setLang] = useState(() => {
    const saved = localStorage.getItem("settle_lang");
    return saved in LANGS ? saved : "ko";
  });
  const [t, setT] = useState(KO);
  const [translating, setTranslating] = useState(false);
  const [aiUsed, setAiUsed] = useState(false);
  const [theme, setTheme] = useState(getTheme);
  const [messages, setMessages] = useState([]);
  const [roadmap, setRoadmap] = useState([]);
  const [situations, setSituations] = useState([]);
  const [dday, setDday] = useState(null);
  const [log, setLog] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef(null);

  // 저장된 대화를 먼저 복원하고, 재방문이면 에이전트가 먼저 말을 건다(능동 브리핑)
  useEffect(() => {
    (async () => {
      setBusy(true);
      try {
        const saved = await api.state(userId);
        const restored = saved.history.map((h) => ({ role: h.role, content: h.content, actions: h.actions }));
        setMessages(restored.length ? restored : [WELCOME]);
        setRoadmap(saved.roadmap);
        setSituations(saved.situations || []);
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
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  // 한국어가 아니면 i18n.js 에 직접 번역해 둔 문구를 쓴다.
  // 번역에 빠진 키가 있을 때만 AI 번역으로 채운다 (번역이 오기 전까지 빠진 키는 한국어로 보인다)
  useEffect(() => {
    document.documentElement.lang = lang;
    setTranslating(false);
    setAiUsed(false);
    const manual = TRANSLATIONS[lang];
    const base = mergeStrings(KO, manual);
    setT(base);
    if (lang === "ko" || !hasMissing(KO, manual)) return;
    const fill = (strings) => {
      setT(mergeStrings(mergeStrings(KO, strings), manual));
      setAiUsed(true);
    };
    const sig = JSON.stringify(KO);
    const cached = cachedStrings(lang, sig);
    if (cached) {
      fill(cached);
      return;
    }
    let cancelled = false;
    setTranslating(true);
    api.i18n(lang, KO)
      .then((res) => {
        if (cancelled || !res.translated) return;
        fill(res.strings);
        try {
          localStorage.setItem(`settle_i18n_${lang}`, JSON.stringify({ sig, strings: res.strings }));
        } catch {}
      })
      .catch(() => {})
      .finally(() => !cancelled && setTranslating(false));
    return () => {
      cancelled = true;
    };
  }, [lang]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  function applyResult(res, kind = "chat") {
    setMessages((m) => [...m, { role: "assistant", content: res.reply, files: res.files, actions: res.actions, kind }]);
    setLog((l) => [{ at: new Date(), ms: res.elapsed_ms, trace: res.trace, kind }, ...l]);
    setRoadmap(res.state.roadmap);
    setSituations(res.state.situations || []);
    setDday(res.state.dday_label);
  }

  async function send(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    await say(text);
  }

  // 입력창 전송과 액션 카드(say) 클릭이 같은 길로 메시지를 보낸다
  async function say(text) {
    if (!text || busy) return;
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
    setMessages([WELCOME]);
    setRoadmap([]);
    setSituations([]);
    setDday(null);
    setLog([]);
  }

  function changeTheme(next) {
    setTheme(next);
    localStorage.setItem("settle_theme", next);
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
          <div className="theme-toggle" role="group" aria-label={t.theme}>
            <button type="button" aria-pressed={theme === "light"} onClick={() => changeTheme("light")} aria-label={t.themeLight} title={t.themeLight}>☀<span className="label"> {t.themeLight}</span></button>
            <button type="button" aria-pressed={theme === "dark"} onClick={() => changeTheme("dark")} aria-label={t.themeDark} title={t.themeDark}>☾<span className="label"> {t.themeDark}</span></button>
          </div>
          <select id="lang" value={lang} onChange={(e) => changeLang(e.target.value)}>
            {Object.entries(LANGS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <button className="ghost" onClick={resetAll}>{t.reset}</button>
          {(translating || aiUsed) && (
            <span className="ai-badge" aria-live="polite">{translating ? t.translating : t.aiTranslated}</span>
          )}
        </div>
      </header>

      <main className="grid">
        <section className="chat">
          <div className="messages">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role} ${m.kind || ""}`}>
                <div className="bubble">{m.kind === "welcome" ? t.welcome : m.content}</div>
                {m.files?.map((f) => (
                  <a key={f} className="file" href={f}>{t.download}</a>
                ))}
                {/* 지난 답장의 카드는 이미 지나간 제안이므로 마지막 답장에만 보인다 */}
                {i === messages.length - 1 && m.actions?.length > 0 && (
                  <ActionCards actions={m.actions} title={t.nextActions} disabled={busy} onSay={say} />
                )}
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
            <h2>{t.situations}</h2>
            {situations.length === 0 ? (
              <p className="muted">{t.emptySituations}</p>
            ) : (
              <ul className="situations">
                {[...situations]
                  .sort((a, b) => (a.status === "해결됨") - (b.status === "해결됨"))
                  .map((s) => (
                    <li key={s.id} className={`sit ${s.status === "해결됨" ? "resolved" : ""} u-${s.urgency}`}>
                      <div className="sit-head">
                        <span className="need">{t.needs?.[s.need] ?? s.need}</span>
                        <span className="urgency">{t.urgency?.[s.urgency] ?? s.urgency}</span>
                        {s.confidence === "추정" && <span className="guess">{t.guessed}</span>}
                        {s.status === "해결됨" && <span className="guess">{t.resolved}</span>}
                      </div>
                      <p className="sit-text">{s.understanding}</p>
                      <p className="sit-evidence">{t.evidence}: “{s.evidence}”</p>
                    </li>
                  ))}
              </ul>
            )}
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
                  <div className="turn-head">
                    {turn.at.toLocaleTimeString(LOCALES[lang])}
                    {turn.kind === "briefing" && ` · ${t.briefingTurn}`} · {turn.ms}ms
                  </div>
                  {turn.trace.length === 0 && <div className="muted small">{t.noToolCall}</div>}
                  {turn.trace.map((c, j) => (
                    <div key={j}>
                      <details className="call">
                        <summary>
                          {t.tools?.[c.tool] ?? c.tool} <code>{c.tool}</code> · {c.ms}ms
                        </summary>
                        <pre>{JSON.stringify({ args: c.args, result: c.result }, null, 2)}</pre>
                      </details>
                      {c.result?.pipeline?.steps && (
                        <ol className="pipeline">
                          {c.result.pipeline.steps.map((s, k) => (
                            <li key={k}>
                              {t.pipeline?.[s.stage] ?? s.stage} <span className="muted">{s.detail}</span>
                            </li>
                          ))}
                        </ol>
                      )}
                    </div>
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

// 에이전트가 판단한 다음 행동 카드. say 는 누르면 그 문장을 보내고, call·link 는 전화·출처로 바로 연결한다
function ActionCards({ actions, title, disabled, onSay }) {
  return (
    <div className="actions" role="group" aria-label={title}>
      <div className="actions-title">{title}</div>
      {actions.map((a, i) => {
        const body = (
          <>
            <span className="action-label">
              {a.kind === "call" ? "☎ " : a.kind === "link" ? "↗ " : ""}
              {a.label}
            </span>
            <span className="action-reason">{a.reason}</span>
          </>
        );
        if (a.kind === "call") return <a key={i} className="action" href={`tel:${a.phone}`}>{body}</a>;
        if (a.kind === "link") return <a key={i} className="action" href={a.url} target="_blank" rel="noreferrer">{body}</a>;
        return (
          <button key={i} type="button" className="action" disabled={disabled} onClick={() => onSay(a.message)}>
            {body}
          </button>
        );
      })}
    </div>
  );
}
