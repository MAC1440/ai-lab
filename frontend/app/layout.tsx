import type { Metadata } from "next";

import { StoreProvider } from "@/components/providers/store-provider";
import { AppShell } from "@/components/shell/app-shell";
import "@xterm/xterm/css/xterm.css";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "AI Lab",
    template: "%s | AI Lab",
  },
  description:
    "A local-first AI workspace for chat, coding tasks, knowledge, changes, verification, and direct workspace terminals.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full">
        <StoreProvider>
          <AppShell>{children}</AppShell>
        </StoreProvider>
      </body>
    </html>
  );
}
