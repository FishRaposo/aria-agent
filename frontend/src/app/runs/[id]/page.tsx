import RunDetailView from "@/components/RunDetailView";

export default function RunDetailPage({ params }: { params: { id: string } }) {
  return <RunDetailView runId={params.id} />;
}
