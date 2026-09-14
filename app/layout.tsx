import type { Metadata } from "next";
import "./globals.css";
import { AtlasThemeProvider } from "@/components/theme-picker";

export const metadata: Metadata = {
  title: "Code Atlas | Repository Intelligence",
  description: "Build a grounded, interactive map of an unfamiliar codebase.",
  manifest: "/manifest.webmanifest",
  other: {
    "theme-color": "#07101c",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased"><AtlasThemeProvider>{children}</AtlasThemeProvider></body>
    </html>
  );
}
