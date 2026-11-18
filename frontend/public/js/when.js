/* when.js — showing the schedule's times.
 *
 * THE SERVER SENDS THE CLOCK AS IT READS IN THE HALL: "2027-03-12" and "09:30",
 * already California time. Nothing here builds a Date from an instant or asks
 * the browser what zone it is in, so a laptop set to Texas, or a visitor in
 * another country, reads the same 9:30 as everyone in the building. The only
 * Date made is for a day's name, from its own year, month and day.
 */

/** "09:30" -> "9:30 a.m." */
export function clockText(hhmm) {
  if (!hhmm) return "";
  const [hour, minute] = hhmm.split(":").map(Number);
  const meridiem = hour < 12 ? "a.m." : "p.m.";
  return `${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${meridiem}`;
}

/** "09:30", "10:15" -> "9:30–10:15 a.m."; across noon, both are spelled out. */
export function rangeText(start, end) {
  if (!start) return "";
  if (!end) return clockText(start);
  const first = clockText(start);
  const second = clockText(end);
  const sameHalf = first.slice(-4) === second.slice(-4);
  return `${sameHalf ? first.slice(0, -5) : first}–${second}`;
}

/** "2027-03-12" -> "Friday, March 12" */
export function dayText(date) {
  if (!date) return "";
  const [year, month, day] = date.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric",
  });
}

/** "Friday, March 12 · 9:30–10:15 a.m." for one thing that happens once. */
export function whenText(item) {
  if (!item || !item.date) return "";
  return `${dayText(item.date)} · ${rangeText(item.start, item.end)}`;
}

/** Is the hall's clock inside this entry? Both sides are plain strings that
 *  sort the way time does, so no Date is needed. */
export function isHappening(item, now) {
  if (!item.date || !now || item.date !== now.date) return false;
  if (!item.end) return item.start === now.time;
  return item.start <= now.time && now.time < item.end;
}
