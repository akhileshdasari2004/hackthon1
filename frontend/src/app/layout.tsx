import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { NavBar } from "@/components/NavBar";
import { Providers } from "@/components/Providers";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Agira — Autonomous Software Engineer",
  description:
    "An autonomous software engineer that audits, fixes, validates and explains repositories.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <Providers>
          <NavBar />
          <main>{children}</main>
        </Providers>
      </body>
    </html>
  );
}
