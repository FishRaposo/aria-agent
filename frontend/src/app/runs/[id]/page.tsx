import ConsoleBoundary from "@/components/ConsoleBoundary";
import RunDetailView from "@/components/RunDetailView";

export default function RunDetailPage({ params }: { params: { id: string } }) {
  return <ConsoleBoundary><RunDetailView runId={params.id} /></ConsoleBoundary>;
}
