import type { Metadata } from "next";
import DemoShell from "@/components/DemoShell";
import ErrorBoundary from "@/components/ErrorBoundary";
import Nav from "@/components/Nav";
import "./globals.css";



export const metadata: Metadata = {
  title: {
    default: "ARIA — an agent you can inspect and control",
    template: "%s · ARIA",
  },
  description:
    "Follow a request through permission, human review and execution. ARIA pairs a visual recruiter demo with a real Python harness whose approvals bind exact actions and admit a single execution claim.",
  applicationName: "ARIA",
  authors: [{ name: "Vinícius Raposo" }],
  keywords: ["agent harness", "approval boundary", "controlled execution", "portfolio", "FastAPI", "Next.js"],
  openGraph: {
    title: "ARIA — an agent you can inspect and control",
    description:
      "Controlled agent execution: validated tools, single-use approvals, inspectable traces, saved skill evidence.",
    type: "website",
    siteName: "ARIA",
  },
  twitter: {
    card: "summary",
    title: "ARIA — an agent you can inspect and control",
    description:
      "Controlled agent execution: validated tools, single-use approvals, inspectable traces, saved skill evidence.",
  },
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
