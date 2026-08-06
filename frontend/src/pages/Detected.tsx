import { useEffect, useState } from "react";
import { api, fmt } from "../api";
import { ExternalLink, RefreshCw, RotateCcw } from "lucide-react";
type D = {
  id: number;
  title: string;
  summary: string;
  published_at: string | null;
  starts_at: string | null;
  ends_at: string | null;
  required_minutes: number | null;
  source_url: string;
  source_name: string;
  last_checked_at: string;
  excerpt: string;
  confidence: "low" | "medium" | "high";
  event_type: string;
  status: string;
  probable_rewards: string[];
  qualification_decision: "auto_approve" | "manual_review" | "auto_ignore";
  confidence_score: number;
  reward_value: "high" | "medium" | "low" | "unknown";
  matched_keywords: string[];
  score_breakdown: { rule: string; points: number; reason: string }[];
  decision_reason: string;
  decided_by: string;
  decided_at: string | null;
};
const local = (x: string | null) =>
  x
    ? new Date(new Date(x).getTime() - new Date(x).getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16)
    : "";
const labels = {
  auto_approve: "Automatycznie zatwierdzone",
  manual_review: "Wymaga decyzji",
  auto_ignore: "Automatycznie zignorowane",
};
export default function Detected() {
  const [items, setItems] = useState<D[]>([]),
    [editing, setEditing] = useState<D | null>(null),
    [msg, setMsg] = useState(""),
    [filter, setFilter] = useState("all");
  const load = () => api<D[]>("/detected-events").then(setItems);
  useEffect(() => {
    load();
  }, []);
  async function sync() {
    const r: any = await api("/sources/sync", { method: "POST" });
    setMsg(
      `Sprawdzono: ${r.checked || 0}, nowe: ${r.created || 0}${r.cached ? " (cache)" : ""}`,
    );
    load();
  }
  async function action(id: number, path: string) {
    await api(`/detected-events/${id}/${path}`, { method: "POST" });
    load();
  }
  async function ignorePlainStreams() {
    const result: any = await api("/detected-events/bulk/ignore-streams", {
      method: "POST",
    });
    setMsg(`Zignorowano transmisje bez Drops: ${result.ignored}`);
    load();
  }
  async function reanalyze(id: number) {
    await api(`/detected-events/${id}/reanalyze`, { method: "POST" });
    setMsg("Ponownie pobrano i zakwalifikowano źródło.");
    load();
  }
  async function approve(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!editing) return;
    const f = new FormData(e.currentTarget);
    await api(`/detected-events/${editing.id}/approve`, {
      method: "POST",
      body: JSON.stringify({
        title: f.get("title"),
        description: f.get("description"),
        starts_at: new Date(String(f.get("starts"))).toISOString(),
        ends_at: new Date(String(f.get("ends"))).toISOString(),
        required_minutes: Number(f.get("minutes") || 0),
        eligible_channels: String(f.get("channels") || "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
        rewards: String(f.get("rewards") || "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
        link_url: editing.source_url,
      }),
    });
    setEditing(null);
    load();
  }
  const visible = items.filter((x) => {
    if (filter === "confirmed") return x.qualification_decision === "auto_approve";
    if (filter === "missing") return x.qualification_decision === "auto_approve" &&
      (!x.probable_rewards.length || x.required_minutes == null || !x.starts_at || !x.ends_at);
    if (filter === "streams") return x.qualification_decision === "auto_ignore" &&
      (x.event_type === "stream" || x.decision_reason.toLowerCase().includes("transmis"));
    if (filter === "manual") return x.qualification_decision === "manual_review";
    return true;
  });
  return (
    <>
      <div className="pagehead">
        <div>
          <span className="eyebrow">KWALIFIKACJA · AUDYTOWALNE DECYZJE</span>
          <h1>Wykryte wydarzenia</h1>
          <p>
            Potwierdzone Drops są oddzielone od zwykłych transmisji. Każda
            decyzja zachowuje uzasadnienie.
          </p>
        </div>
        <button onClick={sync}>
          <RefreshCw />
          Sprawdź teraz
        </button>
      </div>
      {msg && <div className="notice">{msg}</div>}
      {editing && (
        <form className="editor" onSubmit={approve}>
          <h2>Ręcznie zatwierdź kampanię</h2>
          <label>
            Tytuł
            <input name="title" defaultValue={editing.title} required />
          </label>
          <label>
            Opis
            <textarea name="description" defaultValue={editing.summary} />
          </label>
          <div className="twocol">
            <label>
              Start
              <input
                name="starts"
                type="datetime-local"
                defaultValue={local(editing.starts_at)}
                required
              />
            </label>
            <label>
              Koniec
              <input
                name="ends"
                type="datetime-local"
                defaultValue={local(editing.ends_at)}
                required
              />
            </label>
          </div>
          <label>
            Czas oglądania
            <input
              name="minutes"
              type="number"
              min="0"
              defaultValue={editing.required_minutes || 0}
            />
          </label>
          <label>
            Kanały
            <input name="channels" placeholder="worldoftanks" />
          </label>
          <label>
            Nagrody, po przecinku
            <input
              name="rewards"
              defaultValue={editing.probable_rewards.join(", ")}
            />
          </label>
          <div className="actions">
            <button>Zatwierdź</button>
            <button
              type="button"
              className="secondary"
              onClick={() => setEditing(null)}
            >
              Anuluj
            </button>
          </div>
        </form>
      )}
      <div className="filters">
        <button className="secondary" onClick={() => setFilter("confirmed")}>Drops potwierdzone oficjalnie</button>
        <button className="secondary" onClick={() => setFilter("missing")}>Brakuje tylko szczegółów</button>
        <button className="secondary" onClick={() => setFilter("streams")}>Zwykłe streamy bez Drops</button>
        <button className="secondary" onClick={() => setFilter("manual")}>Naprawdę wymagają decyzji</button>
        <button className="secondary" onClick={() => setFilter("all")}>Wszystkie</button>
        <button className="danger" onClick={ignorePlainStreams}>Zignoruj wszystkie transmisje bez wzmianki o Twitch Drops</button>
      </div>
      <div className="detected-grid">
        {visible.map((x) => (
          <article className={`detected ${x.status}`} key={x.id}>
            <header>
              <div className="actions">
                <span className={`pill score-${x.confidence_score}`}>
                  {x.confidence_score}/100
                </span>
                <span className={`pill value-${x.reward_value}`}>
                  Wartość: {x.reward_value}
                </span>
              </div>
              <span
                className={`source-tag ${x.qualification_decision === "auto_approve" ? "confirmed" : ""}`}
              >
                {labels[x.qualification_decision]}
              </span>
            </header>
            <h3>{x.title}</h3>
            <p>{x.summary}</p>
            <blockquote>{x.decision_reason}</blockquote>
            {x.matched_keywords.length > 0 && (
              <p>
                <b>Frazy:</b> {x.matched_keywords.join(", ")}
              </p>
            )}
            <ul className="score-list">
              {x.score_breakdown.map((b, i) => (
                <li key={i}>
                  <b>
                    {b.points > 0 ? "+" : ""}
                    {b.points}
                  </b>{" "}
                  {b.reason}
                </li>
              ))}
            </ul>
            <dl>
              <dt>Źródło</dt>
              <dd>{x.source_name}</dd>
              <dt>Termin</dt>
              <dd>
                {x.starts_at
                  ? `${fmt(x.starts_at)} — ${x.ends_at ? fmt(x.ends_at) : "brak końca"}`
                  : "Nie podano"}
              </dd>
              <dt>Czas</dt>
              <dd>
                {x.required_minutes == null
                  ? "Nie podano"
                  : `${x.required_minutes} min`}
              </dd>
              <dt>Decyzja</dt>
              <dd>
                {x.decided_by} · {x.decided_at ? fmt(x.decided_at) : "—"}
              </dd>
            </dl>
            <footer>
              <a href={x.source_url} target="_blank" rel="noreferrer">
                Źródło <ExternalLink />
              </a>
              <div className="actions">
                {x.status === "pending" && (
                  <>
                    <button onClick={() => setEditing(x)}>Zatwierdź</button>
                    <button
                      className="secondary"
                      onClick={() => reanalyze(x.id)}
                    >
                      Ponów analizę
                    </button>
                    <button
                      className="secondary"
                      onClick={() => action(x.id, "duplicate")}
                    >
                      Duplikat
                    </button>
                    <button
                      className="danger"
                      onClick={() => action(x.id, "reject")}
                    >
                      Odrzuć
                    </button>
                  </>
                )}
                {x.status !== "pending" && (
                  <button
                    className="secondary"
                    onClick={() => action(x.id, "undo")}
                  >
                    <RotateCcw />
                    Cofnij decyzję
                  </button>
                )}
              </div>
            </footer>
          </article>
        ))}
      </div>
    </>
  );
}
