import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { Bot, Loader2, Plus, X } from "lucide-react";
import {
  getListStrategiesQueryKey, useGetFarm, useListStrategies, useSaveStrategy,
  type Farm, type Strategy, type StrategyInputSlot,
} from "@workspace/api-client-react";
import { Shell, Tag } from "@/components/shell";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { FarmMissing } from "@/pages/farm-overview";
import { PlanReports } from "@/components/plan-reports";
import { goalLabel, irrigationLabel } from "@/lib/field";

function FarmContextSummary({ farm }: { farm: Farm }) {
  const missing = [
    !farm.cropHistory?.trim() && "Crop history",
    !farm.soilType?.trim() && "Soil type",
    farm.soilMoisture == null && "Soil moisture",
    farm.soilPh == null && "Soil pH",
    farm.farmSize == null && "Farm size",
    !farm.waterResources?.trim() && "Water resources",
    !farm.waterConstraints?.trim() && "Water constraints",
    !farm.agriculturalConstraints?.trim() && "Other farming constraints",
  ].filter((value): value is string => typeof value === "string");
  const checks = [
    (!farm.waterResources?.trim() || !farm.waterConstraints?.trim())
      ? "Check how much water you can use this season."
      : null,
    (!farm.soilType?.trim() || farm.soilPh == null || farm.soilMoisture == null)
      ? "To check this field's soil, use a new soil test. Empty boxes are not test results."
      : null,
    /rice/i.test(farm.currentCrop)
      ? "Rice can grow in dry ground or under water. Check which kind you grow."
      : null,
    "Ask a local farm helper before you change your crop plan.",
  ].filter((value): value is string => typeof value === "string");

  return (
    <section className="mb-6 rounded-3xl border border-card-border bg-card p-5 md:p-6" aria-labelledby="farm-context-heading" data-testid="farm-context-summary">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="farm-context-heading" className="font-display text-2xl text-primary">About this farm</h2>
        <Tag kind="farmer">You told us</Tag>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">These are the details you shared. Empty answers stay empty. We do not guess.</p>
      <dl className="mt-4 grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
        <div><dt className="text-xs text-muted-foreground">Current crop</dt><dd className="font-semibold">{farm.currentCrop}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Past crops</dt><dd className="font-semibold">{farm.cropHistory?.trim() || "Not added"}</dd></div>
        <div><dt className="text-xs text-muted-foreground">What matters most</dt><dd className="font-semibold">{goalLabel[farm.goal] ?? farm.goal}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Watering</dt><dd className="font-semibold">{irrigationLabel[farm.irrigation] ?? farm.irrigation}</dd></div>
      </dl>
      <div className="mt-5 grid gap-5 border-t border-border pt-4 md:grid-cols-2">
        <div>
          <h3 className="text-sm font-semibold">Details not added yet</h3>
          {missing.length
            ? <ul className="mt-2 flex flex-wrap gap-2">{missing.map((item) => <li key={item} className="rounded-full bg-muted px-3 py-1 text-xs">{item}: not added</li>)}</ul>
            : <p className="mt-2 text-sm text-muted-foreground">You filled in every box. We have not checked if the answers are true.</p>}
        </div>
        <div>
          <h3 className="text-sm font-semibold">Things to check</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">{checks.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </div>
    </section>
  );
}

function DraftEditor({ farmId, slot, label, existing }: { farmId: number; slot: StrategyInputSlot; label: string; existing?: Strategy }) {
  const [name, setName] = useState(existing?.name ?? `Alternative ${label}`);
  const [crops, setCrops] = useState<string[]>(existing?.crops?.length ? existing.crops : [""]);
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [error, setError] = useState("");
  const init = useRef(existing?.id);
  useEffect(() => {
    if (existing && init.current !== existing.id) {
      init.current = existing.id; setName(existing.name); setCrops(existing.crops.length ? existing.crops : [""]); setNotes(existing.notes);
    }
  }, [existing]);
  const save = useSaveStrategy();
  const qc = useQueryClient();
  const { toast } = useToast();

  function submit() {
    const clean = crops.map((c) => c.trim()).filter(Boolean);
    if (!name.trim()) return setError("Name this draft.");
    if (!clean.length) return setError("Add at least one crop.");
    setError("");
    save.mutate({ id: farmId, data: { slot, name: name.trim(), crops: clean, notes } }, {
      onSuccess: () => { qc.invalidateQueries({ queryKey: getListStrategiesQueryKey(farmId) }); toast({ title: `Draft ${label} saved` }); },
      onError: () => toast({ title: "Could not save draft", variant: "destructive" }),
    });
  }

  return (
    <div className="rounded-3xl border border-card-border bg-card p-6 flex flex-col gap-4 rise">
      <div className="flex items-center justify-between">
        <span className="font-display text-5xl italic text-accent leading-none">{label}</span>
        <div className="flex gap-2"><Tag kind="draft">Farmer draft</Tag>{existing && <Tag kind="farmer">Saved</Tag>}</div>
      </div>
      <Input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} aria-label={`Draft ${label} name`} className="font-display text-lg" data-testid={`input-draft-name-${slot}`} />
      <div>
        <p className="text-sm font-semibold mb-2">Crop order ({crops.length} of 6)</p>
        <ol className="space-y-2">
          {crops.map((c, i) => (
            <li key={i} className="flex items-center gap-2">
              <span className="w-7 h-7 shrink-0 rounded-full bg-secondary font-mono text-xs flex items-center justify-center">{i + 1}</span>
              <Input value={c} maxLength={100} placeholder="Crop name" onChange={(e) => setCrops(crops.map((x, j) => (j === i ? e.target.value : x)))} aria-label={`Crop ${i + 1}`} data-testid={`input-crop-${slot}-${i}`} />
              <Button type="button" variant="ghost" size="icon" disabled={crops.length === 1} onClick={() => setCrops(crops.filter((_, j) => j !== i))} aria-label="Remove crop" data-testid={`button-remove-crop-${slot}-${i}`}><X className="h-4 w-4" /></Button>
            </li>
          ))}
        </ol>
        <Button type="button" variant="outline" size="sm" className="mt-3 rounded-full" disabled={crops.length >= 6} onClick={() => setCrops([...crops, ""])} data-testid={`button-add-crop-${slot}`}><Plus className="h-4 w-4" />Add crop</Button>
      </div>
      <Textarea value={notes} maxLength={2000} rows={3} onChange={(e) => setNotes(e.target.value)} placeholder="Why do you like this plan? What do you want to ask a farm helper?" aria-label="Notes" data-testid={`input-notes-${slot}`} />
      <div className="rounded-2xl bg-muted/70 p-4 space-y-2 text-sm">
        {["Water check", "Soil check", "Things to watch"].map((k) => (
          <div key={k} className="flex items-center justify-between gap-3"><span>{k}</span><Tag kind="unassessed">Not checked</Tag></div>
        ))}
        <p className="text-xs text-muted-foreground pt-1">These plans are ideas only. Make a report below to see what the crop guides say. We do not give your plans a score.</p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button onClick={submit} disabled={save.isPending} className="rounded-full" data-testid={`button-save-${slot}`}>
        {save.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Save plan {label}
      </Button>
    </div>
  );
}

