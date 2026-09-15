"use client";

import { useEffect, useMemo, useState } from "react";
import { Excalidraw, MainMenu, restoreElements } from "@excalidraw/excalidraw";
import type { ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";
import type { ExcalidrawElement } from "@excalidraw/excalidraw/element/types";
import "@excalidraw/excalidraw/index.css";

export default function BoardCanvas({ elements, onChange, highlight, disabled }: { elements: Record<string, unknown>[]; onChange: (elements: Record<string, unknown>[]) => void; highlight: string[]; disabled: boolean }) {
  const initialData = useMemo(() => ({ elements: restoreElements(elements as unknown as ExcalidrawElement[], null), appState: { viewBackgroundColor: "#f8fafc" } }), [elements]);
  const [api, setApi] = useState<ExcalidrawImperativeAPI | null>(null);
  useEffect(() => {
    if (!api) return;
    const fit = () => { const content = api.getSceneElements(); if (content.length) api.scrollToContent(content, { fitToViewport: true }); };
    fit(); window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [api]);
  return <div className="space-y-2">
    {highlight.length > 0 && <button className="text-sm underline" onClick={() => { const selected = api?.getSceneElements().filter(e => highlight.includes(e.id)); if (selected?.length) { api?.updateScene({ appState: { selectedElementIds: Object.fromEntries(selected.map(e => [e.id, true])) } }); api?.scrollToContent(selected); } }}>Locate selected evidence ({highlight.length})</button>}
    <div className="h-[65vh] min-h-[420px] overflow-hidden rounded-xl border" aria-label="Drawing canvas">
      <Excalidraw initialData={initialData} excalidrawAPI={setApi} viewModeEnabled={disabled} validateEmbeddable={() => false}
        onLinkOpen={(_, event) => event.preventDefault()} onPaste={(data) => !data.files?.length}
        UIOptions={{ tools: { image: false }, canvasActions: { loadScene: false, saveToActiveFile: false, export: false, saveAsImage: true } }}
        onChange={(next) => onChange(next.filter(e => !e.isDeleted).map(e => ({ ...e, link: null, customData: undefined })) as unknown as Record<string, unknown>[])}>
        <MainMenu><MainMenu.DefaultItems.SaveAsImage /><MainMenu.DefaultItems.ClearCanvas /><MainMenu.DefaultItems.ToggleTheme /></MainMenu>
      </Excalidraw>
    </div>
  </div>;
}
