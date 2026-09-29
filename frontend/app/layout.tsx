import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/components/theme-provider";
import { NavTabs } from "@/components/nav-tabs";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "DICT Procurement",
  description: "Procurement document compliance review",
  icons: {
    icon: [
      { url: "/dict-logo.png" },
    ],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/dict-logo.png" type="image/png" />
      </head>
      <body className={`${inter.variable} font-sans antialiased`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem={false}
          disableTransitionOnChange
        >
          <div className="flex h-screen flex-col">
            <NavTabs />
            <div className="min-h-0 flex-1">{children}</div>
          </div>
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
