import { getUpcoming } from "@/lib/data";
import UpcomingClient from "@/components/UpcomingClient";

export default async function Home() {
  const { event, fights, models, default_model } = await getUpcoming();

  if (!event) {
    return (
      <div className="py-16 text-center text-neutral-500">
        No upcoming event with locked predictions.
      </div>
    );
  }

  return (
    <div>
      <header className="mb-6">
        <p className="text-sm uppercase tracking-wider text-neutral-500">
          Next event · {event.event_date}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">{event.name}</h1>
        {event.location && (
          <p className="mt-1 text-sm text-neutral-500">{event.location}</p>
        )}
      </header>

      <UpcomingClient fights={fights} models={models} defaultModel={default_model} />
    </div>
  );
}
