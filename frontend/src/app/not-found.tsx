import Link from "next/link";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="text-center">
        <p className="text-6xl font-semibold tracking-tight text-muted-foreground/30">404</p>
        <h1 className="mt-4 text-2xl font-semibold tracking-tight text-foreground">
          Page not found
        </h1>
        <p className="mt-2 max-w-sm text-muted-foreground">
          The page you are looking for does not exist or has been moved.
        </p>
        <div className="mt-8 flex gap-3 justify-center">
          <Link
            href="/"
            className="rounded-full bg-foreground px-6 py-2.5 text-sm font-medium text-background transition-opacity hover:opacity-80"
          >
            Go home
          </Link>
          <Link
            href="/analysis"
            className="rounded-full border border-border px-6 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            Start analysis
          </Link>
        </div>
      </div>
    </div>
  );
}