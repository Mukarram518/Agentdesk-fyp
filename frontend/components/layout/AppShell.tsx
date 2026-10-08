"use client";

import React, { useState } from "react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeItem, setActiveItem] = useState("dashboard");

  const titles: Record<string, string> = {
    dashboard: "Dashboard",
    conversations: "Conversations",
    leads: "Leads",
    appointments: "Appointments",
    knowledge: "Knowledge Base",
    agents: "AI Agents",
    analytics: "Analytics",
    settings: "Settings",
  };

  return (
    <div className="min-h-screen flex bg-warm-ivory text-main-text">
      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activeItem={activeItem}
        onSelectItem={(item) => setActiveItem(item)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          onOpenSidebar={() => setSidebarOpen(true)}
          activeItemTitle={titles[activeItem] || "Dashboard"}
        />
        <main className="flex-1 p-6 sm:p-8 lg:p-10 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
