/**
 * Group an array of fight/prediction objects by event and sort them for display.
 *
 * - Fights within each event are sorted by card_order (main event first).
 * - Events are split into upcoming (ascending) and past (descending) so the
 *   next event is always at the top.
 *
 * @param {Array} items – rows from the predictions or results endpoint.
 *   Each item must have at least: event_name, fight_date, card_order, fight_id.
 * @param {{ chronological?: boolean }} opts
 *   chronological: if true, sort ALL events reverse-chronologically (no
 *   upcoming/past split). Useful for the Results page where every event is
 *   already in the past.
 * @returns {Array<{ eventName: string, date: Date, fights: Array }>}
 */
export function groupAndSortByEvent(items, { chronological = false } = {}) {
  if (!items || items.length === 0) return [];

  const parseDate = (dateStr) => {
    if (!dateStr) return new Date();
    // Always extract YYYY-MM-DD to construct local date and avoid UTC offsets
    const datePart = dateStr.split('T')[0];
    const [year, month, day] = datePart.split('-');
    return new Date(year, month - 1, day);
  };

  const groups = items.reduce((acc, current) => {
    const key = current.event_name;
    const currentEventDate = parseDate(current.fight_date);
    if (!acc[key]) {
      acc[key] = {
        eventName: key,
        date: currentEventDate,
        fights: [],
      };
    }
    acc[key].fights.push(current);
    if (currentEventDate > acc[key].date) acc[key].date = currentEventDate;
    return acc;
  }, {});

  // Sort fights within each event by card_order (main event first).
  Object.values(groups).forEach((event) => {
    event.fights.sort((a, b) => {
      const ao = a.card_order ?? Number.MAX_SAFE_INTEGER;
      const bo = b.card_order ?? Number.MAX_SAFE_INTEGER;
      if (ao !== bo) return ao - bo;
      return (a.fight_id ?? 0) - (b.fight_id ?? 0);
    });
  });

  if (chronological) {
    return Object.values(groups).sort((a, b) => b.date - a.date);
  }

  // Split upcoming vs past so the next event is always on top.
  const now = new Date();
  const upcoming = [];
  const past = [];
  Object.values(groups).forEach((event) => {
    // Cutoff time is 1:30 AM local time the day AFTER the event
    const cutoffTime = new Date(event.date);
    cutoffTime.setDate(cutoffTime.getDate() + 1);
    cutoffTime.setHours(1, 30, 0, 0);

    if (now < cutoffTime) upcoming.push(event);
    else past.push(event);
  });
  upcoming.sort((a, b) => a.date - b.date);
  past.sort((a, b) => b.date - a.date);
  return [...upcoming, ...past];
}
