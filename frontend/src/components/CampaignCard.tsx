import { Campaign } from "../types";
import { duration, fmt } from "../api";
import { ExternalLink, Clock, ShieldCheck } from "lucide-react";
export default function CampaignCard({
  c,
  onProgress,
  onEdit,
  onReward,
}: {
  c: Campaign;
  onProgress?: (c: Campaign) => void;
  onEdit?: (c: Campaign) => void;
  onReward?: (
    c: Campaign,
    rewardId: number,
    earned: boolean,
    claimed: boolean,
  ) => void;
}) {
  const pct = Math.min(
      100,
      c.required_minutes ? (c.watched_minutes / c.required_minutes) * 100 : 0,
    ),
    status =
      c.status === "active"
        ? "Aktywna"
        : c.status === "upcoming"
          ? "Nadchodząca"
          : c.status === "confirmed"
            ? "Potwierdzone Drops"
            : "Zakończona";
  return (
    <article className="campaign">
      <header>
        <div>
          <div className="actions">
            <span className={`pill ${c.status}`}>{status}</span>
            {c.auto_approved && (
              <span className="pill high">
                AUTO · {c.confidence_score}/100 · {c.reward_value}
              </span>
            )}
          </div>
          <h3>{c.title}</h3>
        </div>
        <strong className="count">
          <Clock />
          {c.status === "confirmed"
            ? "Szczegóły oczekują"
            : duration(c.seconds_remaining)}
        </strong>
      </header>
      <p>{c.description}</p>
      {c.verification_reason && (
        <div className="notice ok">
          Drops potwierdzone oficjalnie — szczegóły oczekują na publikację
        </div>
      )}
      <div className="dates">
        <span>
          Start <b>{c.starts_at ? fmt(c.starts_at) : "Jeszcze nie podano"}</b>
        </span>
        <span>
          Koniec <b>{c.ends_at ? fmt(c.ends_at) : "Do uzupełnienia"}</b>
        </span>
      </div>
      <div className="progress-label">
        <span>
          {c.required_minutes == null
            ? "Wymagany czas: jeszcze nie podano"
            : `Obejrzano ${c.watched_minutes} z ${c.required_minutes} min`}
        </span>
        <b>{c.required_minutes ? `${pct.toFixed(1)}%` : "—"}</b>
      </div>
      <div className="bar">
        <i style={{ width: `${pct}%` }} />
      </div>
      <small>
        <ShieldCheck /> Źródło: {c.source_url || c.source_type}
      </small>
      <div className="rewards">
        {c.rewards.map((r) => (
          <button
            type="button"
            className={r.claimed ? "claimed" : r.earned ? "earned" : ""}
            key={r.id}
            onClick={() =>
              onReward?.(c, r.id, !r.earned, r.earned ? !r.claimed : false)
            }
          >
            {r.name}
            {r.name !== "Jeszcze nie podano" && ` · ${r.required_minutes} min`}
          </button>
        ))}
      </div>
      <footer>
        <div className="actions">
          <a href={c.link_url} target="_blank" rel="noreferrer">
            Stream <ExternalLink />
          </a>
          <a
            href="https://www.twitch.tv/drops/inventory"
            target="_blank"
            rel="noreferrer"
          >
            Drops Inventory <ExternalLink />
          </a>
        </div>
        <div className="card-actions">
          {onProgress && (
            <button className="secondary" onClick={() => onProgress(c)}>
              Postęp
            </button>
          )}
          {onEdit && (
            <button className="secondary" onClick={() => onEdit(c)}>
              Edytuj
            </button>
          )}
        </div>
      </footer>
    </article>
  );
}
