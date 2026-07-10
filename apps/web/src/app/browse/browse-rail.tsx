import type { BrowseState } from "@/lib/browse";

/**
 * The surveyor's console: one GET form owning every browse parameter, so
 * state lives in the URL and works without client JS (facet chips are plain
 * links that layer on top of this form's values).
 */
export function BrowseRail({ state }: { state: BrowseState }) {
  return (
    <aside className="lg:sticky lg:top-24 lg:self-start">
      <form action="/browse" className="panel-etched space-y-7 p-6">
        <div>
          <label htmlFor="browse-city" className="voice-etch mb-2.5 block">
            City
          </label>
          <input
            id="browse-city"
            type="text"
            name="city"
            defaultValue={state.city ?? ""}
            placeholder="any city"
            className="input-field"
          />
        </div>

        <div>
          <label htmlFor="browse-category" className="voice-etch mb-2.5 block">
            Charted as
          </label>
          <input
            id="browse-category"
            type="text"
            name="category"
            defaultValue={state.category ?? ""}
            placeholder="any category"
            className="input-field"
          />
        </div>

        <fieldset>
          <legend className="voice-etch mb-2.5">Price at most</legend>
          <div className="seg">
            <label>
              <input
                type="radio"
                name="price_max"
                value=""
                defaultChecked={state.priceMax === undefined}
              />
              <span>any</span>
            </label>
            {[1, 2, 3, 4].map((level) => (
              <label key={level}>
                <input
                  type="radio"
                  name="price_max"
                  value={level}
                  defaultChecked={state.priceMax === level}
                />
                <span>{"$".repeat(level)}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="voice-etch mb-2.5">Rated at least</legend>
          <div className="seg">
            <label>
              <input
                type="radio"
                name="min_stars"
                value=""
                defaultChecked={state.minStars === undefined}
              />
              <span>any</span>
            </label>
            {[3, 4, 4.5].map((stars) => (
              <label key={stars}>
                <input
                  type="radio"
                  name="min_stars"
                  value={stars}
                  defaultChecked={state.minStars === stars}
                />
                <span>{stars}✦</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="voice-etch mb-2.5">Signal</legend>
          <label className="toggle">
            {/* hidden "off" + checkbox "on": the later value wins server-side */}
            <input type="hidden" name="open" value="off" />
            <input type="checkbox" name="open" value="on" defaultChecked={state.openOnly} />
            <span className="track" />
            <span className="text-xs text-dim">
              {state.openOnly ? "Only open doors" : "Include archived stars"}
            </span>
          </label>
        </fieldset>

        <fieldset>
          <legend className="voice-etch mb-2.5">Ordered by</legend>
          <div className="seg !grid w-full grid-cols-3">
            {(
              [
                ["rating", "rating"],
                ["reviews", "voices"],
                ["name", "name"],
              ] as const
            ).map(([value, label]) => (
              <label key={value} className="min-w-0">
                <input type="radio" name="sort" value={value} defaultChecked={state.sort === value} />
                <span className="block w-full text-center">{label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <button type="submit" className="btn-brass w-full">
          Survey the sky
        </button>
      </form>
    </aside>
  );
}
