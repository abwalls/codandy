"use client";

import { ThemeProvider, useTheme } from "next-themes";
import { Palette } from "lucide-react";
import { useSyncExternalStore, type ReactNode } from "react";

const subscribe = () => () => {};

const themes = [
  ["atlas", "Atlas Midnight"],
  ["forbright", "Demo background"],
  ["tennessee", "Vol Orange"],
  ["violet", "Violet Night"],
  ["graphite", "Graphite"],
] as const;

export function AtlasThemeProvider({ children }: { children: ReactNode }) {
  return <ThemeProvider attribute="data-theme" defaultTheme="atlas" enableSystem={false}
    storageKey="code-atlas-theme" themes={themes.map(([id]) => id)}>{children}</ThemeProvider>;
}

export function ThemePicker() {
  const { theme, setTheme } = useTheme();
  const hydrated = useSyncExternalStore(subscribe, () => true, () => false);
  return <label className="flex min-w-0 items-center gap-1.5 rounded-lg border border-white/10 bg-background px-2 py-1.5 text-xs text-slate-300">
    <Palette aria-hidden="true" className="size-4 shrink-0 text-cyan-300" />
    <span className="sr-only">Color scheme</span>
    <select aria-label="Color scheme" className="max-w-[115px] bg-background text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring" value={hydrated ? theme || "atlas" : "atlas"} onChange={event => setTheme(event.target.value)}>
      {themes.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
    </select>
  </label>;
}
