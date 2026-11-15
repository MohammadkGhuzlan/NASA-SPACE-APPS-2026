import { Link } from "wouter";
import { ArrowRight, Satellite, Sprout, ShieldCheck, NotebookPen } from "lucide-react";
import { useListCaseStudies } from "@workspace/api-client-react";
import { Shell, Tag } from "@/components/shell";
import { Skeleton } from "@/components/ui/skeleton";
import { asset } from "@/lib/field";

export default function Landing() {
  const cases = useListCaseStudies();
  return (
    <Shell>
      <section className="relative overflow-hidden">
        <div className="mx-auto max-w-7xl px-5 pt-14 pb-20 grid lg:grid-cols-[1.1fr_1fr] gap-12 items-center">
          <div>
            <p className="rise font-mono text-xs uppercase tracking-[0.2em] text-accent">NASA Space Apps 2026 · Farm planning test</p>
            <h1 className="rise font-display text-5xl md:text-7xl font-medium leading-[0.98] text-primary mt-5" style={{ animationDelay: ".08s" }}>
              Learn about your farm before you plan.
            </h1>
            <p className="rise mt-6 text-lg text-foreground/75 max-w-xl leading-relaxed" style={{ animationDelay: ".16s" }}>
              Choose a place on the map. See rain and heat data from NASA. Then try a plan for what to grow. This test app tells you when information is missing.
            </p>
            <div className="rise mt-9 flex flex-wrap gap-3" style={{ animationDelay: ".24s" }}>
              <Link href="/select" data-testid="button-analyze" className="group inline-flex items-center gap-2 rounded-full bg-primary px-7 py-4 text-primary-foreground font-semibold shadow-lg shadow-primary/20 transition-transform active:scale-[.97]">
                Choose a place <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link href="/farms" data-testid="link-saved-farms" className="inline-flex items-center rounded-full border border-primary/25 px-7 py-4 font-semibold text-primary hover:bg-secondary transition-colors">
                Saved farms
              </Link>
            </div>
          </div>
          <div className="rise relative" style={{ animationDelay: ".2s" }}>
            <div className="absolute -inset-4 rounded-[2.5rem] bg-secondary rotate-2" />
            <img src={asset("hero-fields.jpg")} alt="Illustrated aerial view of patchwork crop fields" className="relative rounded-[2rem] aspect-[4/5] md:aspect-[5/4] lg:aspect-[4/5] object-cover w-full shadow-2xl shadow-primary/20" />
            <div className="absolute bottom-5 left-5 right-5 rounded-2xl bg-card/90 backdrop-blur p-4 flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-[11px] text-muted-foreground uppercase tracking-wider">Check each number</p>
                <p className="font-display text-lg text-primary">Who made it, and when?</p>
              </div>
              <Satellite className="h-7 w-7 text-accent" />
            </div>
          </div>
        </div>
      </section>

      <section className="bg-primary text-primary-foreground furrows">
        <div className="mx-auto max-w-7xl px-5 py-20 grid md:grid-cols-[1fr_1.4fr] gap-12">
          <h2 className="font-display text-4xl md:text-5xl leading-tight">Three kinds of information.</h2>
          <div className="space-y-8">
            {[
              { icon: Satellite, t: "From NASA", d: "NASA data shows rain and temperature. It also gives computer estimates of wet soil. These are not farm measurements. If data is missing, we say so." },
              { icon: NotebookPen, t: "From you", d: "You can add soil, water and crop history. Empty boxes stay empty. We do not fill them in." },
              { icon: Sprout, t: "Your crop plans", d: "Write two other crop plans. You can also make a report using crop guides. The app does not rank your plans." },
            ].map((x, i) => (
              <div key={x.t} className="flex gap-5 border-t border-primary-foreground/15 pt-6">
                <span className="font-mono text-sm text-[hsl(92_24%_66%)]">0{i + 1}</span>
                <div>
                  <h3 className="flex items-center gap-2 font-display text-2xl"><x.icon className="h-5 w-5 text-[hsl(92_24%_66%)]" />{x.t}</h3>
                  <p className="mt-2 text-primary-foreground/75 leading-relaxed">{x.d}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-20 grid lg:grid-cols-2 gap-12">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent">Why change crops?</p>
          <h2 className="font-display text-4xl text-primary mt-3">A crop plan helps you choose what to grow.</h2>
          <p className="mt-5 text-foreground/75 leading-relaxed">Growing different crops can affect bugs, soil and water. What works depends on the farm. First, look at the rain and temperature data for your place.</p>
        </div>
        <div className="rounded-3xl border border-card-border bg-card p-8">
          <ShieldCheck className="h-8 w-8 text-accent" />
          <h3 className="font-display text-2xl text-primary mt-4">What this test app cannot do</h3>
          <ul className="mt-4 space-y-3 text-foreground/80">
            <li>It cannot tell you which crop is best for your farm or how much you will harvest.</li>
            <li>Its crop model has not passed tests. Do not use its guesses to choose what to grow.</li>
            <li>It cannot replace a farmer, soil test or local farm expert.</li>
          </ul>
          <Link href="/sources" className="mt-6 inline-flex items-center gap-1 font-semibold text-primary hover:text-accent transition-colors" data-testid="link-sources">See where the facts come from <ArrowRight className="h-4 w-4" /></Link>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 pb-10">
        <div className="flex items-end justify-between gap-4 mb-6">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent">Places to try</p>
            <h2 className="font-display text-4xl text-primary mt-2">Try these four places</h2>
          </div>
          <Tag kind="unassessed">Examples, not real farms</Tag>
        </div>
        {cases.isLoading ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-44 rounded-3xl" />)}</div>
        ) : cases.isError ? (
          <p className="text-muted-foreground">Case studies could not be loaded. You can still pick any location on the map.</p>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {(cases.data ?? []).map((c, i) => (
              <Link key={c.name} href={`/select?case=${encodeURIComponent(c.name)}`} data-testid={`card-case-${i}`} className="lift rounded-3xl border border-card-border bg-card p-6 flex flex-col">
                <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">{c.country}</span>
                <span className="font-display text-2xl text-primary mt-1">{c.name}</span>
                <span className="text-sm text-foreground/70 mt-3 flex-1">Example place. Not a real farm.</span>
                <span className="mt-4 font-mono text-xs text-accent">{c.latitude.toFixed(2)}, {c.longitude.toFixed(2)}</span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </Shell>
  );
}
