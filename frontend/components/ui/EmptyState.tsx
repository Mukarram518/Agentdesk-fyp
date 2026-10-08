import React from "react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  actionText,
  onAction,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center p-8 rounded-xl border border-dashed border-border-main bg-warm-ivory/60",
        className
      )}
    >
      {icon && (
        <div className="w-12 h-12 rounded-xl bg-white border border-border-main flex items-center justify-center text-secondary-text mb-4 shadow-xs">
          {icon}
        </div>
      )}
      <h4 className="text-sm font-semibold text-main-text mb-1.5">{title}</h4>
      <p className="text-xs text-secondary-text max-w-xs leading-relaxed mb-4">
        {description}
      </p>
      {actionText && (
        <button
          onClick={onAction}
          className="text-xs font-medium text-cherry hover:text-cherry-hover hover:underline flex items-center gap-1 transition"
        >
          {actionText} &rarr;
        </button>
      )}
    </div>
  );
}
