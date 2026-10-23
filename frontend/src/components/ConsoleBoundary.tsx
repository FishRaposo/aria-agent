"use client";
import { Fragment } from "react";
import { getProviderMode, getResetKey } from "@/lib/demo-scenarios";
import { useDemoRevision } from "@/lib/use-demo";
/** Reset only application state. Next's persistent route tree must stay mounted. */
export default function ConsoleBoundary({ children }: { children: React.ReactNode }) {
  useDemoRevision();
  return <Fragment key={`${getProviderMode()}-${getResetKey()}`}>{children}</Fragment>;
}
