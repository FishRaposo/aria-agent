import type { ReactNode } from "react";
import DemoBadge from "@/components/DemoBadge";

interface PageHeaderProps {
  title: string;
  description?: string;
  demo?: boolean;
  demoForced?: boolean;
  demoReason?: string;
  actions?: ReactNode;
}

export default function PageHeader({
  title,
  description,
  demo,
  demoForced,
  demoReason,
  actions,
}: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-ink-50">
            {title}
          </h1>
          {demo && (
            <DemoBadge reason={demoReason} forced={demoForced} />
          )}
        </div>
        {description && (
          <p className="mt-1 max-w-2xl text-sm text-ink-400">{description}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
