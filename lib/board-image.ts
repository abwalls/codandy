import type { ExcalidrawElement } from "@excalidraw/excalidraw/element/types";

export async function renderBoardImage(elements: Record<string, unknown>[]) {
  if (!elements.length) throw new Error("Draw something before preparing a visual interpretation.");
  (window as unknown as { EXCALIDRAW_ASSET_PATH: string }).EXCALIDRAW_ASSET_PATH = "/excalidraw-assets/";
  const { exportToBlob, restoreElements } = await import("@excalidraw/excalidraw");
  const blob = await exportToBlob({ elements: restoreElements(elements as unknown as ExcalidrawElement[], null), files: {}, mimeType: "image/png", maxWidthOrHeight: 2048,
    appState: { exportBackground: true, exportEmbedScene: false, viewBackgroundColor: "#ffffff", exportWithDarkMode: false } });
  if (blob.size > 2 * 1024 * 1024) throw new Error("The drawing image exceeds 2 MiB. Simplify the drawing before trying again.");
  return new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(new Error("Could not prepare the drawing preview.")); reader.onload = () => resolve(String(reader.result)); reader.readAsDataURL(blob); });
}
