export default function LoadingPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="mb-8 flex flex-col items-center gap-4 text-center">
        <div className="relative h-12 w-12">
          <div className="absolute inset-0 animate-pulse rounded-full border-2 border-foreground/20" />
          <div className="absolute inset-0 animate-ping rounded-full border-2 border-foreground/40" />
        </div>
        <div>
          <h2 className="text-lg font-medium text-foreground">Loading Agira</h2>
          <p className="mt-1 text-sm text-muted-foreground">Preparing your workspace…</p>
        </div>
      </div>
      <div className="h-1 w-48 overflow-hidden rounded-full bg-muted">
        <div className="h-full w-1/3 animate-progress rounded-full bg-foreground" />
      </div>
    </div>
  );
}