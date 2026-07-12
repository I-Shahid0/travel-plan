"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { PaletteHit } from "@/app/api/palette/route";

/** Custom event so server components (nav, empty states) can open the palette. */
export const OPEN_PALETTE_EVENT = "meridian:open-palette";

const RECENT_KEY = "meridian:recent-queries";
const MAX_RECENT = 5;
const DEBOUNCE_MS = 180;

interface NavAction {
  label: string;
  hint: string;
  href: string;
}

const NAV_ACTIONS: NavAction[] = [
  { label: "Search the atlas", hint: "hybrid semantic search", href: "/search" },
  { label: "Browse the atlas", hint: "facets, filters, the whole sky", href: "/browse" },
  { label: "Plan a journey", hint: "LLM itineraries with budget verdicts", href: "/plan" },
  { label: "For you", hint: "your recommendation sky", href: "/foryou" },
  { label: "History", hint: "your recorded signals", href: "/history" },
  { label: "Observatory", hint: "live service health", href: "/observatory" },
];

type Row =
  | { kind: "search"; query: string }
  | { kind: "listing"; hit: PaletteHit }
  | { kind: "nav"; action: NavAction }
  | { kind: "recent"; query: string };

function readRecent(): string[] {
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((v) => typeof v === "string") : [];
  } catch {
    return [];
  }
}

