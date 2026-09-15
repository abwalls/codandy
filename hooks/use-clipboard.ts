"use client";

import { useState } from "react";

/** Copies text and reports whether the browser allowed it. */
export function useClipboard() {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const copy = (text: string) => {
    if (!navigator.clipboard) {
      setState("failed");
      return;
    }
    navigator.clipboard.writeText(text).then(() => setState("copied"), () => setState("failed"));
  };
  return [state, copy] as const;
}
