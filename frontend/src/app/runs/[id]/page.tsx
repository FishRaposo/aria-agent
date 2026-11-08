import ConsoleBoundary from "@/components/ConsoleBoundary";
import RunDetailView from "@/components/RunDetailView";
import { DENIED_RUN } from "@/lib/demo-scenarios";
import { MOCK_RUNS } from "@/lib/mockData";

// A static export needs every run id at build time; the demo ships a fixed set.
// dynamicParams=false turns an unknown id into a 404 instead of a build surprise.
export const dynamicParams = false;

export function generateStaticParams() {
  const ids = new Set(MOCK_RUNS.map((run) => run.id));
  ids.add(DENIED_RUN);
  return [...ids].map((id) => ({ id }));
}

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ConsoleBoundary><RunDetailView runId={id} /></ConsoleBoundary>;
}