function pushRecent(query: string) {
  try {
    const next = [query, ...readRecent().filter((q) => q !== query)].slice(0, MAX_RECENT);
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    // storage unavailable (private mode) — recents are a nicety, not a need
  }
}

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<PaletteHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState(0);
  const [recent, setRecent] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // ---- open/close wiring ----
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((v) => !v);
      } else if (event.key === "Escape") {
        setOpen(false);
      }
    };
    const onOpenEvent = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_PALETTE_EVENT, onOpenEvent);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_PALETTE_EVENT, onOpenEvent);
    };
  }, []);

  useEffect(() => {
    if (open) {
      setRecent(readRecent());
      // let the dialog mount before grabbing focus
      requestAnimationFrame(() => inputRef.current?.focus());
      document.body.style.overflow = "hidden";
    } else {
      setQuery("");
      setHits([]);
      setSelected(0);
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  // ---- debounced live search ----
  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    if (q.length < 2) {
      setHits([]);
      setSearching(false);
      abortRef.current?.abort();
      return;
    }
    setSearching(true);
    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const res = await fetch(`/api/palette?q=${encodeURIComponent(q)}`, {
          signal: controller.signal,
        });
        const data = (await res.json()) as { results: PaletteHit[] };
        setHits(data.results);
        setSelected(0);
      } catch {
        // aborted or offline — keep whatever is showing
      } finally {
        if (abortRef.current === controller) setSearching(false);
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query, open]);

  // ---- rows in display order ----
  const rows = useMemo<Row[]>(() => {
    const q = query.trim();
    if (q.length >= 2) {
      const navMatches = NAV_ACTIONS.filter((a) =>
        a.label.toLowerCase().includes(q.toLowerCase()),
      );
      return [
        { kind: "search", query: q },
        ...hits.map((hit) => ({ kind: "listing", hit }) as Row),
        ...navMatches.map((action) => ({ kind: "nav", action }) as Row),
      ];
    }
    return [
      ...recent.map((r) => ({ kind: "recent", query: r }) as Row),
      ...NAV_ACTIONS.map((action) => ({ kind: "nav", action }) as Row),
    ];
  }, [query, hits, recent]);

  const go = useCallback(
    (row: Row) => {
      setOpen(false);
      switch (row.kind) {
        case "search":
        case "recent":
          pushRecent(row.query);
          router.push(`/search?q=${encodeURIComponent(row.query)}`);
          break;
        case "listing":
          if (query.trim()) pushRecent(query.trim());
          router.push(`/listing/${row.hit.id}`);
          break;
        case "nav":
          router.push(row.action.href);
          break;
      }
    },
    [router, query],
  );

  const onInputKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelected((s) => Math.min(s + 1, rows.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelected((s) => Math.max(s - 1, 0));
    } else if (event.key === "Enter" && rows[selected]) {
      event.preventDefault();
      go(rows[selected]);
    }
  };

  // keep the selected row in view
  useEffect(() => {
    listRef.current
      ?.querySelector(`[data-index="${selected}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  if (!open) return null;

  const q = query.trim();

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center px-4 pt-[14vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      {/* backdrop */}
      <button
        aria-label="Close palette"
        className="absolute inset-0 cursor-default bg-ink-950/70 backdrop-blur-sm"
        onClick={() => setOpen(false)}
      />

      <div className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-(--line-bright) bg-ink-900/95 shadow-[0_0_0_1px_rgba(139,124,255,0.08),0_24px_80px_-16px_rgba(4,6,14,0.9),0_0_64px_-24px_rgba(139,124,255,0.5)] backdrop-blur-xl">
        {/* aurora hairline across the top */}
        <div
          aria-hidden="true"
          className="h-px w-full [background:var(--aurora-gradient)] opacity-70"
        />

        {/* input row */}
        <div className="flex items-center gap-3 border-b border-(--line) px-5 py-4">
          <svg
            viewBox="0 0 20 20"
            className={`h-5 w-5 shrink-0 transition-colors ${searching ? "animate-pulse text-aurora-violet" : "text-faint"}`}
            aria-hidden="true"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <circle cx="9" cy="9" r="6.5" />
            <line x1="13.8" y1="13.8" x2="18" y2="18" strokeLinecap="round" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKeyDown}
            placeholder="Search places, or jump anywhere…"
            aria-label="Search places or navigate"
            className="w-full bg-transparent font-sans text-base text-starlight outline-none placeholder:text-faint"
          />
          <kbd className="voice-etch shrink-0 rounded-md border border-(--line) px-1.5 py-0.5 !text-[0.625rem] text-faint">
            esc
          </kbd>
        </div>

        {/* rows */}
        <ul ref={listRef} className="max-h-[46vh] list-none overflow-y-auto py-2" role="listbox">
          {q.length >= 2 && rows.length === 1 && !searching && (
            <li className="px-5 py-3 text-sm text-dim">
              Nothing rose above the horizon — press <span className="text-starlight">↵</span> to
              search the full atlas anyway.
            </li>
          )}
          {q.length < 2 && recent.length === 0 && (
            <li className="px-5 pt-3 pb-1">
              <p className="voice-etch !text-[0.625rem] text-faint">
                Type to search 150,000+ places · or jump to
              </p>
            </li>
          )}

          {rows.map((row, index) => {
            const isSelected = index === selected;
            const key =
              row.kind === "listing"
                ? `l-${row.hit.id}`
                : row.kind === "nav"
                  ? `n-${row.action.href}`
                  : `${row.kind}-${row.query}`;
            return (
              <li key={key} data-index={index} role="option" aria-selected={isSelected}>
                <button
                  type="button"
                  className={`flex w-full items-baseline justify-between gap-3 px-5 py-2.5 text-left transition-colors ${
                    isSelected ? "bg-white/[0.06]" : "hover:bg-white/[0.03]"
                  }`}
                  onClick={() => go(row)}
                  onMouseMove={() => setSelected(index)}
                >
                  {row.kind === "search" && (
                    <>
                      <span className="min-w-0 truncate text-sm text-starlight">
                        Chart <em className="voice-wonk text-gradient-aurora">“{row.query}”</em>
                      </span>
                      <span className="voice-etch shrink-0 !text-[0.625rem] text-faint">
                        full search {isSelected && "↵"}
                      </span>
                    </>
                  )}
                  {row.kind === "listing" && (
                    <>
                      <span className="min-w-0 truncate text-sm text-starlight">
                        {row.hit.title}
                      </span>
                      <span className="shrink-0 font-mono text-[0.6875rem] tracking-tight text-faint">
                        {[
                          row.hit.category,
                          row.hit.city,
                          row.hit.stars != null ? `★ ${row.hit.stars.toFixed(1)}` : null,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </>
                  )}
                  {row.kind === "nav" && (
                    <>
                      <span className="text-sm text-brass">{row.action.label}</span>
                      <span className="voice-etch shrink-0 !text-[0.625rem] text-faint">
                        {row.action.hint}
                      </span>
                    </>
                  )}
                  {row.kind === "recent" && (
                    <>
                      <span className="min-w-0 truncate text-sm text-dim">
                        <span aria-hidden="true" className="mr-2 text-faint">
                          ↩
                        </span>
                        {row.query}
                      </span>
                      <span className="voice-etch shrink-0 !text-[0.625rem] text-faint">
                        recent
                      </span>
                    </>
                  )}
                </button>
              </li>
            );
          })}
        </ul>

        {/* footer hints */}
        <div className="flex items-center justify-between border-t border-(--line) px-5 py-2.5">
          <span className="voice-etch !text-[0.625rem] text-faint">
            ↑↓ navigate · ↵ open · esc close
          </span>
          <span className="voice-etch !text-[0.625rem] text-aurora-teal">
            live hybrid retrieval
          </span>
        </div>
      </div>
    </div>
  );
}

/** Nav button that opens the palette — usable from server components. */
export function PaletteTrigger() {
  const [isMac, setIsMac] = useState(true);
  useEffect(() => {
    setIsMac(/Mac|iPhone|iPad/i.test(navigator.userAgent));
  }, []);

  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new CustomEvent(OPEN_PALETTE_EVENT))}
      aria-label="Open command palette"
      className="group/palette flex items-center gap-2 rounded-full border border-(--line) px-2.5 py-2 transition-all hover:border-aurora-violet/50 hover:shadow-[0_0_24px_-8px_rgba(139,124,255,0.5)] sm:px-3"
    >
      <svg
        viewBox="0 0 20 20"
        className="h-3.5 w-3.5 text-faint transition-colors group-hover/palette:text-aurora-violet"
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      >
        <circle cx="9" cy="9" r="6.5" />
        <line x1="13.8" y1="13.8" x2="18" y2="18" strokeLinecap="round" />
      </svg>
      <kbd className="voice-etch hidden !text-[0.625rem] text-faint transition-colors group-hover/palette:text-starlight sm:inline">
        {isMac ? "⌘" : "Ctrl"}&thinsp;K
      </kbd>
    </button>
  );
}
