import type { Metadata } from "next";
import { Fraunces, IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import type { ReactNode } from "react";

import { Footer } from "@/components/footer";
import { Nav } from "@/components/nav";

import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  axes: ["opsz", "SOFT", "WONK"],
});

const grotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-grotesk",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: {
    default: "Meridian — a celestial atlas of earthly places",
    template: "%s · Meridian",
  },
  description:
    "Search 150,000+ real places with hybrid retrieval, personalization, and LLM trip planning. A star atlas for earthly travel.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={`${fraunces.variable} ${grotesk.variable} ${plexMono.variable} dark`}
      // the inline script below appends .js before hydration — expected drift
      suppressHydrationWarning
    >
      <body className="min-h-screen antialiased">
        {/* mark JS availability before paint so reveal-on-scroll can't hide
            content from no-JS visitors or crawlers */}
        <script
          dangerouslySetInnerHTML={{
            __html: "document.documentElement.classList.add('js')",
          }}
        />
        <Nav />
        <main className="relative z-10">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
