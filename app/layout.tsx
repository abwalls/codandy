import type { Metadata } from "next";
import "./globals.css";
import { CodandyThemeProvider } from "@/components/theme-picker";

export const metadata: Metadata = {
  title: "Codandy | Repository Intelligence",
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
      <body className="antialiased"><CodandyThemeProvider>{children}</CodandyThemeProvider></body>
    </html>
  );
}
