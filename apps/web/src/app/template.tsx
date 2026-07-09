import type { ReactNode } from "react";

/** Soft page-enter veil on every route change. */
export default function Template({ children }: { children: ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
