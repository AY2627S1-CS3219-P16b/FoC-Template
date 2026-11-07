/**
 * Acceptance deadlines offered when creating a request.
 *
 * Order Service enforces the same rules: a deadline at most an hour away, and,
 * when the store closes, at least CLOSING_BUFFER_MINUTES before closing so a
 * courier who accepts at the last moment can still reach the store.
 */

export const DEADLINE_OPTIONS = [
  { label: "Within 30 mins", minutes: 30 },
  { label: "Within 45 mins", minutes: 45 },
  { label: "Within 1 hour", minutes: 60 },
];

export const DEFAULT_DEADLINE = "Within 45 mins";
export const CLOSING_BUFFER_MINUTES = 10;

const MINUTE = 60000;

export function deadlineMinutes(label) {
  return DEADLINE_OPTIONS.find((option) => option.label === label)?.minutes ?? 45;
}

/** Campus clock time, e.g. "21:00", for a Supplier Service timestamp. */
export function campusTime(value) {
  return new Date(value).toLocaleTimeString("en-GB", {
    hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Singapore",
  });
}

/**
 * Each option with whether it still fits before the store closes.
 * A supplier without closes_at never closes, so every option fits.
 */
export function deadlineChoices(closesAt, now = new Date()) {
  const latest = closesAt ? new Date(closesAt).getTime() - CLOSING_BUFFER_MINUTES * MINUTE : null;
  return DEADLINE_OPTIONS.map((option) => ({
    ...option,
    available: latest === null || now.getTime() + option.minutes * MINUTE <= latest,
  }));
}

/** The chosen option if it still fits, otherwise the longest one that does. */
export function effectiveDeadline(choices, chosen) {
  const available = choices.filter((choice) => choice.available);
  return available.find((choice) => choice.label === chosen) || available[available.length - 1] || null;
}

/** What the form says about closing time, or "" when the store never closes. */
export function closingNotice(closesAt, choices) {
  if (!closesAt) return "";
  const closes = campusTime(closesAt);
  if (!choices.some((choice) => choice.available)) {
    return `This store closes at ${closes}, too soon for a courier to get there. Try again when it next opens.`;
  }
  const latest = campusTime(new Date(closesAt).getTime() - CLOSING_BUFFER_MINUTES * MINUTE);
  return `This store closes at ${closes}, so a courier must accept by ${latest}.`;
}
