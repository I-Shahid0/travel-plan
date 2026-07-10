import { getSessionCookie } from "better-auth/cookies";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Optimistic redirect for protected routes: a missing session cookie means
 * the visitor is definitely signed out, so bounce them to sign-in early.
 * Real (cryptographic) session validation happens in the pages and server
 * actions via `auth.api.getSession` — this is UX, not the security boundary.
 */
export function proxy(request: NextRequest) {
  const sessionCookie = getSessionCookie(request);
  if (!sessionCookie) {
    const signIn = new URL("/sign-in", request.url);
    signIn.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(signIn);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/plan/:path*", "/profile/:path*", "/foryou/:path*", "/history/:path*"],
};
