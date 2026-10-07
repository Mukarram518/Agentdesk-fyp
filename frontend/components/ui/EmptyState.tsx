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
        "flex flex-col items-center justify-center text-center p-8 rounded-xl border border-dashed border-slate-800/80 bg-slate-950/40",
        className
      )}
    >
      {icon && (
        <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-400 mb-4 shadow-sm">
          {icon}
        </div>
      )}
      <h4 className="text-sm font-semibold text-slate-200 mb-1.5">{title}</h4>
      <p className="text-xs text-slate-400 max-w-xs leading-relaxed mb-4">
        {description}
      </p>
      {actionText && (
        <button
          onClick={onAction}
          className="text-xs font-medium text-indigo-400 hover:text-indigo-300 hover:underline flex items-center gap-1 transition"
        >
          {actionText} &rarr;
        </button>
      )}
    </div>
  );
}
