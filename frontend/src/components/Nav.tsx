"use client";

import clsx from "clsx";
import {
  Activity,
  BookOpen,
  CheckSquare,
  Database,
  MessageSquare,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/runs", label: "Runs", icon: Activity },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/skills", label: "Skills", icon: BookOpen },
  { href: "/tools", label: "Tools", icon: Wrench },
  { href: "/approvals", label: "Approvals", icon: CheckSquare },
  { href: "/memory", label: "Memory", icon: Database },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-20 border-b border-ink-800 bg-ink-950/80 backdrop-blur">
      <nav className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-3">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-sm font-bold text-white">
            H
          </span>
          <span className="text-base font-semibold tracking-tight text-ink-50">
            ARIA
            <span className="ml-1 hidden text-ink-500 sm:inline">
              Agent Console
            </span>
          </span>
        </Link>

        <div className="flex items-center gap-1 overflow-x-auto">
          {LINKS.map(({ href, label, icon: Icon }) => {
            const active =
              pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                className={clsx("nav-link", active && "nav-link-active")}
              >
                <Icon className="h-4 w-4" />
                <span className="hidden sm:inline">{label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </header>
  );
}
