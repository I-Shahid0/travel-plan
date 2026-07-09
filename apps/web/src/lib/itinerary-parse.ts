/**
 * Tolerant parser for planner output.
 *
 * The itinerary service may answer with LLM prose (markdown-ish), or with the
 * deterministic template used while the LLM circuit is open. Both shapes speak
 * in "Day N" sections with numbered/bulleted stops; anything unparseable
 * degrades to a single free-text block rather than breaking the page.
 */

export interface ItineraryDay {
  /** 1-based day number as announced by the text. */
  day: number;
  /** Trailing text on the day line, e.g. "Day 2: Old City" → "Old City". */
  heading: string | null;
  stops: ItineraryStop[];
  /** Prose lines inside the day that are not stops. */
  notes: string[];
}

export interface ItineraryStop {
  /** Primary name — text before the first "—" / ":" separator. */
  title: string;
  /** Remainder after the separator (categories, city, flavor text). */
  detail: string | null;
}

export interface ParsedItinerary {
  intro: string[];
  days: ItineraryDay[];
  /** Set when no day structure was found — render as plain text. */
  raw: string | null;
}

const DAY_PATTERN = /^\s*(?:[#*_>\s]*)\bday\s+(\d+)\b[\s:—-]*(.*?)[\s:*_]*$/i;
const STOP_PATTERN = /^\s*(?:\d+[.)]\s+|[-*•]\s+)(.*)$/;

function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/`(.+?)`/g, "$1")
    .trim();
}

function parseStop(line: string): ItineraryStop {
  const clean = stripMarkdown(line);
  const separator = clean.match(/\s+[—–-]\s+|:\s+/);
  if (separator && separator.index !== undefined && separator.index > 0) {
    return {
      title: clean.slice(0, separator.index).trim(),
      detail: clean.slice(separator.index + separator[0].length).trim() || null,
    };
  }
  return { title: clean, detail: null };
}

export function parseItinerary(text: string): ParsedItinerary {
  const lines = text.split(/\r?\n/);
  const intro: string[] = [];
  const days: ItineraryDay[] = [];
  let current: ItineraryDay | null = null;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    const dayMatch = trimmed.match(DAY_PATTERN);
    if (dayMatch?.[1]) {
      current = {
        day: Number(dayMatch[1]),
        heading: stripMarkdown(dayMatch[2] ?? "") || null,
        stops: [],
        notes: [],
      };
      days.push(current);
      continue;
    }

    const stopMatch = trimmed.match(STOP_PATTERN);
    if (current && stopMatch?.[1]) {
      current.stops.push(parseStop(stopMatch[1]));
      continue;
    }

    if (current) {
      current.notes.push(stripMarkdown(trimmed));
    } else {
      intro.push(stripMarkdown(trimmed));
    }
  }

  if (days.length === 0) {
    return { intro: [], days: [], raw: text.trim() };
  }
  return { intro, days, raw: null };
}
