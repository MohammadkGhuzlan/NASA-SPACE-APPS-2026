import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useSearch } from "wouter";
import { ArrowRight, Check, Loader2, PenLine, Search, Trash2, Undo2 } from "lucide-react";
import { getSearchLocationsQueryKey, useListCaseStudies, useSearchLocations, type CaseStudy } from "@workspace/api-client-react";
import { PageHead, Shell, Tag } from "@/components/shell";
import { LocationMap } from "@/components/location-map";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fmtCoord, savePending } from "@/lib/field";

type Pt = [number, number];

export default function SelectLocation() {
  const [, navigate] = useLocation();
  const search = useSearch();
  const cases = useListCaseStudies();
  const [q, setQ] = useState("");
  const [submitted, setSubmitted] = useState("");
  const results = useSearchLocations({ q: submitted }, { query: { enabled: submitted.length >= 2, queryKey: getSearchLocationsQueryKey({ q: submitted }) } });

  const [point, setPoint] = useState<Pt | null>(null);
  const [name, setName] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [manualErr, setManualErr] = useState("");
  const [drawing, setDrawing] = useState(false);
  const [vertices, setVertices] = useState<Pt[]>([]);
  const [closed, setClosed] = useState(false);

  function choose(p: Pt, label: string) {
    setPoint(p); setName(label); setLat(p[0].toFixed(5)); setLon(p[1].toFixed(5));
  }
  const pick = (c: CaseStudy) => choose([c.latitude, c.longitude], `${c.name}, ${c.country}`);

  useEffect(() => {
    const name = new URLSearchParams(search).get("case");
    const c = cases.data?.find((x) => x.name === name);
    if (c) choose([c.latitude, c.longitude], `${c.name}, ${c.country}`);
  }, [cases.data, search]);

  function onMapClick(p: Pt) {
    if (drawing && !closed) { setVertices((v) => [...v, p]); return; }
    if (!drawing) choose(p, name || `Pinned point ${fmtCoord(p[0], p[1])}`);
  }

  function applyManual(e: FormEvent) {
    e.preventDefault();
    const a = Number(lat), b = Number(lon);
    if (!lat || !lon || Number.isNaN(a) || Number.isNaN(b) || a < -90 || a > 90 || b < -180 || b > 180) {
      setManualErr("Latitude must be -90 to 90 and longitude -180 to 180."); return;
    }
    setManualErr(""); choose([a, b], name || `Point ${fmtCoord(a, b)}`);
  }

  function confirm() {
    if (!point) return;
    const boundary = closed && vertices.length >= 3
      ? { type: "Polygon" as const, coordinates: [[...vertices.map(([a, b]) => [b, a]), [vertices[0][1], vertices[0][0]]]] }
      : undefined;
    savePending({ locationName: name.trim() || fmtCoord(point[0], point[1]), latitude: point[0], longitude: point[1], boundary });
    navigate("/farms/new");
  }

  return (
    <Shell>
      <div className="mx-auto max-w-7xl px-5 py-12">
        <PageHead eyebrow="Step 1 of 2" title={<>Find your <span className="italic text-accent">field</span></>}>
          Search anywhere on Earth, click the map, or type coordinates. Optionally trace the boundary.
        </PageHead>
        <div className="grid lg:grid-cols-[380px_1fr] gap-6">
          <aside className="space-y-5 order-2 lg:order-1">
            <form onSubmit={(e) => { e.preventDefault(); setSubmitted(q.trim()); }} className="rounded-3xl border border-card-border bg-card p-5">
              <label htmlFor="q" className="text-sm font-semibold">Search places</label>
              <div className="mt-2 flex gap-2">
                <Input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Town, region, landmark" data-testid="input-search" />
                <Button type="submit" size="icon" disabled={q.trim().length < 2} aria-label="Search" data-testid="button-search">
                  {results.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                </Button>
              </div>
              {submitted && !results.isFetching && (
                <div className="mt-3 max-h-56 overflow-auto space-y-1">
                  {results.isError && <p className="text-sm text-destructive">Search failed. Try again or click the map.</p>}
                  {results.data?.length === 0 && <p className="text-sm text-muted-foreground">No places found for "{submitted}".</p>}
                  {results.data?.map((r, i) => (
                    <button type="button" key={i} onClick={() => pick(r)} data-testid={`button-result-${i}`} className="w-full rounded-xl px-3 py-2 text-left text-sm hover:bg-secondary transition-colors">
                      <span className="font-medium block truncate">{r.name}</span>
                      <span className="text-xs text-muted-foreground">{r.country} · {r.latitude.toFixed(3)}, {r.longitude.toFixed(3)}</span>
                    </button>
                  ))}
                </div>
              )}
            </form>

            <div className="rounded-3xl border border-card-border bg-card p-5">
              <div className="flex items-center justify-between"><p className="text-sm font-semibold">Case studies</p><Tag kind="unassessed">Not farms</Tag></div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {cases.isLoading && [0, 1, 2, 3].map((i) => <div key={i} className="h-14 rounded-xl bg-muted animate-pulse" />)}
                {cases.isError && <p className="col-span-2 text-sm text-muted-foreground">Unavailable right now.</p>}
                {cases.data?.map((c, i) => (
                  <button key={c.name} onClick={() => pick(c)} data-testid={`button-case-${i}`} className="rounded-xl border border-input px-3 py-2 text-left hover:border-primary/60 hover:bg-secondary/50 transition-all active:scale-[.98]">
                    <span className="block text-sm font-semibold text-primary">{c.name}</span>
                    <span className="text-xs text-muted-foreground">{c.country}</span>
                  </button>
                ))}
              </div>
            </div>

            <form onSubmit={applyManual} className="rounded-3xl border border-card-border bg-card p-5 space-y-3">
              <p className="text-sm font-semibold">Manual coordinates</p>
              <div className="grid grid-cols-2 gap-2">
                <Input aria-label="Latitude" placeholder="Latitude" value={lat} onChange={(e) => setLat(e.target.value)} inputMode="decimal" data-testid="input-lat" />
                <Input aria-label="Longitude" placeholder="Longitude" value={lon} onChange={(e) => setLon(e.target.value)} inputMode="decimal" data-testid="input-lon" />
              </div>
              {manualErr && <p className="text-xs text-destructive">{manualErr}</p>}
              <Button type="submit" variant="outline" className="w-full rounded-full" data-testid="button-apply-coords">Place pin</Button>
            </form>
          </aside>

          <div className="order-1 lg:order-2 space-y-4">
            <div className="relative overflow-hidden rounded-[2rem] border border-card-border shadow-xl shadow-primary/10">
              <LocationMap point={point} vertices={vertices} closed={closed} drawing={drawing} onMapClick={onMapClick} className="h-[420px] md:h-[560px] w-full" />
              <div className="absolute top-4 right-4 z-[500] flex flex-wrap justify-end gap-2">
                {!drawing ? (
                  <Button size="sm" variant="secondary" className="rounded-full shadow" onClick={() => { setDrawing(true); setVertices([]); setClosed(false); }} data-testid="button-draw">
                    <PenLine className="h-4 w-4" /> Draw boundary
                  </Button>
                ) : (
                  <>
                    <Button size="sm" variant="secondary" className="rounded-full shadow" disabled={!vertices.length || closed} onClick={() => setVertices((v) => v.slice(0, -1))} data-testid="button-undo-vertex"><Undo2 className="h-4 w-4" />Undo</Button>
                    <Button size="sm" className="rounded-full shadow" disabled={vertices.length < 3 || closed} onClick={() => { setClosed(true); setDrawing(false); }} data-testid="button-finish-boundary"><Check className="h-4 w-4" />Finish</Button>
                    <Button size="sm" variant="secondary" className="rounded-full shadow" onClick={() => { setVertices([]); setClosed(false); setDrawing(false); }} data-testid="button-cancel-draw">Cancel</Button>
                  </>
                )}
                {closed && !drawing && (
                  <Button size="sm" variant="secondary" className="rounded-full shadow" onClick={() => { setVertices([]); setClosed(false); }} data-testid="button-clear-boundary"><Trash2 className="h-4 w-4" />Clear boundary</Button>
                )}
              </div>
              {drawing && (
                <div className="absolute bottom-4 left-4 z-[500] rounded-full bg-primary px-4 py-2 text-xs font-medium text-primary-foreground shadow">
                  Click to add vertices · {vertices.length} placed{vertices.length < 3 ? ` · need ${3 - vertices.length} more` : ""}
                </div>
              )}
            </div>

            <div className={cn("rounded-3xl border bg-card p-5 flex flex-col md:flex-row md:items-center gap-4 transition-all", point ? "border-primary/40" : "border-card-border")}>
              <div className="flex-1 space-y-2">
                {point ? (
                  <>
                    <Input value={name} onChange={(e) => setName(e.target.value)} aria-label="Location name" className="font-display text-lg" data-testid="input-selected-name" />
                    <p className="font-mono text-xs text-muted-foreground" data-testid="text-selected-coords">{fmtCoord(point[0], point[1])}{closed ? ` · boundary with ${vertices.length} vertices` : ""}</p>
                  </>
                ) : (
                  <p className="text-muted-foreground">No location chosen yet. Click anywhere on the map.</p>
                )}
              </div>
              <Button size="lg" className="rounded-full px-7" disabled={!point || drawing} onClick={confirm} data-testid="button-confirm-location">
                Confirm location <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
