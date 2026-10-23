import type { Metadata } from "next";
import DemoShell from "@/components/DemoShell";
import ErrorBoundary from "@/components/ErrorBoundary";
import Nav from "@/components/Nav";
import "./globals.css";



export const metadata: Metadata = {
  title: "ARIA — Agent Control Console",
  description:
    "Operate, trace, and govern an autonomous agent: runs, traces, tool registry, approval queue, and memory.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-ink-950 text-ink-100 antialiased">
        <a href="#main-content" className="skip-link">Skip to content</a><Nav />
        <DemoShell><main id="main-content" tabIndex={-1} className="mx-auto max-w-7xl px-6 py-8">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main></DemoShell>
      </body>
    </html>
  );
}
