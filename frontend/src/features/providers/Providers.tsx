import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapContainer, Marker, TileLayer, useMap } from "react-leaflet";
import { api, ApiError } from "../../lib/api";
import type { Provider } from "../../lib/types";
import { Icon } from "../../components/icons/Icon";
import { ErrorNote, Field, PageTitle, useDocTitle } from "../../components/ui";

const pin = (color: string) => L.divIcon({
  className: "", iconSize: [26, 26], iconAnchor: [13, 13],
  html: `<span style="display:block;width:26px;height:26px;background:${color};border:3px solid #14304f;border-radius:4px"></span>`,
});
const BLUE = pin("#2f6fde"), GREEN = pin("#2e9e5b");
const LABEL = "Suggestion only, not a guarantee of availability or suitability";

function Fit({ pts }: { pts: Provider[] }) {
  const map = useMap();
  useEffect(() => { if (pts.length) map.fitBounds(L.latLngBounds(pts.map((p) => [p.lat, p.lng] as [number, number])), { padding: [40, 40], maxZoom: 14 }); }, [pts, map]);
  return null;
}

/** Screen 7: provider map. GPS first, State > District > Area as the fallback. Specialty comes from the task. */
export default function Providers() {
  useDocTitle("Find a provider");
  const { taskId = "" } = useParams();
  const [sp] = useSearchParams();
  const specialty = sp.get("specialty") ?? "";
  const pid = sp.get("pid") ?? "";
  const nav = useNavigate();
  const [state, setState] = useState(""); const [district, setDistrict] = useState(""); const [area, setArea] = useState("");
  const [results, setResults] = useState<Provider[] | null>(null);
  const [sel, setSel] = useState<Provider | null>(null);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const states = useQuery({ queryKey: ["states"], queryFn: () => api<string[]>("/locations/states") });
  const districts = useQuery({ queryKey: ["districts", state], enabled: !!state, queryFn: () => api<string[]>(`/locations/districts?state=${encodeURIComponent(state)}`) });
  const areas = useQuery({ queryKey: ["areas", state, district], enabled: !!district, queryFn: () => api<string[]>(`/locations/areas?state=${encodeURIComponent(state)}&district=${encodeURIComponent(district)}`) });

  async function search(qs: string) {
    setErr(""); setSel(null); setBusy(true);
    try { const r = await api<{ results: Provider[] }>(`/providers?specialty=${encodeURIComponent(specialty)}&${qs}`); setResults(r.results); if (!r.results.length) setErr("No matching providers in that area."); }
    catch (x) { setErr(x instanceof ApiError ? x.message : "Search failed."); } finally { setBusy(false); }
  }
  function gps() {
    if (!navigator.geolocation) return setErr("This browser cannot share a location. Choose an area instead.");
    navigator.geolocation.getCurrentPosition((p) => void search(`lat=${p.coords.latitude}&lng=${p.coords.longitude}`),
      () => setErr("Location was not shared. Choose State, District and Area instead."), { timeout: 10000 });
  }
  async function choose() {
    if (!sel) return;
    try { await api(`/tasks/${taskId}/provider`, { method: "POST", json: { provider_id: sel.id } }); nav(`/hub/plan/${pid}`); }
    catch (x) { setErr(x instanceof ApiError ? x.message : "Could not save your choice."); }
  }

  return (
    <div>
      <PageTitle icon="location" sub={LABEL}>Find a provider</PageTitle>
      <section className="tile mb-6 flex flex-col gap-4 p-5" aria-label="Location">
        <Field label="Specialty"><input className="field" value={specialty} readOnly aria-readonly /></Field>
        <button className="btn btn-primary self-start" onClick={gps} disabled={busy}><Icon name="location" size={22} className="duo-on-teal !text-ground" />Use my location</button>
        <p className="font-display font-semibold">Or choose an area</p>
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="State"><select className="field" value={state} onChange={(e) => { setState(e.target.value); setDistrict(""); setArea(""); }}><option value="">Select</option>{states.data?.map((s) => <option key={s}>{s}</option>)}</select></Field>
          <Field label="District"><select className="field" value={district} disabled={!state} onChange={(e) => { setDistrict(e.target.value); setArea(""); }}><option value="">Select</option>{districts.data?.map((s) => <option key={s}>{s}</option>)}</select></Field>
          <Field label="Area"><select className="field" value={area} disabled={!district} onChange={(e) => setArea(e.target.value)}><option value="">Select</option>{areas.data?.map((s) => <option key={s}>{s}</option>)}</select></Field>
        </div>
        <button className="btn btn-plain self-start" disabled={!area || busy} onClick={() => void search(`state=${encodeURIComponent(state)}&district=${encodeURIComponent(district)}&area=${encodeURIComponent(area)}`)}>Show providers</button>
      </section>
      {err && <div className="mb-4"><ErrorNote>{err}</ErrorNote></div>}
      {results && results.length > 0 && (
        <section aria-label="Map" className="relative">
          <div className="h-[28rem] border-2 border-ink" style={{ borderRadius: 4 }}>
            <MapContainer center={[results[0].lat, results[0].lng]} zoom={13} className="h-full w-full" scrollWheelZoom={false}>
              <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <Fit pts={results} />
              {results.map((p) => <Marker key={p.id} position={[p.lat, p.lng]} icon={p.type === "hospital" ? BLUE : GREEN} eventHandlers={{ click: () => setSel(p) }} />)}
            </MapContainer>
          </div>
          <p className="mt-2 flex gap-5 text-sm"><span><span className="mr-1 inline-block h-3 w-3 bg-pending" />Hospitals</span><span><span className="mr-1 inline-block h-3 w-3 bg-done" />Local clinics and doctors</span></p>
          <ul className="mt-4 flex flex-col gap-2">{results.map((p) => (
            <li key={p.id}><button className={`flex w-full items-center gap-3 p-3 text-left ${sel?.id === p.id ? "border-[3px] border-teal bg-ground-deep" : "tile"}`} style={{ borderRadius: 4 }} onClick={() => setSel(p)}>
              <span className={`h-4 w-4 shrink-0 ${p.type === "hospital" ? "bg-pending" : "bg-done"}`} /><span className="flex-1 font-display font-semibold">{p.name}<span className="block text-sm font-normal text-ink-soft">{p.facility}</span></span><span>{p.distance_km} km</span></button></li>))}</ul>
        </section>)}
      {sel && (
        <section role="dialog" aria-label="Provider details" className="sticky bottom-0 mt-4 border-2 border-ink bg-tile p-5" style={{ borderRadius: 4 }}>
          <p className="font-display text-xl font-bold">{sel.name}</p>
          <p>{sel.specialty}, {sel.facility}</p>
          <p className="text-ink-soft">{sel.distance_km} km away (synthetic). Contact {sel.contact}</p>
          <p className="mt-1 text-sm font-semibold">{LABEL}</p>
          <div className="mt-3 flex gap-3"><button className="btn btn-primary" onClick={choose}>Select this provider</button><button className="btn btn-plain" onClick={() => setSel(null)}>Close</button></div>
        </section>)}
    </div>
  );
}
