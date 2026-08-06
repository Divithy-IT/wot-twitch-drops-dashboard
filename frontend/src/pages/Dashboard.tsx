import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Campaign } from "../types";
import CampaignCard from "../components/CampaignCard";
import Calendar30 from "../components/Calendar30";
import { Radio, RefreshCw, AlertTriangle } from "lucide-react";
export default function Dashboard() {
  const [c, setC] = useState<Campaign[]>([]),
    [tw, setTw] = useState<any>({ connected: false }),
    [err, setErr] = useState("");
  const load = useCallback(
    () =>
      Promise.all([api<Campaign[]>("/campaigns"), api("/oauth/twitch/status")])
        .then(([a, b]) => {
          setC(a);
          setTw(b);
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
  const current = c.filter((x) => x.status !== "ended"),
    auto = current.filter((x) => x.auto_approved);
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
      <h1>Potwierdzone kampanie Drops</h1>
      <Section
        title="Wysoka wartość"
        icon={<Radio />}
        items={auto.filter((x) => x.reward_value === "high")}
        edit={edit}
      />
      <Section
        title="Średnia wartość"
        items={auto.filter((x) => x.reward_value === "medium")}
        edit={edit}
      />
      <Section
        title="Zwykłe Dropy"
        items={auto.filter(
          (x) => x.reward_value === "low" || x.reward_value === "unknown",
        )}
        edit={edit}
      />
      <Section
        title="Wymagające decyzji / zatwierdzone ręcznie"
        items={current.filter((x) => !x.auto_approved)}
        edit={edit}
      />
      <Section
        title="Historia nagród"
        items={c.filter((x) => x.status === "ended")}
        edit={edit}
      />
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
