import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FYVE",
  description: "Find your best-fit Georgia Tech professor for one course.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
