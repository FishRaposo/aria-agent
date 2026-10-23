import ConsoleBoundary from "@/components/ConsoleBoundary";
import RunDetailView from "@/components/RunDetailView";

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ConsoleBoundary><RunDetailView runId={id} /></ConsoleBoundary>;
}
