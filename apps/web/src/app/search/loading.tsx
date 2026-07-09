export default function SearchLoading() {
  return (
    <div className="mx-auto max-w-7xl px-5 pt-28 pb-16" aria-busy="true" aria-live="polite">
      <div className="mb-10">
        <p className="voice-etch mb-3">Observation deck</p>
        <div className="skeleton h-10 w-72 max-w-full" />
        <p className="mt-4 font-mono text-xs tracking-[0.14em] text-faint">
          <span className="star-twinkle inline-block">✦</span> consulting the sky…
        </p>
      </div>

      <div className="grid gap-10 lg:grid-cols-[280px_1fr]">
        <div className="panel-etched hidden space-y-6 p-6 lg:block">
          <div className="skeleton h-10 w-full" />
          <div className="skeleton h-8 w-4/5" />
          <div className="skeleton h-10 w-full" />
          <div className="skeleton h-8 w-3/5" />
          <div className="skeleton h-11 w-full !rounded-full" />
        </div>

        <ul className="grid list-none grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 9 }).map((_, index) => (
            <li key={index} className="card-listing">
              <div className="skeleton aspect-[16/10] !rounded-none" />
              <div className="space-y-3 p-4">
                <div className="skeleton h-5 w-3/4" />
                <div className="skeleton h-3.5 w-1/2" />
                <div className="flex gap-1.5">
                  <div className="skeleton h-5 w-16 !rounded-full" />
                  <div className="skeleton h-5 w-20 !rounded-full" />
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
