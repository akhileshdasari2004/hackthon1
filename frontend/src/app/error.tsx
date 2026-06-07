"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to console in development
    console.error("[Agira] App error:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-6">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          Something went wrong
        </h1>
        <p className="mt-3 max-w-md text-muted-foreground">
          An unexpected error occurred. Your analysis state has been preserved.
          {error.digest && (
            <span className="ml-2 font-mono text-xs text-muted-foreground/60">
              ID: {error.digest}
            </span>
          )}
        </p>
      </div>
      <div className="flex gap-3">
        <button
          onClick={reset}
          className="rounded-full bg-foreground px-6 py-2.5 text-sm font-medium text-background transition-opacity hover:opacity-80"
        >
          Try again
        </button>
        <Link
          href="/"
          className="rounded-full border border-border px-6 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-muted"
        >
          Go home
        </Link>
      </div>
    </div>
  );
}