import { Link } from "wouter";
import { ArrowUpRight, Plus, Sprout } from "lucide-react";
import { format } from "date-fns";
import { useListFarms } from "@workspace/api-client-react";
import { PageHead, Shell, Tag } from "@/components/shell";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { fmtCoord, goalLabel, irrigationLabel } from "@/lib/field";

export default function Farms() {
  const farms = useListFarms();
  const add = (
    <Link href="/select" data-testid="button-new-farm" className="inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground active:scale-[.97] transition-transform">
      <Plus className="h-4 w-4" /> New farm
    </Link>
  );
  return (
    <Shell>
      <div className="mx-auto max-w-7xl px-5 py-12">
        <PageHead eyebrow="This browser session" title="Saved farms" actions={add}>
          Farms are stored for this anonymous session only. Clearing cookies removes them.
        </PageHead>
        {farms.isLoading ? (
          <div className="grid md:grid-cols-2 gap-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-52 rounded-3xl" />)}</div>
        ) : farms.isError ? (
          <div className="rounded-3xl border border-destructive/30 bg-card p-8">
            <p className="font-display text-2xl text-primary">Farms could not be loaded.</p>
            <Button className="mt-4 rounded-full" onClick={() => farms.refetch()} data-testid="button-retry">Try again</Button>
          </div>
        ) : !farms.data?.length ? (
          <div className="rounded-[2rem] border-2 border-dashed border-input bg-card/60 p-12 text-center furrows">
            <Sprout className="mx-auto h-10 w-10 text-accent" />
            <p className="font-display text-3xl text-primary mt-4">No fields yet.</p>
            <p className="text-muted-foreground mt-2 max-w-md mx-auto">Start by placing a pin on the map where your crops grow. Everything else follows from the location.</p>
            <div className="mt-6 flex justify-center">{add}</div>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 gap-5">
            {farms.data.map((f, i) => (
              <Link key={f.id} href={`/farms/${f.id}`} data-testid={`card-farm-${f.id}`} className="lift rise group rounded-3xl border border-card-border bg-card p-7 flex flex-col gap-4" style={{ animationDelay: `${i * 0.05}s` }}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-display text-3xl text-primary">{f.name}</h2>
                    <p className="text-sm text-muted-foreground mt-1">{f.locationName}</p>
                  </div>
                  <ArrowUpRight className="h-5 w-5 text-accent transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                </div>
                <div className="flex flex-wrap gap-2">
                  <Tag kind="farmer">{f.currentCrop}</Tag>
                  <Tag kind="farmer">{irrigationLabel[f.irrigation]}</Tag>
                  <Tag kind="farmer">{goalLabel[f.goal]}</Tag>
                </div>
                <div className="mt-auto flex justify-between font-mono text-xs text-muted-foreground border-t border-border pt-3">
                  <span>{fmtCoord(f.latitude, f.longitude)}</span>
                  <span>Updated {format(new Date(f.updatedAt), "d MMM yyyy")}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </Shell>
  );
}
