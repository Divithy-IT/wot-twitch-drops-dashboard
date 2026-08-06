import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Campaign } from "../types";
import CampaignCard from "../components/CampaignCard";
import Calendar30 from "../components/Calendar30";
import { Radio, RefreshCw, AlertTriangle } from "lucide-react";
export default function Dashboard() {
  const [c, setC] = useState<Campaign[]>([]),
    [tw, setTw] = useState<any>({ connected: false }),
    [disk, setDisk] = useState<any>(null),
    [err, setErr] = useState("");
  const load = useCallback(
    () =>
      Promise.all([api<Campaign[]>("/campaigns"), api("/oauth/twitch/status"), api("/disk/status")])
        .then(([a, b, d]) => {
          setC(a);
          setTw(b);
          setDisk(d);
          setErr("");
        })
        .catch((e) => setErr(e.message)),
    [],
  );
  useEffect(() => {
    load();
    const poll = setInterval(load, 60000);
    return () => clearInterval(poll);
  }, [load]);
  async function edit(x: Campaign) {
    const v = prompt(
      "Ręcznie potwierdzone obejrzane minuty:",
      String(x.watched_minutes),
    );
    if (v !== null)
      await api(`/campaigns/${x.id}/progress`, {
        method: "PATCH",
        body: JSON.stringify({ watched_minutes: Number(v), source: "manual" }),
      }).then(load);
  }
  const current = c.filter((x) => !x.archived && ["active", "upcoming", "recent_announcement", "unknown_date_recent"].includes(x.freshness_status)),
    auto = current.filter((x) => x.auto_approved),
    historical = c.filter((x) => x.freshness_status === "historical"),
    references = c.filter((x) => x.freshness_status === "reference_document");
  return (
    <>
      <div className="pagehead">
        <div>
          <span className="eyebrow">CENTRUM WYDARZEŃ</span>
          <h1>World of Tanks</h1>
          <p>
            Potwierdzone kampanie Drops i propozycje ręczne są zawsze
            rozdzielone.
          </p>
        </div>
        <button className="icon" onClick={load}>
          <RefreshCw />
        </button>
      </div>
      {err && (
        <div className="notice error">
          <AlertTriangle />
          {err}
        </div>
      )}
      {disk && disk.used_percent >= 80 && <div className={`notice ${disk.used_percent >= 90 ? "error" : ""}`}>
        <AlertTriangle /> Dysk VPS: {disk.used_percent}% zajęte, wolne {(disk.free_bytes / 1024 / 1024 / 1024).toFixed(1)} GiB.
      </div>}
      <section className="status-grid">
        <div className="status-card">
          <i className={tw.connected ? "green" : "red"} />
          <div>
            <small>TWITCH API</small>
            <strong>
              {tw.connected ? `Połączono: ${tw.login}` : "Brak autoryzacji"}
            </strong>
          </div>
        </div>
        <div className="status-card">
          <i className="green" />
          <div>
            <small>AUTO KWALIFIKACJA</small>
            <strong>{auto.length} potwierdzonych kampanii</strong>
          </div>
        </div>
        <div className="status-card">
          <i className="orange" />
          <div>
            <small>POSTĘP DROPS</small>
            <strong>Wyłącznie ręczny — brak API widza</strong>
          </div>
        </div>
      </section>
      <div className="limitation">
        <AlertTriangle />
        <span>
          Automat zatwierdza tylko jednoznaczne Twitch Drops z zaufanego źródła.{" "}
          <a
            href="https://www.twitch.tv/drops/inventory"
            target="_blank"
            rel="noreferrer"
          >
            Drops Inventory
          </a>
          .
        </span>
      </div>
      <Calendar30 />
      <h1>Jakie Twitch Drops możesz zdobyć teraz lub wkrótce?</h1>
      <Section
        title="Aktywne teraz"
        icon={<Radio />}
        items={auto.filter((x) => x.freshness_status === "active")}
        edit={edit}
      />
      <Section
        title="Nadchodzące"
        items={auto.filter((x) => x.freshness_status === "upcoming")}
        edit={edit}
      />
      <Section
        title="Świeże zapowiedzi"
        items={auto.filter((x) => ["recent_announcement", "unknown_date_recent"].includes(x.freshness_status))}
        edit={edit}
      />
      <Section
        title="Ręcznie zatwierdzone aktualne kampanie"
        items={current.filter((x) => !x.auto_approved)}
        edit={edit}
      />
      <details><summary>Archiwum i materiały historyczne ({historical.length})</summary>
        <Section title="Archiwum" items={historical} edit={edit} />
      </details>
      <details><summary>Poradniki i dokumenty referencyjne ({references.length})</summary>
        <Section title="Poradniki i źródła" items={references} edit={edit} />
      </details>
    </>
  );
}
function Section({
  title,
  icon,
  items,
  edit,
}: {
  title: string;
  icon?: any;
  items: Campaign[];
  edit: (x: Campaign) => void;
}) {
  return (
    <section>
      <h2>
        {icon}
        {title}
        <span>{items.length}</span>
      </h2>
      <div className="cards">
        {items.length ? (
          items.map((x) => <CampaignCard key={x.id} c={x} onProgress={edit} />)
        ) : (
          <div className="empty">Brak kampanii w tej sekcji.</div>
        )}
      </div>
    </section>
  );
}
