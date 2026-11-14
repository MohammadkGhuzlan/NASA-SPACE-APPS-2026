import { useState } from "react";
import { Link, useLocation } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { getListFarmsQueryKey, useCreateFarm } from "@workspace/api-client-react";
import { PageHead, Shell } from "@/components/shell";
import { FarmForm } from "@/components/farm-form";
import { useToast } from "@/hooks/use-toast";
import { clearPending, readPending } from "@/lib/field";

export default function FarmNew() {
  const [pending] = useState(readPending);
  const [, navigate] = useLocation();
  const qc = useQueryClient();
  const { toast } = useToast();
  const create = useCreateFarm();

  if (!pending) {
    return (
      <Shell>
        <div className="mx-auto max-w-xl px-5 py-24 text-center">
          <h1 className="font-display text-4xl text-primary">Choose a location first</h1>
          <p className="text-muted-foreground mt-3">The questionnaire needs a confirmed point on the map.</p>
          <Link href="/select" className="mt-6 inline-flex rounded-full bg-primary px-6 py-3 font-semibold text-primary-foreground" data-testid="link-select">Open the map</Link>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="mx-auto max-w-3xl px-5 py-12">
        <PageHead eyebrow="Step 2 of 2" title="Tell us about this field">Only what you know. Every answer is labelled as farmer reported.</PageHead>
        <FarmForm
          initial={pending}
          submitLabel="Save farm"
          pending={create.isPending}
          locationAction={<Link href="/select" className="text-sm font-semibold text-accent hover:underline" data-testid="link-change-location">Change</Link>}
          onSubmit={(data) => create.mutate({ data }, {
            onSuccess: (farm) => {
              clearPending();
              qc.invalidateQueries({ queryKey: getListFarmsQueryKey() });
              toast({ title: "Farm saved", description: farm.name });
              navigate(`/farms/${farm.id}`);
            },
            onError: () => toast({ title: "Could not save farm", description: "Check the fields and try again.", variant: "destructive" }),
          })}
        />
      </div>
    </Shell>
  );
}
