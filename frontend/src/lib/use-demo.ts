"use client";
import { useSyncExternalStore } from "react";
import { getDemoRevision, subscribeDemo } from "./demo-scenarios";
export function useDemoRevision() { return useSyncExternalStore(subscribeDemo, getDemoRevision, () => 0); }
