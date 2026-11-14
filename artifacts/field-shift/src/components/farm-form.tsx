import { useState, type FormEvent, type ReactNode } from "react";
import { Loader2, MapPin } from "lucide-react";
import type { FarmInput, FarmInputGoal, FarmInputIrrigation } from "@workspace/api-client-react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Tag } from "@/components/shell";
import { cn } from "@/lib/utils";
import { fmtCoord, goalLabel, irrigationLabel } from "@/lib/field";

type Props = {
  initial: Partial<FarmInput> & Pick<FarmInput, "locationName" | "latitude" | "longitude">;
  submitLabel: string;
  pending: boolean;
  onSubmit: (data: FarmInput) => void;
  locationAction?: ReactNode;
};

const numStr = (n?: number | null) => (n === null || n === undefined ? "" : String(n));

function Field({ label, hint, error, children, id }: { label: string; hint?: string; error?: string; children: ReactNode; id: string }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-semibold text-foreground">{label}</label>
      {children}
      {error ? <p className="text-xs text-destructive">{error}</p> : hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function Choice<T extends string>({ value, options, labels, onChange, name }: { value: T; options: T[]; labels: Record<string, string>; onChange: (v: T) => void; name: string }) {
  return (
    <div role="radiogroup" className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {options.map((o) => (
        <button type="button" role="radio" aria-checked={value === o} key={o} onClick={() => onChange(o)} data-testid={`radio-${name}-${o}`}
          className={cn("rounded-xl border px-4 py-3 text-left text-sm font-medium transition-all active:scale-[.98]",
            value === o ? "border-primary bg-primary text-primary-foreground shadow-sm" : "border-input bg-card hover:border-primary/50")}>
          {labels[o]}
        </button>
      ))}
    </div>
  );
}

export function FarmForm({ initial, submitLabel, pending, onSubmit, locationAction }: Props) {
  const [name, setName] = useState(initial.name ?? "");
  const [locationName, setLocationName] = useState(initial.locationName);
  const [currentCrop, setCurrentCrop] = useState(initial.currentCrop ?? "");
  const [cropHistory, setCropHistory] = useState(initial.cropHistory ?? "");
  const [irrigation, setIrrigation] = useState<FarmInputIrrigation>(initial.irrigation ?? "rainfed");
  const [goal, setGoal] = useState<FarmInputGoal>(initial.goal ?? "conserve_water");
  const [soilType, setSoilType] = useState(initial.soilType ?? "");
  const [soilMoisture, setSoilMoisture] = useState(numStr(initial.soilMoisture));
  const [soilPh, setSoilPh] = useState(numStr(initial.soilPh));
  const [farmSize, setFarmSize] = useState(numStr(initial.farmSize));
  const [waterConstraints, setWaterConstraints] = useState(initial.waterConstraints ?? "");
  const [errors, setErrors] = useState<Record<string, string>>({});

  function submit(e: FormEvent) {
    e.preventDefault();
    const err: Record<string, string> = {};
    if (!name.trim()) err.name = "Give this farm a name.";
    if (!locationName.trim()) err.locationName = "Describe the location.";
    if (!currentCrop.trim()) err.currentCrop = "Enter what is growing now (or 'fallow').";
    const num = (s: string, key: string, min: number, max: number, exclusiveMin = false) => {
      if (!s.trim()) return null;
      const n = Number(s);
      if (Number.isNaN(n) || (exclusiveMin ? n <= min : n < min) || n > max) { err[key] = `Enter a number ${exclusiveMin ? "above" : "from"} ${min}${max < Infinity ? ` to ${max}` : ""}.`; return null; }
      return n;
    };
    const sm = num(soilMoisture, "soilMoisture", 0, 100);
    const ph = num(soilPh, "soilPh", 0, 14);
    const fs = num(farmSize, "farmSize", 0, Infinity, true);
    setErrors(err);
    if (Object.keys(err).length) return;
    const data: FarmInput = {
      name: name.trim(), locationName: locationName.trim(), latitude: initial.latitude, longitude: initial.longitude,
      currentCrop: currentCrop.trim(), irrigation, goal,
      soilMoisture: sm, soilPh: ph, farmSize: fs,
    };
    if (initial.boundary) data.boundary = initial.boundary;
    if (cropHistory.trim()) data.cropHistory = cropHistory.trim();
    if (soilType.trim()) data.soilType = soilType.trim();
    if (waterConstraints.trim()) data.waterConstraints = waterConstraints.trim();
    onSubmit(data);
  }

  const section = "rounded-3xl border border-card-border bg-card p-6 md:p-8 space-y-5 rise";

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      <section className={section}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-xs text-accent tracking-widest">01 / PLACE</p>
            <h2 className="font-display text-2xl text-primary mt-1">Where is the field?</h2>
          </div>
          {locationAction}
        </div>
        <div className="flex items-center gap-3 rounded-2xl bg-secondary/60 px-4 py-3 text-sm">
          <MapPin className="h-4 w-4 text-primary shrink-0" />
          <span className="font-mono" data-testid="text-coordinates">{fmtCoord(initial.latitude, initial.longitude)}</span>
          {initial.boundary && <Tag kind="farmer">Boundary drawn</Tag>}
        </div>
        <div className="grid md:grid-cols-2 gap-5">
          <Field id="name" label="Farm name" error={errors.name}>
            <Input id="name" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} placeholder="e.g. North terrace plots" data-testid="input-name" />
          </Field>
          <Field id="locationName" label="Location description" error={errors.locationName}>
            <Input id="locationName" value={locationName} maxLength={300} onChange={(e) => setLocationName(e.target.value)} data-testid="input-location-name" />
          </Field>
        </div>
      </section>

      <section className={section}>
        <p className="font-mono text-xs text-accent tracking-widest">02 / CROPS</p>
        <h2 className="font-display text-2xl text-primary -mt-3">What has this ground carried?</h2>
        <div className="grid md:grid-cols-2 gap-5">
          <Field id="currentCrop" label="Current crop" error={errors.currentCrop}>
            <Input id="currentCrop" value={currentCrop} maxLength={100} onChange={(e) => setCurrentCrop(e.target.value)} placeholder="e.g. durum wheat" data-testid="input-current-crop" />
          </Field>
          <Field id="farmSize" label="Farm size (hectares)" hint="Optional." error={errors.farmSize}>
            <Input id="farmSize" inputMode="decimal" value={farmSize} onChange={(e) => setFarmSize(e.target.value)} placeholder="e.g. 12.4" data-testid="input-farm-size" />
          </Field>
        </div>
        <Field id="cropHistory" label="Crop history" hint="Optional. Previous seasons in your own words.">
          <Textarea id="cropHistory" value={cropHistory} maxLength={1000} onChange={(e) => setCropHistory(e.target.value)} placeholder="2023 barley, 2024 chickpea, 2025 wheat" rows={3} data-testid="input-crop-history" />
        </Field>
      </section>

      <section className={section}>
        <p className="font-mono text-xs text-accent tracking-widest">03 / SOIL & WATER</p>
        <h2 className="font-display text-2xl text-primary -mt-3">Your own measurements</h2>
        <p className="text-sm text-muted-foreground -mt-2">Leave blank anything you have not measured. Blanks are saved as unknown, never estimated.</p>
        <div className="grid md:grid-cols-3 gap-5">
          <Field id="soilType" label="Soil type" hint="Optional.">
            <Input id="soilType" value={soilType} maxLength={100} onChange={(e) => setSoilType(e.target.value)} placeholder="e.g. clay loam" data-testid="input-soil-type" />
          </Field>
          <Field id="soilMoisture" label="Soil moisture (vol. %)" hint="Measured by you, 0–100." error={errors.soilMoisture}>
            <Input id="soilMoisture" inputMode="decimal" value={soilMoisture} onChange={(e) => setSoilMoisture(e.target.value)} data-testid="input-soil-moisture" />
          </Field>
          <Field id="soilPh" label="Soil pH" hint="0–14." error={errors.soilPh}>
            <Input id="soilPh" inputMode="decimal" value={soilPh} onChange={(e) => setSoilPh(e.target.value)} data-testid="input-soil-ph" />
          </Field>
        </div>
        <Field id="irrigation" label="Irrigation">
          <Choice name="irrigation" value={irrigation} options={["rainfed", "limited", "fully_irrigated"]} labels={irrigationLabel} onChange={(v) => setIrrigation(v as FarmInputIrrigation)} />
        </Field>
        <Field id="waterConstraints" label="Water constraints" hint="Optional. Quotas, well depth, salinity, shared canals.">
          <Textarea id="waterConstraints" value={waterConstraints} maxLength={1000} onChange={(e) => setWaterConstraints(e.target.value)} rows={2} data-testid="input-water-constraints" />
        </Field>
      </section>

      <section className={section}>
        <p className="font-mono text-xs text-accent tracking-widest">04 / INTENT</p>
        <h2 className="font-display text-2xl text-primary -mt-3">What matters most this cycle?</h2>
        <Choice name="goal" value={goal} options={["conserve_water", "soil_health", "productivity", "reduce_risk"]} labels={goalLabel} onChange={(v) => setGoal(v as FarmInputGoal)} />
      </section>

      <div className="flex justify-end">
        <Button type="submit" size="lg" disabled={pending} className="rounded-full px-8" data-testid="button-submit-farm">
          {pending && <Loader2 className="h-4 w-4 animate-spin" />}{submitLabel}
        </Button>
      </div>
    </form>
  );
}
