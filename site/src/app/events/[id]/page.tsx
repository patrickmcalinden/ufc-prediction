import Link from "next/link";
import { notFound } from "next/navigation";
import { getSnapshot, listSnapshotIds } from "@/lib/data";
import EventClient from "@/components/EventClient";

export async function generateStaticParams() {
  const ids = await listSnapshotIds();
  return ids.map((id) => ({ id: String(id) }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  try {
    const snap = await getSnapshot(Number(id));
    return { title: `${snap.event.name} · UFC Predictor` };
  } catch {
    return { title: "Event · UFC Predictor" };
  }
}

export default async function EventPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let snap;
  try {
    snap = await getSnapshot(Number(id));
  } catch {
    notFound();
  }
  if (!snap) notFound();

  return (
    <div>
      <Link href="/performance/" className="text-xs text-neutral-500 hover:underline">
        ← Performance
      </Link>
      <header className="mb-6 mt-2">
        <p className="text-sm uppercase tracking-wider text-neutral-500">
          {snap.event.event_date}
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{snap.event.name}</h1>
        {snap.event.location && (
          <p className="mt-1 text-sm text-neutral-500">{snap.event.location}</p>
        )}
      </header>

      <EventClient
        fights={snap.fights}
        models={snap.models}
        defaultModel={snap.default_model}
      />
    </div>
  );
}
