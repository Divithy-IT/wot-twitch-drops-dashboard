import { FormEvent, useEffect, useState } from "react";
import { api, fmt } from "../api";
import { Link2, Unplug, RefreshCw, Trash2 } from "lucide-react";
const toggles = [
  ["enabled", "Automatycznie zatwierdzaj potwierdzone Twitch Drops"],
  ["auto_high", "Zatwierdzaj wysoką wartość"],
  ["auto_medium", "Zatwierdzaj średnią wartość"],
  ["auto_low", "Zatwierdzaj niską wartość"],
  ["auto_unknown", "Zatwierdzaj nieznane nagrody"],
  ["require_worldoftanks_channel", "Wymagaj kanału worldoftanks"],
  ["require_exact_dates", "Wymagaj dokładnych dat"],
  ["require_watch_time", "Wymagaj czasu oglądania"],
  ["require_trusted_source", "Wymagaj oficjalnego źródła"],
  ["require_explicit_drops", "Wymagaj jednoznacznego potwierdzenia Drops"],
];
export default function SettingsPage() {
  const [t, setT] = useState<any>(null),
    [discord, setDiscord] = useState<any>({ configured: false }),
    [logs, setLogs] = useState<any[]>([]),
    [rules, setRules] = useState<any>({}),
    [sources, setSources] = useState<any[]>([]),
    [msg, setMsg] = useState("");
  const load = () =>
    Promise.all([
      api("/oauth/twitch/status"),
      api<any[]>("/logs"),
      api("/notifications/discord"),
      api("/qualification/settings"),
      api<any[]>("/trusted-sources"),
    ]).then(([a, b, c, d, e]) => {
      setT(a);
      setLogs(b);
      setDiscord(c);
      setRules(d);
      setSources(e);
    });
  useEffect(() => {
    load();
  }, []);
  async function post(p: string) {
    try {
      const r: any = await api(p, { method: "POST" });
      setMsg(r.note || "Gotowe");
      load();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }
  async function saveDiscord(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const url = String(new FormData(e.currentTarget).get("webhook") || "");
    await api("/notifications/discord", {
      method: "PUT",
      body: JSON.stringify({ webhook_url: url || null }),
    });
    setMsg("Zapisano");
    load();
  }
  async function saveRules() {
    await api("/qualification/settings", {
      method: "PUT",
      body: JSON.stringify(rules),
    });
    setMsg("Reguły zapisane");
  }
  async function addSource(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    await api("/trusted-sources", {
      method: "POST",
      body: JSON.stringify({
        name: f.get("name"),
        url_pattern: f.get("url"),
        enabled: true,
        auto_approve: true,
        max_trust_score: 100,
        ignored: false,
      }),
    });
    e.currentTarget.reset();
    load();
  }
  return (
    <>
      <div className="pagehead">
        <div>
          <span className="eyebrow">KONFIGURACJA</span>
          <h1>Ustawienia</h1>
        </div>
      </div>
      <section className="panel">
        <h2>Automatyczna kwalifikacja Drops</h2>
        {toggles.map(([key, label]) => (
          <label key={key} className="check">
            <input
              type="checkbox"
              checked={!!rules[key]}
              onChange={(e) => setRules({ ...rules, [key]: e.target.checked })}
            />
            {label}
          </label>
        ))}
        <div className="twocol">
          <label>
            Próg automatycznego zatwierdzenia
            <input
              type="number"
              min="0"
              max="100"
              value={rules.approve_threshold ?? 85}
              onChange={(e) =>
                setRules({
                  ...rules,
                  approve_threshold: Number(e.target.value),
                })
              }
            />
          </label>
          <label>
            Próg ręcznej weryfikacji
            <input
              type="number"
              min="0"
              max="100"
              value={rules.review_threshold ?? 55}
              onChange={(e) =>
                setRules({ ...rules, review_threshold: Number(e.target.value) })
              }
            />
          </label>
        </div>
        <button onClick={saveRules}>Zapisz reguły</button>
      </section>
      <section className="panel">
        <h2>Zaufane źródła</h2>
        <div className="source-list">
          {sources.map((s) => (
            <div key={s.id}>
              <span>
                <b>{s.name}</b>
                <small>
                  {s.url_pattern} · max {s.max_trust_score}/100 · auto:{" "}
                  {s.auto_approve ? "tak" : "nie"}
                </small>
              </span>
              <button
                className="danger"
                onClick={() =>
                  api(`/trusted-sources/${s.id}`, { method: "DELETE" }).then(
                    load,
                  )
                }
              >
                <Trash2 />
              </button>
            </div>
          ))}
        </div>
        <form onSubmit={addSource}>
          <div className="twocol">
            <label>
              Nazwa
              <input name="name" required />
            </label>
            <label>
              Prefiks URL
              <input name="url" type="url" required />
            </label>
          </div>
          <button>Dodaj zaufane źródło</button>
        </form>
      </section>
      <section className="panel">
        <h2>Konto Twitch</h2>
        {t?.connected ? (
          <>
            <dl>
              <dt>Stan</dt>
              <dd className="ok">Połączone</dd>
              <dt>Konto</dt>
              <dd>{t.login}</dd>
            </dl>
            <div className="actions">
              <button onClick={() => post("/oauth/twitch/sync")}>
                <RefreshCw />
                Synchronizuj
              </button>
              <a
                className="button secondary"
                href="/wot/api/oauth/twitch/connect"
              >
                <Link2 />
                Połącz ponownie
              </a>
              <button
                className="danger"
                onClick={() => post("/oauth/twitch/disconnect")}
              >
                <Unplug />
                Odłącz
              </button>
            </div>
          </>
        ) : (
          <a className="button" href="/wot/api/oauth/twitch/connect">
            <Link2 />
            Połącz Twitch
          </a>
        )}
      </section>
      <section className="panel">
        <h2>Discord webhook</h2>
        <p>
          Stan: <b>{discord.configured ? "skonfigurowany" : "nieaktywny"}</b>.
        </p>
        <form onSubmit={saveDiscord}>
          <label>
            Nowy webhook
            <input name="webhook" type="password" autoComplete="off" />
          </label>
          <button>Zapisz</button>
        </form>
      </section>
      {msg && <div className="notice">{msg}</div>}
      <section className="panel">
        <h2>Ostatnie zdarzenia</h2>
        <div className="log">
          {logs.map((x) => (
            <div key={x.id}>
              <i className={x.level} />
              <span>
                <b>{x.message}</b>
                <small>{fmt(x.created_at)}</small>
              </span>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
