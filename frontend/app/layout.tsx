import type { Metadata } from "next";
import GtMark from "@/components/GtMark";
import "./globals.css";

export const metadata: Metadata = {
  title: "FYVE",
  description: "Find your best-fit Georgia Tech professor for one course.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      {/* Mounted here rather than per-screen so the marker is present on
          every step without each one having to remember it. */}
      <body>
        {children}
        <GtMark />
      </body>
    </html>
  );
}
