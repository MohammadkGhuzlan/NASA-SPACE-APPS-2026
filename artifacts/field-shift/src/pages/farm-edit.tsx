import { Link, useLocation, useParams } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { getGetFarmQueryKey, getGetEnvironmentQueryKey, getListFarmsQueryKey, useGetFarm, useUpdateFarm } from "@workspace/api-client-react";
import { PageHead, Shell } from "@/components/shell";
import { FarmForm } from "@/components/farm-form";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { FarmMissing } from "@/pages/farm-overview";

export default function FarmEdit() {
  const id = Number(useParams<{ id: string }>().id);
  const farm = useGetFarm(id);
  const update = useUpdateFarm();
  const qc = useQueryClient();
  const [, navigate] = useLocation();
  const { toast } = useToast();

  return (
    <Shell>
      <div className="mx-auto max-w-3xl px-5 py-12">
        {farm.isLoading ? (
          <div className="space-y-4"><Skeleton className="h-16 w-2/3 rounded-2xl" /><Skeleton className="h-64 rounded-3xl" /><Skeleton className="h-64 rounded-3xl" /></div>
        ) : farm.isError || !farm.data ? (
          <FarmMissing onRetry={() => farm.refetch()} />
        ) : (
          <>
            <PageHead eyebrow="Edit profile" title={farm.data.name} actions={<Link href={`/farms/${id}`} className="rounded-full border border-input px-5 py-2 text-sm font-semibold hover:bg-secondary" data-testid="link-cancel">Cancel</Link>} />
            <FarmForm
              initial={farm.data}
              submitLabel="Save changes"
              pending={update.isPending}
              onSubmit={(data) => update.mutate({ id, data }, {
                onSuccess: () => {
                  qc.invalidateQueries({ queryKey: getGetFarmQueryKey(id) });
                  qc.invalidateQueries({ queryKey: getListFarmsQueryKey() });
                  qc.invalidateQueries({ queryKey: getGetEnvironmentQueryKey(id) });
                  toast({ title: "Profile updated" });
                  navigate(`/farms/${id}`);
                },
                onError: () => toast({ title: "Could not save changes", variant: "destructive" }),
              })}
            />
          </>
        )}
      </div>
    </Shell>
  );
}
