"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

const appLinks = [
  { href: "/analysis", label: "Analysis" },
  { href: "/history", label: "History" },
  { href: "/settings", label: "Settings" },
];

const landingAnchors = [
  { href: "#features", label: "Features" },
  { href: "#architecture", label: "Architecture" },
  { href: "#how-it-works", label: "How it works" },
];

export function NavBar() {
  const pathname = usePathname();
  const isLanding = pathname === "/";
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (isLanding) {
    return (
      <header
        className={cn(
          "fixed top-0 right-0 left-0 z-50 transition-all duration-300",
          scrolled ? "border-b border-border bg-background/80 backdrop-blur-xl" : "bg-transparent",
        )}
      >
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="text-[15px] font-semibold tracking-tight">
            Agira
          </Link>
          <nav className="hidden items-center gap-6 md:flex">
            {landingAnchors.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-[13px] text-muted-foreground transition-colors hover:text-foreground"
              >
                {link.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link href="/analysis" className="hidden text-[13px] text-muted-foreground hover:text-foreground sm:inline">
              Dashboard
            </Link>
            <Button asChild size="sm" className="rounded-full">
              <Link href="/analysis">Start Analysis</Link>
            </Button>
          </div>
        </div>
      </header>
    );
  }

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link href="/" className="text-[15px] font-semibold tracking-tight">
          Agira
        </Link>
        <nav className="flex items-center gap-1">
          {[{ href: "/", label: "Home" }, ...appLinks].map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "rounded-full px-4 py-1.5 text-[13px] transition-colors",
                pathname === link.href
                  ? "bg-muted font-medium text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );
}
