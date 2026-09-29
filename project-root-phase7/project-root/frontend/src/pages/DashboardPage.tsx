import { useQuery } from "@tanstack/react-query";
import { fetchCaseCount, fetchOpenCaseCount } from "@/api/casesApi";
import { fetchPersonCount } from "@/api/personsApi";
import { useAuth } from "@/hooks/useAuth";

/**
 * Deliberately minimal: three real counts from the Phase 4 API, no
 * charts or geographic breakdown yet — the full stats dashboard
 * (charts, recent activity, geographic distribution) is Phase 16. This
 * page exists so Phase 5 delivers a working authenticated landing page
 * that shows real data rather than a static placeholder.
 */
export function DashboardPage() {
  const { user } = useAuth();

  const personCount = useQuery({ queryKey: ["stats", "person-count"], queryFn: fetchPersonCount });
  const caseCount = useQuery({ queryKey: ["stats", "case-count"], queryFn: fetchCaseCount });
  const openCaseCount = useQuery({ queryKey: ["stats", "open-case-count"], queryFn: fetchOpenCaseCount });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">Dashboard</h1>
        <p className="text-sm text-slate-500">Welcome back, {user?.email}.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Total Persons" query={personCount} />
        <StatCard label="Total Cases" query={caseCount} />
        <StatCard label="Open Cases" query={openCaseCount} />
      </div>
    </div>
  );
}

function StatCard({
  label,
  query,
}: {
  label: string;
  query: { data?: number; isLoading: boolean; isError: boolean };
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-2xl font-semibold text-slate-800 mt-1">
        {query.isLoading ? "…" : query.isError ? "—" : query.data}
      </p>
    </div>
  );
}
