import { type ReactNode, useState } from "react";
import { Link, useLocation } from "wouter";
import { Menu, X } from "lucide-react";
import { useHealthCheck } from "@workspace/api-client-react";
import { Logo } from "@/components/logo";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/farms", label: "My farms" },
  { href: "/select", label: "Analyze a location" },
  { href: "/environment", label: "Explore" },
  { href: "/compare", label: "Compare regions" },
  { href: "/sources", label: "Sources & limits" },
];

export function Shell({ children }: { children: ReactNode }) {
  const [loc] = useLocation();
  const [open, setOpen] = useState(false);
  const health = useHealthCheck();
  const ok = health.data?.status === "ok" || (!!health.data && !health.isError);

  return (
    <div className="grain min-h-[100dvh] flex flex-col bg-background">
      <header className="sticky top-0 z-40 border-b border-border/70 bg-background/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5">
          <Link href="/" data-testid="link-home" aria-label="Field Shift home"><Logo /></Link>
          <nav className="hidden md:flex items-center gap-1">
            {nav.map((n) => {
              const active = loc === n.href || (n.href === "/farms" && loc.startsWith("/farms"));
              return (
                <Link key={n.href} href={n.href} data-testid={`link-nav-${n.href.slice(1)}`}
                  className={cn("relative rounded-full px-4 py-2 text-sm font-medium transition-colors",
                    active ? "bg-primary text-primary-foreground" : "text-foreground/75 hover:text-foreground hover:bg-secondary")}>
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <button className="md:hidden rounded-full p-2 hover:bg-secondary" onClick={() => setOpen(!open)} aria-label="Toggle menu" data-testid="button-menu">
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        {open && (
          <nav className="md:hidden border-t border-border px-5 py-3 flex flex-col gap-1">
            {nav.map((n) => (
              <Link key={n.href} href={n.href} onClick={() => setOpen(false)} className="rounded-xl px-3 py-2.5 text-sm font-medium hover:bg-secondary">{n.label}</Link>
            ))}
          </nav>
        )}
      </header>
      <main className="flex-1">{children}</main>
      <footer className="border-t border-border/70 mt-16">
        <div className="mx-auto max-w-7xl px-5 py-8 flex flex-col md:flex-row gap-4 justify-between text-sm text-muted-foreground">
          <div className="flex items-center gap-3"><Logo /><span>NASA Space Apps 2026 prototype</span></div>
          <div className="flex items-center gap-2" data-testid="status-api">
            <span className={cn("h-2 w-2 rounded-full", health.isLoading ? "bg-chart-4 animate-pulse" : ok ? "bg-chart-3" : "bg-destructive")} />
            {health.isLoading ? "Checking service" : ok ? "Service reachable" : "Service unreachable"}
            <span className="mx-2 opacity-40">|</span>Observations are not advice.
          </div>
        </div>
      </footer>
    </div>
  );
}

export function PageHead({ eyebrow, title, children, actions }: { eyebrow?: string; title: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="rise flex flex-col md:flex-row md:items-end justify-between gap-6 pb-8">
      <div className="max-w-2xl">
        {eyebrow && <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent mb-3">{eyebrow}</p>}
        <h1 className="font-display text-4xl md:text-5xl font-medium text-primary leading-[1.05]">{title}</h1>
        {children && <div className="mt-3 text-muted-foreground leading-relaxed">{children}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Tag({ kind, children }: { kind: "observed" | "farmer" | "draft" | "unassessed"; children: ReactNode }) {
  const styles = {
    observed: "bg-[hsl(200_38%_42%/.12)] text-[hsl(200_45%_30%)] border-[hsl(200_38%_42%/.3)]",
    farmer: "bg-secondary text-secondary-foreground border-[hsl(92_20%_70%)]",
    draft: "bg-[hsl(38_70%_50%/.14)] text-[hsl(30_60%_30%)] border-[hsl(38_70%_50%/.35)]",
    unassessed: "bg-muted text-muted-foreground border-dashed border-input",
  }[kind];
  return <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10.5px] uppercase tracking-wider", styles)}>{children}</span>;
}
