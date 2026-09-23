import type { Metadata } from "next";
import GtMark from "@/components/GtMark";
import HomeButton from "@/components/HomeButton";
import "./globals.css";

export const metadata: Metadata = {
  title: "FYVE",
  description: "Find your best-fit Georgia Tech professor for one course.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      {/* Mounted here rather than per-screen so the backdrop, start-over
          button and GT marker are present on every step without each one
          having to remember them. */}
      <body>
        <div className="page-backdrop" aria-hidden="true" />
        <div className="landing-glow" aria-hidden="true" />
        <div className="landing-shapes" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </div>
        <HomeButton />
        {children}
        <GtMark />
      </body>
    </html>
  );
}
