import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import { Campaign } from "../types";
import CampaignCard from "../components/CampaignCard";
const local = (iso: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};
export default function Campaigns() {
  const [c, setC] = useState<Campaign[]>([]),
    [editing, setEditing] = useState<Campaign | null | undefined>(undefined),
    [err, setErr] = useState("");
  const load = () => api<Campaign[]>("/campaigns").then(setC);
  useEffect(() => {
    load();
  }, []);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget),
      mins = Number(f.get("required_minutes"));
    const body = {
      title: f.get("title"),
      description: f.get("description"),
      starts_at: new Date(String(f.get("starts_at"))).toISOString(),
      ends_at: new Date(String(f.get("ends_at"))).toISOString(),
      required_minutes: mins,
      eligible_channels: String(f.get("channels") || "")
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean),
      category_name: "World of Tanks",
      link_url: f.get("link_url"),
      source_type: f.get("source_type"),
      source_url: f.get("source_url") || null,
      rewards: String(f.get("rewards") || "")
        .split(",")
        .filter(Boolean)
        .map((x) => {
          const [name, threshold] = x.split(":");
          return {
            name: name.trim(),
            required_minutes: Number(threshold) || mins,
          };
        }),
    };
    try {
      await api(editing ? `/campaigns/${editing.id}` : "/campaigns", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(body),
      });
      setEditing(undefined);
      load();
    } catch (x) {
      setErr((x as Error).message);
    }
  }
  async function remove() {
    if (editing && confirm(`Usunąć kampanię „${editing.title}”?`)) {
      await api(`/campaigns/${editing.id}`, { method: "DELETE" });
      setEditing(undefined);
      load();
    }
  }
  async function reward(
    x: Campaign,
    id: number,
    earned: boolean,
    claimed: boolean,
  ) {
    await api(
      `/campaigns/${x.id}/rewards/${id}?earned=${earned}&claimed=${claimed}`,
      { method: "PATCH" },
    );
    load();
  }
  return (
    <>
      <div className="pagehead">
        <div>
          <span className="eyebrow">ZARZĄDZANIE RĘCZNYMI DANYMI</span>
          <h1>Kampanie</h1>
          <p>
            Twitch nie udostępnia widzowi katalogu kampanii — tutaj zapisujesz
            dane z publicznych źródeł.
          </p>
        </div>
        <button
          onClick={() => setEditing(editing === undefined ? null : undefined)}
        >
          + Dodaj kampanię
        </button>
      </div>
      {editing !== undefined && (
        <form className="editor" onSubmit={submit}>
          <label>
            Nazwa
            <input name="title" required defaultValue={editing?.title} />
          </label>
          <label>
            Opis
            <textarea name="description" defaultValue={editing?.description} />
          </label>
          <div className="twocol">
            <label>
              Start
              <input
                name="starts_at"
                type="datetime-local"
                required
                defaultValue={editing ? local(editing.starts_at) : ""}
              />
            </label>
            <label>
              Koniec
              <input
                name="ends_at"
                type="datetime-local"
                required
                defaultValue={editing ? local(editing.ends_at) : ""}
              />
            </label>
          </div>
          <label>
            Wymagane minuty
            <input
              name="required_minutes"
              type="number"
              min="0"
              required
              defaultValue={editing?.required_minutes ?? ""}
            />
          </label>
          <label>
            Nagrody: nazwa:minuty, po przecinku
            <input
              name="rewards"
              defaultValue={editing?.rewards
                .map((r) => `${r.name}:${r.required_minutes}`)
                .join(", ")}
            />
          </label>
          <label>
            Kanały (po przecinku)
            <input
              name="channels"
              defaultValue={editing?.eligible_channels.join(", ")}
            />
          </label>
          <label>
            Link Twitch
            <input
              name="link_url"
              type="url"
              defaultValue={
                editing?.link_url ||
                "https://www.twitch.tv/directory/category/world-of-tanks"
              }
              required
            />
          </label>
          <label>
            Typ źródła
            <select
              name="source_type"
              defaultValue={editing?.source_type || "manual"}
            >
              <option value="manual">Ręczne</option>
              <option value="wargaming">Wargaming</option>
              <option value="twitch">Twitch</option>
            </select>
          </label>
          <label>
            Publiczne źródło
            <input
              name="source_url"
              type="url"
              defaultValue={editing?.source_url}
            />
          </label>
          {err && <div className="error">{err}</div>}
          <div className="actions">
            <button>Zapisz</button>
            <button
              type="button"
              className="secondary"
              onClick={() => setEditing(undefined)}
            >
              Anuluj
            </button>
            {editing && (
              <button type="button" className="danger" onClick={remove}>
                Usuń
              </button>
            )}
          </div>
        </form>
      )}
      <div className="cards">
        {c.map((x) => (
          <CampaignCard
            key={x.id}
            c={x}
            onEdit={setEditing}
            onReward={reward}
          />
        ))}
      </div>
    </>
  );
}
