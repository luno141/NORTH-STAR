import type { Metadata } from "next";
import { IBM_Plex_Mono, Manrope, Space_Grotesk } from "next/font/google";

import "./globals.css";
import { Nav } from "@/components/Nav";

const bodyFont = Manrope({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap"
});

const displayFont = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "700"],
  display: "swap"
});

const monoFont = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500"],
  display: "swap"
});

export const metadata: Metadata = {
  title: "N★RTH STAR | Threat Intelligence",
  description: "N★RTH STAR federated threat-intelligence dashboard"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${bodyFont.variable} ${displayFont.variable} ${monoFont.variable}`}>
        <div className="site-shell">
          <div className="space-backdrop" aria-hidden />
          <div className="shell-noise" aria-hidden />
          <Nav />
          <main className="w-full px-4 py-6 sm:px-6 lg:px-8 xl:px-10 2xl:px-12">{children}</main>
        </div>
      </body>
    </html>
  );
}
