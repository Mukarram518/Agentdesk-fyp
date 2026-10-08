import React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost";
  size?: "sm" | "md" | "lg";
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  className,
  ...props
}: ButtonProps) {
  const variantStyles = {
    primary:
      "bg-cherry hover:bg-cherry-hover text-white shadow-xs shadow-cherry/20 active:scale-[0.98]",
    secondary:
      "bg-cherry-soft hover:bg-cherry-light text-cherry border border-border-main active:scale-[0.98]",
    outline:
      "border border-border-main hover:border-cherry/50 text-main-text hover:bg-cherry-soft active:scale-[0.98]",
    ghost:
      "text-secondary-text hover:text-main-text hover:bg-cherry-soft",
  };

  const sizeStyles = {
    sm: "px-2.5 py-1.5 text-xs rounded-md",
    md: "px-3.5 py-2 text-sm rounded-lg",
    lg: "px-4.5 py-2.5 text-base rounded-lg",
  };

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center font-medium transition duration-150 focus:outline-none focus:ring-2 focus:ring-cherry/30 disabled:opacity-50 disabled:cursor-not-allowed",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
