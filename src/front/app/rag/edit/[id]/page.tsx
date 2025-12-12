import { RagEditPage } from '@/components/rag/RagEditPage';

interface RagEditRouteProps {
  params: Promise<{ id: string }>;
}

export default async function RagEditRoute({ params }: RagEditRouteProps) {
  const { id } = await params;
  return <RagEditPage configId={id} />;
}
