import Link from "next/link";

import { ConstellationArt } from "@/components/constellation-art";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[70svh] max-w-2xl flex-col items-center justify-center px-5 pt-24 text-center">
      <div className="panel w-full max-w-sm overflow-hidden">
        <ConstellationArt id="lost-at-sea-404" categories={[]} className="aspect-[16/10] w-full" />
      </div>
      <p className="voice-etch mt-8">Uncharted waters</p>
      <h1 className="voice-display mt-3 text-3xl font-light text-starlight">
        This page isn&apos;t on <em className="voice-wonk text-gradient-aurora">any map</em>
      </h1>
      <p className="mt-4 max-w-sm text-sm leading-relaxed text-dim">
        The coordinates you followed lead nowhere. Return to the atlas and take a bearing.
      </p>
      <Link href="/" className="btn-brass mt-8">
        Back to the atlas
      </Link>
    </div>
  );
}
