import Link from "next/link";
import { notFound } from "next/navigation";
import { getSnapshot, listSnapshotIds } from "@/lib/data";
import FightRow from "@/components/FightRow";

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

  const graded = snap.fights.filter((f) => f.prediction && f.winner_id != null);
  const correct = graded.filter(
    (f) => f.prediction!.predicted_winner_id === f.winner_id,
  ).length;

  return (
    <div>
      <Link
        href="/performance/"
        className="text-xs text-neutral-500 hover:underline"
      >
        ← Performance
      </Link>
      <header className="mb-8 mt-2">
        <p className="text-sm uppercase tracking-wider text-neutral-500">
          {snap.event.event_date}
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">
          {snap.event.name}
        </h1>
        {snap.event.location && (
          <p className="mt-1 text-sm text-neutral-500">{snap.event.location}</p>
        )}
        {graded.length > 0 && (
          <p className="mt-3 text-sm text-neutral-600 dark:text-neutral-400">
            <span className="font-medium">{correct}/{graded.length}</span> graded picks correct
            <span className="ml-1 text-neutral-500">
              ({Math.round((correct / graded.length) * 100)}%)
            </span>
          </p>
        )}
      </header>

      <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
        {snap.fights.map((f) => (
          <FightRow key={f.fight_id} fight={f} />
        ))}
      </ul>
    </div>
  );
}
