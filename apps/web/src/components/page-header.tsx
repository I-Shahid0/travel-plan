import type { ReactNode } from "react";

import { Aurora } from "@/components/aurora";
import { CompassRose } from "@/components/compass";

/**
 * Shared header treatment for inner pages: dim aurora, a brass compass
 * watermark drifting behind the title, and the etched kicker line.
 */
export function PageHeader({
  kicker,
  title,
  children,
}: {
  kicker: string;
  title: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="relative mb-10">
      <div className="pointer-events-none absolute -inset-x-24 -top-28 bottom-0 overflow-hidden" aria-hidden="true">
        <Aurora dim />
      </div>
      <CompassRose
        className="pointer-events-none absolute -top-6 right-0 hidden h-36 w-36 text-brass/[0.08] sm:block"
        spin
      />
      <div className="relative">
        <p className="voice-etch mb-3">{kicker}</p>
        <h1 className="voice-display text-3xl font-light text-starlight sm:text-4xl">{title}</h1>
        {children}
      </div>
    </header>
  );
}
