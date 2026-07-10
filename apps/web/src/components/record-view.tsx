"use client";

import { useEffect, useRef } from "react";

import { recordListingView } from "@/app/listing/actions";

/**
 * Fire-and-forget view recording on real page mounts only — server-side
 * recording would also count Next.js link prefetches. Renders nothing.
 */
export function RecordView(props: {
  listingId: string;
  title: string;
  city: string | null;
  categories: string[];
  source?: string;
  anchorId?: string;
}) {
  const recorded = useRef<string | null>(null);

  useEffect(() => {
    if (recorded.current === props.listingId) return;
    recorded.current = props.listingId;
    recordListingView(props).catch(() => {
      // Event loss is acceptable; page behavior never depends on it.
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.listingId]);

  return null;
}
