import Link from "next/link";

import type { SearchMode } from "@/lib/api/query/client";

/**
 * The navigator's console: one GET form owning every search parameter, so
 * state lives in the URL and works without client JS.
 */
export function FilterRail({
  q,
  mode,
  city,
  priceMax,
  personalize,
  canPersonalize,
  signedIn,
}: {
  q: string;
  mode: SearchMode;
  city: string;
  priceMax: number | undefined;
  personalize: boolean;
  canPersonalize: boolean;
  signedIn: boolean;
}) {
  return (
    <aside className="lg:sticky lg:top-24 lg:self-start">
      <form action="/search" className="panel-etched space-y-7 p-6">
        <div>
          <label htmlFor="rail-q" className="voice-etch mb-2.5 block">
            Query
          </label>
          <input
            id="rail-q"
            type="text"
            name="q"
            defaultValue={q}
            required
            placeholder="what do you long for…"
            className="input-field"
          />
        </div>

        <fieldset>
          <legend className="voice-etch mb-2.5">Retrieval mode</legend>
          <div className="seg !grid w-full grid-cols-2">
            {(["hybrid", "dense", "sparse", "keyword"] as const).map((value) => (
              <label key={value} className="min-w-0">
                <input type="radio" name="mode" value={value} defaultChecked={mode === value} />
                <span className="block w-full text-center">{value}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div>
          <label htmlFor="rail-city" className="voice-etch mb-2.5 block">
            City
          </label>
          <input
            id="rail-city"
            type="text"
            name="city"
            defaultValue={city}
            placeholder="any city"
            className="input-field"
          />
        </div>

        <fieldset>
          <legend className="voice-etch mb-2.5">Price at most</legend>
          <div className="seg">
            <label>
              <input type="radio" name="price_max" value="" defaultChecked={priceMax === undefined} />
              <span>any</span>
            </label>
            {[1, 2, 3, 4].map((level) => (
              <label key={level}>
                <input
                  type="radio"
                  name="price_max"
                  value={level}
                  defaultChecked={priceMax === level}
                />
                <span>{"$".repeat(level)}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="voice-etch mb-2.5">Personal sky</legend>
          {canPersonalize ? (
            <label className="toggle">
              {/* hidden "off" + checkbox "on": the later value wins server-side,
                  so unchecking genuinely turns personalization off */}
              <input type="hidden" name="personalize" value="off" />
              <input type="checkbox" name="personalize" value="on" defaultChecked={personalize} />
              <span className="track" />
              <span className="text-xs text-dim">
                {personalize ? "Ranking blends your taste" : "Personalization paused"}
              </span>
            </label>
          ) : (
            <p className="text-xs leading-relaxed text-faint">
              {signedIn ? (
                <>
                  <Link href="/profile" className="text-aurora-teal underline-offset-4 hover:underline">
                    Link a traveler profile
                  </Link>{" "}
                  to bend the ranking toward your taste.
                </>
              ) : (
                <>
                  <Link href="/sign-in" className="text-aurora-teal underline-offset-4 hover:underline">
                    Sign in
                  </Link>{" "}
                  to rank the sky by your own taste.
                </>
              )}
            </p>
          )}
        </fieldset>

        <button type="submit" className="btn-brass w-full">
          Recalibrate
        </button>
      </form>
    </aside>
  );
}
