import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Playfair_Display } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";
import { BetaBadge } from "@/components/beta-badge";

// Everything on screen. 400/500 carry body text and metadata, 600/700/800 the
// headings and titles — load only those five, since each weight is a file.
const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-jakarta",
});

// Accent only: signature and attestation lines in a report endorsement, where
// a formal serif reads as a signed document rather than as another screen.
// preload is off because nothing in the normal UI uses it — the @font-face is
// declared either way, and the browser fetches the file only once a rule asks
// for it. Turn preload back on if the serif ever lands above the fold.
const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ["400", "600"],
  style: ["normal", "italic"],
  variable: "--font-playfair",
  preload: false,
});

export const metadata: Metadata = {
  title: "Procurement Intelligence Platform",
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
        className={`${jakarta.variable} ${playfair.variable} font-sans antialiased`}
      >
        <BetaBadge />
        {children}
        <Toaster />
      </body>
    </html>
  );
}