export default function Planner() {
  const id = Number(useParams<{ id: string }>().id);
  const farm = useGetFarm(id);
  const strategies = useListStrategies(id);
  const find = (s: StrategyInputSlot) => strategies.data?.find((x) => x.slot === s);

  return (
    <Shell>
      <div className="mx-auto max-w-7xl px-5 py-12">
        {farm.isLoading ? <Skeleton className="h-96 rounded-3xl" /> : farm.isError || !farm.data ? <FarmMissing onRetry={() => farm.refetch()} /> : (
          <>
            <div className="rise pb-8">
              <Link href={`/farms/${id}`} className="font-mono text-xs uppercase tracking-[0.18em] text-accent hover:underline">{farm.data.name} /</Link>
              <h1 className="font-display text-4xl md:text-6xl text-primary mt-2">Your crop plans</h1>
              <p className="text-muted-foreground mt-3 max-w-2xl">See what you grow now. Then write two new plans to compare. Your plans are ideas, not advice. Reports share crop facts. Test model guesses may be wrong.</p>
            </div>
            <FarmContextSummary farm={farm.data} />
            <div className="grid lg:grid-cols-3 gap-5">
              <div className="rounded-3xl bg-primary text-primary-foreground p-6 furrows flex flex-col gap-4">
                <div className="flex items-center justify-between"><span className="font-display text-2xl">Now</span><Tag kind="farmer">You told us</Tag></div>
                <div><p className="text-xs uppercase tracking-wider opacity-70">Current crop</p><p className="font-display text-3xl mt-1" data-testid="text-current-crop">{farm.data.currentCrop}</p></div>
                <div><p className="text-xs uppercase tracking-wider opacity-70">Past crops</p><p className="mt-1 leading-relaxed opacity-90 whitespace-pre-line">{farm.data.cropHistory || "No past crops added."}</p></div>
                <Link href={`/farms/${id}/edit`} className="mt-auto text-sm font-semibold underline-offset-4 hover:underline">Change farm details</Link>
              </div>
              {strategies.isLoading ? [0, 1].map((i) => <Skeleton key={i} className="h-[520px] rounded-3xl" />) : strategies.isError ? (
                <div className="lg:col-span-2 rounded-3xl border border-card-border bg-card p-8">
                  <p className="font-display text-2xl text-primary">Drafts could not be loaded</p>
                  <Button className="mt-4 rounded-full" onClick={() => strategies.refetch()} data-testid="button-retry-strategies">Retry</Button>
                </div>
              ) : (
                <>
                  <DraftEditor key={`a-${find("alternative_a")?.id ?? "new"}`} farmId={id} slot="alternative_a" label="A" existing={find("alternative_a")} />
                  <DraftEditor key={`b-${find("alternative_b")?.id ?? "new"}`} farmId={id} slot="alternative_b" label="B" existing={find("alternative_b")} />
                </>
              )}
            </div>
            <PlanReports farmId={id} defaultCrop={farm.data.currentCrop} defaultPriority={farm.data.goal} />
            <div className="mt-8 grid md:grid-cols-[1.4fr_1fr] gap-5">
              <div className="rounded-3xl border-2 border-dashed border-input p-6 flex gap-4">
                <Bot className="h-8 w-8 text-muted-foreground shrink-0" />
                <div>
                  <div className="flex flex-wrap items-center gap-2"><h2 className="font-display text-2xl text-primary">Test model</h2><Tag kind="unassessed">Not checked enough</Tag></div>
                  <p className="text-sm text-muted-foreground mt-2 leading-relaxed">The test model can show a number for five crops. It has not passed its checks. It may be wrong. Do not use it to choose what to grow. Crop plans and reports use crop guides and FAO maps instead.</p>
                </div>
              </div>
              <div className="rounded-3xl border border-card-border bg-card p-6">
                <h2 className="font-display text-xl text-primary">Before changing your plan</h2>
                <p className="text-sm text-muted-foreground mt-2">Ask a local farm helper. Some facts may be missing or wrong.</p>
                <Link href="/sources" className="mt-3 inline-block text-sm font-semibold text-accent hover:underline" data-testid="link-planner-sources">Where the facts come from</Link>
              </div>
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}
