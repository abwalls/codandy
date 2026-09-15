import { cpSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const destination = new URL("../public/excalidraw-assets/fonts/", import.meta.url);
mkdirSync(destination, { recursive: true });
cpSync(fileURLToPath(new URL("../node_modules/@excalidraw/excalidraw/dist/prod/fonts/", import.meta.url)), fileURLToPath(destination), { recursive: true });
