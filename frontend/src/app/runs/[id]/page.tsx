import ConsoleBoundary from "@/components/ConsoleBoundary";
import RunDetailView from "@/components/RunDetailView";
import { DENIED_RUN } from "@/lib/demo-scenarios";
import { MOCK_RUNS } from "@/lib/mockData";

// A static export needs every run id at build time; the demo ships a fixed set.
// dynamicParams stays at its default: route segment config must be a literal, an export has
// no server to route unknown ids anyway (Pages answers with 404.html), and a connected build
// must still be able to serve a real run id.

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
