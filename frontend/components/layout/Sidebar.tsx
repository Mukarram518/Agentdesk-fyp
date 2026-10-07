"use client";

import React, { useEffect, useState } from "react";
import {
  DashboardIcon,
  ConversationsIcon,
  LeadsIcon,
  AppointmentsIcon,
  KnowledgeIcon,
  AgentsIcon,
  AnalyticsIcon,
  SettingsIcon,
  CloseIcon,
  ChevronDownIcon,
} from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api/client";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  activeItem?: string;
  onSelectItem?: (item: string) => void;
}

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: DashboardIcon },
  { id: "conversations", label: "Conversations", icon: ConversationsIcon },
  { id: "leads", label: "Leads", icon: LeadsIcon },
  { id: "appointments", label: "Appointments", icon: AppointmentsIcon },
  { id: "knowledge", label: "Knowledge Base", icon: KnowledgeIcon },
  { id: "agents", label: "AI Agents", icon: AgentsIcon },
  { id: "analytics", label: "Analytics", icon: AnalyticsIcon },
  { id: "settings", label: "Settings", icon: SettingsIcon },
];

export function Sidebar({
  isOpen,
  onClose,
  activeItem = "dashboard",
  onSelectItem,
}: SidebarProps) {
  const [systemOnline, setSystemOnline] = useState<boolean | null>(null);

  useEffect(() => {
    // Non-intrusive background check for operational status using centralized API client
    const checkSystem = async () => {
      const isOnline = await apiClient.checkOperationalStatus();
      setSystemOnline(isOnline);
    };
    checkSystem();
  }, []);

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={cn(
          "fixed top-0 bottom-0 left-0 z-50 w-64 bg-slate-900/95 border-r border-slate-800/80 flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 lg:static backdrop-blur-md",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Brand Header */}
        <div className="h-16 px-5 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-500 via-indigo-600 to-cyan-400 flex items-center justify-center font-bold text-white shadow-md shadow-indigo-500/20">
              A
            </div>
            <div className="flex flex-col">
              <span className="font-semibold text-sm tracking-tight text-white leading-none">
                AgentDesk
              </span>
              <span className="text-[10px] text-slate-400 font-medium tracking-wide mt-1">
                AI Business Platform
              </span>
            </div>
          </div>

          <button
            onClick={onClose}
            className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
            aria-label="Close menu"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Business Workspace Switcher Placeholder */}
        <div className="p-3">
          <button
            type="button"
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-slate-950/60 border border-slate-800/80 hover:border-slate-700/80 transition text-left group"
          >
            <div className="flex items-center gap-2.5 overflow-hidden">
              <div className="w-6 h-6 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-semibold flex items-center justify-center shrink-0">
                M
              </div>
              <div className="truncate">
                <p className="text-xs font-medium text-slate-200 truncate leading-none">
                  Mukarram&apos;s Business
                </p>
                <p className="text-[10px] text-slate-400 mt-0.5 truncate">
                  Ready to configure
                </p>
              </div>
            </div>
            <ChevronDownIcon className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-200 shrink-0" />
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
          <div className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Navigation
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeItem === item.id;
            return (
              <button
                key={item.id}
                id={`nav-${item.id}`}
                onClick={() => {
                  onSelectItem?.(item.id);
                  onClose();
                }}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition duration-150 group text-left",
                  isActive
                    ? "bg-indigo-600/15 text-indigo-300 border border-indigo-500/30 shadow-sm"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                )}
              >
                <Icon
                  className={cn(
                    "w-4 h-4 transition-colors",
                    isActive
                      ? "text-indigo-400"
                      : "text-slate-400 group-hover:text-slate-300"
                  )}
                />
                <span className="flex-1 truncate">{item.label}</span>
                {item.id === "dashboard" && (
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                )}
              </button>
            );
          })}
        </nav>

        {/* Operational Status & Owner Profile */}
        <div className="p-3 border-t border-slate-800/80 space-y-2">
          {/* Subtle System Status Pill */}
          <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-slate-950/40 border border-slate-800/50 text-[11px]">
            <span className="text-slate-400">Platform Status</span>
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  "w-2 h-2 rounded-full",
                  systemOnline === null
                    ? "bg-amber-400 animate-pulse"
                    : systemOnline
                    ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]"
                    : "bg-rose-400"
                )}
              />
              <span
                className={cn(
                  "font-medium",
                  systemOnline ? "text-emerald-400" : "text-slate-400"
                )}
              >
                {systemOnline === null
                  ? "Checking"
                  : systemOnline
                  ? "Operational"
                  : "Standby"}
              </span>
            </div>
          </div>

          {/* User Account */}
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-slate-950/60 border border-slate-800/60">
            <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-semibold text-slate-200">
              M
            </div>
            <div className="flex flex-col min-w-0 flex-1">
              <span className="text-xs font-medium text-slate-200 truncate">
                Mukarram Ali
              </span>
              <span className="text-[10px] text-slate-400 truncate">
                Owner Account
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
