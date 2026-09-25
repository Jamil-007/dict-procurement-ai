import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Serif } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";
import { BetaBadge } from "@/components/beta-badge";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-sans",
});

// Only the printed report uses the serif, so it reads as a document.
const plexSerif = IBM_Plex_Serif({
  subsets: ["latin"],
  weight: ["400", "600"],
  variable: "--font-plex-serif",
});

export const metadata: Metadata = {
  title: "AI Analyst — DICT",
  description: "Procurement document review for the Bids and Awards Committee",
  icons: {
    icon: [{ url: "/dict-logo.png" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/dict-logo.png" type="image/png" />
      </head>
      <body
        className={`${plexSans.variable} ${plexSerif.variable} font-sans antialiased`}
      >
        <BetaBadge />
        {children}
        <Toaster />
      </body>
    </html>
  );
}
