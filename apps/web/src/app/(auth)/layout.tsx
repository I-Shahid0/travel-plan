import type { ReactNode } from "react";

import { Aurora } from "@/components/aurora";
import { ConstellationArt } from "@/components/constellation-art";
import { Starfield } from "@/components/starfield";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-svh items-center justify-center overflow-hidden px-5 pt-24 pb-16">
      <Aurora dim />
      <Starfield density={0.7} />

      <div className="panel relative z-10 grid w-full max-w-3xl overflow-hidden rounded-2xl! md:grid-cols-[1fr_1.1fr]">
        {/* ornamental panel */}
        <div className="relative hidden flex-col justify-between overflow-hidden border-r border-(--line) p-8 md:flex">
          <ConstellationArt
            id="meridian-gate"
            categories={["Hotels & Travel"]}
            className="absolute inset-0 h-full w-full opacity-70"
          />
          <div className="relative">
            <p className="voice-etch">Meridian</p>
          </div>
          <div className="relative">
            <p className="voice-display text-2xl leading-snug font-light text-starlight">
              Every navigator
              <br />
              <em className="voice-wonk text-gradient-aurora">sees a different sky.</em>
            </p>
            <p className="mt-3 text-xs leading-relaxed text-dim">
              Accounts unlock personalized ranking and journey plotting.
            </p>
          </div>
        </div>

        <div className="p-8 sm:p-10">{children}</div>
      </div>
    </div>
  );
}
