import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

const nextConfig: NextConfig = {
  async headers() {
    // Turbopack gives JS chunks new URLs each time `next dev` starts. If the
    // browser reuses a cached copy of the page HTML from a previous run, that
    // HTML points at chunk URLs the new server doesn't serve - so the markup
    // renders but React never hydrates and every button is silently dead.
    // Telling the browser not to store dev responses keeps the HTML and the
    // chunks it references from ever getting out of step across a restart.
    // Production is left alone so real caching still applies.
    if (!isDev) return [];
    return [
      {
        source: "/:path*",
        headers: [{ key: "Cache-Control", value: "no-store, must-revalidate" }],
      },
    ];
  },
};

export default nextConfig;
