"use client";

import React from "react";
import {
  MenuIcon,
  SearchIcon,
  BellIcon,
  SparklesIcon,
} from "@/components/ui/icons";
import { Button } from "@/components/ui/Button";

interface HeaderProps {
  onOpenSidebar: () => void;
  activeItemTitle?: string;
}

export function Header({
  onOpenSidebar,
  activeItemTitle = "Dashboard",
}: HeaderProps) {
  return (
    <header className="h-16 px-6 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-30 flex items-center justify-between gap-4">
      {/* Left: Mobile Menu Toggle & Title */}
      <div className="flex items-center gap-3">
        <button
          id="mobile-sidebar-toggle"
          onClick={onOpenSidebar}
          className="lg:hidden p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          aria-label="Open sidebar"
        >
          <MenuIcon className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2">
          <h1 className="text-base font-semibold text-white tracking-tight">
            {activeItemTitle}
          </h1>
          <span className="hidden sm:inline-block text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700/60 font-medium">
            Workspace Shell
          </span>
        </div>
      </div>

      {/* Middle: Search Bar Placeholder */}
      <div className="hidden md:flex items-center flex-1 max-w-md mx-4">
        <div className="w-full relative">
          <SearchIcon className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            readOnly
            placeholder="Search conversations, leads, or knowledge... (⌘K)"
            className="w-full pl-9 pr-4 py-1.5 rounded-lg bg-slate-950/70 border border-slate-800 text-xs text-slate-300 placeholder:text-slate-500 focus:outline-none focus:border-slate-700 cursor-pointer"
          />
        </div>
      </div>

      {/* Right: Notifications & Quick Actions */}
      <div className="flex items-center gap-3">
        {/* Notification Bell */}
        <button
          id="notifications-btn"
          type="button"
          className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition relative"
          aria-label="Notifications"
        >
          <BellIcon className="w-4 h-4" />
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 absolute top-2 right-2" />
        </button>

        {/* Primary Workspace Action */}
        <Button
          variant="primary"
          size="sm"
          className="gap-1.5 text-xs font-medium"
        >
          <SparklesIcon className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Configure</span> Workspace
        </Button>
      </div>
    </header>
  );
}
