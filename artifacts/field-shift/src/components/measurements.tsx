import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import {
  useListMeasurements, useSaveMeasurement, useGetFarmFeatures,
  getListMeasurementsQueryKey, getGetFarmFeaturesQueryKey,
  type MeasurementInput, type MeasurementInputParameter, type MeasurementInputUnit, type MeasurementInputSource,
} from "@workspace/api-client-react";
import { Tag } from "@/components/shell";
import { Section, Unavailable, errMessage, Note } from "@/components/env-kit";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";

const PARAMS: Record<MeasurementInputParameter, { label: string; units: MeasurementInputUnit[]; range: [number, number] }> = {
  clay_pct: { label: "Clay", units: ["%"], range: [0, 100] },
  sand_pct: { label: "Sand", units: ["%"], range: [0, 100] },
  silt_pct: { label: "Silt", units: ["%"], range: [0, 100] },
  ph: { label: "pH", units: ["pH"], range: [0, 14] },
  soc_g_kg: { label: "Soil organic carbon", units: ["g/kg", "g/100g"], range: [0, 1000] },
  soil_moisture: { label: "Soil moisture", units: ["%", "m3/m3"], range: [0, 100] },
};
const sel = "h-9 w-full rounded-md border border-input bg-background px-3 text-sm";

export function Measurements({ farmId }: { farmId: number }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const list = useListMeasurements(farmId);
  const save = useSaveMeasurement();
  const today = new Date().toISOString().slice(0, 10);
  const [f, setF] = useState({ parameter: "ph" as MeasurementInputParameter, value: "", unit: "pH" as MeasurementInputUnit, top: "0", bottom: "5", measuredOn: today, source: "farmer_reported" as MeasurementInputSource, notes: "" });
  const [err, setErr] = useState("");
  const set = (k: keyof typeof f, v: string) => setF((p) => ({ ...p, [k]: v }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const spec = PARAMS[f.parameter];
    const value = Number(f.value);
    if (f.value.trim() === "" || Number.isNaN(value)) return setErr("Enter a numeric value.");
    let max = spec.range[1];
    if (f.parameter === "soil_moisture" && f.unit === "m3/m3") max = 1;
    if (f.parameter === "soc_g_kg" && f.unit === "g/100g") max = 100;
    if (value < spec.range[0] || value > max) return setErr(`${spec.label} must be between ${spec.range[0]} and ${max} ${f.unit}.`);
    const top = f.top === "" ? null : Number(f.top), bottom = f.bottom === "" ? null : Number(f.bottom);
    if ((top !== null && Number.isNaN(top)) || (bottom !== null && Number.isNaN(bottom))) return setErr("Depths must be numbers in cm.");
    if (f.parameter === "soil_moisture" && (top === null || bottom === null)) return setErr("Soil moisture requires both depth values.");
    if (top !== null && bottom !== null && (top < 0 || bottom <= top)) return setErr("Bottom depth must be greater than top depth (cm, from 0).");
    if (!f.measuredOn || f.measuredOn > today) return setErr("Measurement date is required and cannot be in the future.");
    setErr("");
    const data: MeasurementInput = { parameter: f.parameter, value, unit: f.unit, depthTopCm: top, depthBottomCm: bottom, measuredOn: f.measuredOn, source: f.source, notes: f.notes.trim() || undefined };
    save.mutate({ id: farmId, data }, {
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: getListMeasurementsQueryKey(farmId) });
        qc.invalidateQueries({ queryKey: getGetFarmFeaturesQueryKey(farmId) });
        toast({ title: "Measurement recorded" });
        setF((p) => ({ ...p, value: "", notes: "" }));
      },
      onError: (e2) => setErr(errMessage(e2)),
    });
  };

  return (
    <Section eyebrow="Your observations" title="Recorded soil measurements" testid="section-measurements" actions={<Tag kind="farmer">Self-reported</Tag>}>
      <form onSubmit={submit} className="grid sm:grid-cols-2 gap-3 text-xs font-semibold" data-testid="form-measurement">
        <label>Parameter
          <select className={sel} value={f.parameter} data-testid="select-parameter"
            onChange={(e) => { const p = e.target.value as MeasurementInputParameter; setF((o) => ({ ...o, parameter: p, unit: PARAMS[p].units[0]! })); }}>
            {Object.entries(PARAMS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </label>
        <div className="grid grid-cols-[1fr_110px] gap-2">
          <label>Value<Input value={f.value} onChange={(e) => set("value", e.target.value)} inputMode="decimal" data-testid="input-measure-value" /></label>
          <label>Unit<select className={sel} value={f.unit} onChange={(e) => set("unit", e.target.value)} data-testid="select-unit">{PARAMS[f.parameter].units.map((u) => <option key={u} value={u}>{u}</option>)}</select></label>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <label>Depth top (cm){f.parameter === "soil_moisture" && " *"}<Input value={f.top} onChange={(e) => set("top", e.target.value)} inputMode="decimal" data-testid="input-depth-top" /></label>
          <label>Depth bottom (cm){f.parameter === "soil_moisture" && " *"}<Input value={f.bottom} onChange={(e) => set("bottom", e.target.value)} inputMode="decimal" data-testid="input-depth-bottom" /></label>
        </div>
        <label>Measured on<Input type="date" max={today} value={f.measuredOn} onChange={(e) => set("measuredOn", e.target.value)} data-testid="input-measured-on" /></label>
        <label>Source
          <select className={sel} value={f.source} onChange={(e) => set("source", e.target.value)} data-testid="select-source">
            <option value="farmer_reported">Farmer reported</option>
            <option value="laboratory_confirmed">Laboratory confirmed (self-reported)</option>
          </select>
        </label>
        <label>Notes<Input value={f.notes} maxLength={500} onChange={(e) => set("notes", e.target.value)} data-testid="input-measure-notes" /></label>
        {err && <p className="sm:col-span-2 text-sm font-normal text-destructive" role="alert" data-testid="text-measure-error">{err}</p>}
        <div className="sm:col-span-2"><Button type="submit" className="rounded-full" disabled={save.isPending} data-testid="button-save-measurement">{save.isPending ? "Saving" : "Record measurement"}</Button></div>
      </form>
      <Note>"Laboratory confirmed" is your own statement and is not independently verified by Field Shift. Only 0–5 cm measurements with matching units can be used beside the 0–5 cm soil proxy.</Note>

      <div className="mt-5">
        {list.isLoading ? <Skeleton className="h-24 rounded-2xl" /> : list.isError ? <Unavailable title="History unavailable" detail={errMessage(list.error)} onRetry={() => list.refetch()} testid="measurements" />
          : !list.data?.length ? <p className="text-sm text-muted-foreground rounded-2xl border border-dashed border-input p-5 text-center">No recorded observations yet. Profile fields entered at farm creation are shown separately as legacy profile values.</p>
          : (
            <ul className="divide-y divide-border" data-testid="list-measurements">
              {list.data.map((m) => (
                <li key={m.id} className="py-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm" data-testid={`row-measurement-${m.id}`}>
                  <span className="font-semibold w-36">{PARAMS[m.parameter]?.label ?? m.parameter}</span>
                  <span className="font-display text-lg text-primary">{m.value} <span className="text-xs font-sans text-muted-foreground">{m.unit}</span></span>
                  <span className="font-mono text-xs text-muted-foreground">{m.depthTopCm ?? "?"}–{m.depthBottomCm ?? "?"} cm · {m.measuredOn}</span>
                  <span className="flex gap-1.5">
                    <Tag kind="farmer">{m.source === "laboratory_confirmed" ? "Lab, self-reported" : "Farmer reported"}</Tag>
                    <Tag kind="unassessed"><ShieldAlert className="h-3 w-3" />{m.verification}</Tag>
                  </span>
                  {m.notes && <span className="basis-full text-xs text-muted-foreground">{m.notes}</span>}
                </li>
              ))}
            </ul>
          )}
      </div>
    </Section>
  );
}

function show(v: unknown): string {
  if (v === null || v === undefined) return "none";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function FeatureInputs({ farmId }: { farmId: number }) {
  const q = useGetFarmFeatures(farmId);
  const rec = q.data;
  const soil = rec && typeof rec.soilInputs === "object" && rec.soilInputs !== null ? (rec.soilInputs as Record<string, unknown>) : null;
  return (
    <Section eyebrow="Input provenance" title="Which source each soil input uses" testid="section-features">
      {q.isLoading ? <Skeleton className="h-24 rounded-2xl" /> : q.isError || !rec ? <Unavailable title="Input summary unavailable" detail={errMessage(q.error)} onRetry={() => q.refetch()} testid="features" />
        : !soil || !Object.keys(soil).length ? <p className="text-sm text-muted-foreground">No soil inputs resolved.</p>
        : (
          <dl className="divide-y divide-border text-sm">
            {Object.entries(soil).map(([k, v]) => {
              const o = v && typeof v === "object" ? (v as Record<string, unknown>) : null;
              return (
                <div key={k} className="py-2 grid grid-cols-[120px_1fr] gap-3" data-testid={`row-feature-${k}`}>
                  <dt className="font-mono text-xs">{k}</dt>
                  <dd className="break-words">{o ? Object.entries(o).map(([a, b]) => <span key={a} className="mr-3"><span className="text-muted-foreground">{a}:</span> {show(b)}</span>) : show(v)}</dd>
                </div>
              );
            })}
          </dl>
        )}
      <Note>A recorded measurement is chosen only when it covers exactly 0–5 cm with the same variable and unit; otherwise the regional proxy is shown. Nothing here is trained or labeled.</Note>
    </Section>
  );
}
