import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("h-9 w-9", className)} aria-hidden="true">
      <rect x="1" y="1" width="38" height="38" rx="12" fill="hsl(152 40% 20%)" />
      <path d="M8 29 Q20 22 32 29" stroke="hsl(92 24% 66%)" strokeWidth="2.2" fill="none" strokeLinecap="round" />
      <path d="M8 24 Q20 17 32 24" stroke="hsl(92 24% 66%)" strokeWidth="2.2" fill="none" strokeLinecap="round" opacity=".7" />
      <path d="M8 19 Q20 12 32 19" stroke="hsl(20 58% 56%)" strokeWidth="2.2" fill="none" strokeLinecap="round" />
      <circle cx="28" cy="10.5" r="3" fill="hsl(42 60% 86%)" />
    </svg>
  );
}

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark />
      <span className={cn("font-display text-xl font-semibold", light ? "text-[hsl(44_45%_93%)]" : "text-primary")}>
        Field<span className="italic font-medium text-accent">Shift</span>
      </span>
    </span>
  );
}
