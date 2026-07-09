"use client";

import { useState } from "react";

import { ConstellationArt } from "@/components/constellation-art";

/**
 * External enrichment image with a graceful landing: if the URL is dead or
 * blocked, the listing falls back to its constellation sigil.
 */
export function ListingImage({
  src,
  alt,
  listingId,
  categories,
}: {
  src: string;
  alt: string;
  listingId: string;
  categories: string[];
}) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return <ConstellationArt id={listingId} categories={categories} className="h-full w-full" />;
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.04]"
    />
  );
}
