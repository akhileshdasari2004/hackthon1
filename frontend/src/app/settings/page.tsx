"use client";

import { SettingsPanel } from "@/components/SettingsPanel";

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
      <p className="mt-2 text-muted-foreground">Configure Agira execution behavior.</p>
      <div className="mt-10">
        <SettingsPanel />
      </div>
    </div>
  );
}
