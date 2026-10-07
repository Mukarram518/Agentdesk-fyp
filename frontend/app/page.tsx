"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  ConversationsIcon,
  LeadsIcon,
  AppointmentsIcon,
  KnowledgeIcon,
  AgentsIcon,
  SparklesIcon,
  ArrowRightIcon,
  CheckCircleIcon,
} from "@/components/ui/icons";

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<"all" | "conversations" | "leads" | "appointments">("all");

  return (
    <AppShell>
      <div className="space-y-8">
        {/* Top Greeting Section */}
        <section className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Good morning, Mukarram
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              Here&apos;s what&apos;s happening with your business.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <Badge variant="indigo" className="text-xs py-1 px-3">
              Workspace Initialized
            </Badge>
            <Button variant="secondary" size="sm" className="text-xs">
              Workspace Settings
            </Button>
          </div>
        </section>

        {/* Workspace Readiness / Setup Guidance Banner */}
        <section className="p-6 rounded-2xl border border-indigo-500/30 bg-gradient-to-r from-indigo-950/40 via-slate-900/60 to-slate-950/80 shadow-lg relative overflow-hidden">
          <div className="absolute right-0 top-0 translate-x-12 -translate-y-12 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div className="max-w-2xl">
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 mb-3">
                <SparklesIcon className="w-3.5 h-3.5 text-indigo-400" />
                <span>Workspace Ready for Setup</span>
              </div>
              <h3 className="text-lg sm:text-xl font-semibold text-white">
                Complete your business setup to activate AI agents
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 mt-1.5 leading-relaxed">
                Connect your business knowledge base and communication channels. Once configured,
                your AI agents will automatically interact with visitors, qualify leads, and manage bookings.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <Button variant="primary" size="sm" className="gap-2 text-xs">
                <span>Start Configuration</span>
                <ArrowRightIcon className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>

          {/* 3 Onboarding Steps */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6 pt-6 border-t border-slate-800/80">
            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-950/50 border border-slate-800/60">
              <div className="w-7 h-7 rounded-md bg-indigo-500/10 text-indigo-400 flex items-center justify-center shrink-0 text-xs font-semibold">
                1
              </div>
              <div>
                <p className="text-xs font-medium text-slate-200">Knowledge Base</p>
                <p className="text-[11px] text-slate-400 mt-0.5">Add business documents and FAQs</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-950/50 border border-slate-800/60">
              <div className="w-7 h-7 rounded-md bg-cyan-500/10 text-cyan-400 flex items-center justify-center shrink-0 text-xs font-semibold">
                2
              </div>
              <div>
                <p className="text-xs font-medium text-slate-200">Connect Channels</p>
                <p className="text-[11px] text-slate-400 mt-0.5">Enable Web Chat &amp; WhatsApp</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-950/50 border border-slate-800/60">
              <div className="w-7 h-7 rounded-md bg-emerald-500/10 text-emerald-400 flex items-center justify-center shrink-0 text-xs font-semibold">
                3
              </div>
              <div>
                <p className="text-xs font-medium text-slate-200">Configure Agents</p>
                <p className="text-[11px] text-slate-400 mt-0.5">Set qualification and booking rules</p>
              </div>
            </div>
          </div>
        </section>

        {/* Metric Overview Cards: [ Conversations ] [ Leads ] [ Appointments ] */}
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Card 1: Conversations */}
          <div
            onClick={() => setActiveTab("conversations")}
            className={`p-5 rounded-xl border transition cursor-pointer text-left ${
              activeTab === "conversations"
                ? "bg-slate-900/90 border-indigo-500/50 ring-1 ring-indigo-500/20"
                : "bg-slate-900/40 border-slate-800/80 hover:border-slate-700/80 hover:bg-slate-900/60"
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Conversations
              </span>
              <div className="w-7 h-7 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center">
                <ConversationsIcon className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white tracking-tight">0</span>
              <span className="text-xs text-slate-400">active sessions</span>
            </div>
            <div className="mt-3 flex items-center gap-1.5 text-[11px] text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
              <span>Channels awaiting incoming traffic</span>
            </div>
          </div>

          {/* Card 2: Leads */}
          <div
            onClick={() => setActiveTab("leads")}
            className={`p-5 rounded-xl border transition cursor-pointer text-left ${
              activeTab === "leads"
                ? "bg-slate-900/90 border-indigo-500/50 ring-1 ring-indigo-500/20"
                : "bg-slate-900/40 border-slate-800/80 hover:border-slate-700/80 hover:bg-slate-900/60"
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Leads
              </span>
              <div className="w-7 h-7 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center">
                <LeadsIcon className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white tracking-tight">0</span>
              <span className="text-xs text-slate-400">qualified prospects</span>
            </div>
            <div className="mt-3 flex items-center gap-1.5 text-[11px] text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
              <span>Pipeline ready for capture</span>
            </div>
          </div>

          {/* Card 3: Appointments */}
          <div
            onClick={() => setActiveTab("appointments")}
            className={`p-5 rounded-xl border transition cursor-pointer text-left ${
              activeTab === "appointments"
                ? "bg-slate-900/90 border-indigo-500/50 ring-1 ring-indigo-500/20"
                : "bg-slate-900/40 border-slate-800/80 hover:border-slate-700/80 hover:bg-slate-900/60"
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Appointments
              </span>
              <div className="w-7 h-7 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
                <AppointmentsIcon className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white tracking-tight">0</span>
              <span className="text-xs text-slate-400">scheduled</span>
            </div>
            <div className="mt-3 flex items-center gap-1.5 text-[11px] text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
              <span>Calendar ready for sync</span>
            </div>
          </div>
        </section>

        {/* Tab Filter Pills */}
        <div className="flex items-center gap-2 pt-2 border-b border-slate-800/80 pb-3">
          <span className="text-xs text-slate-400 mr-2 font-medium">Filter view:</span>
          {(["all", "conversations", "leads", "appointments"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`text-xs px-3 py-1.5 rounded-md font-medium capitalize transition ${
                activeTab === tab
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-slate-900 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              {tab === "all" ? "All Sections" : tab}
            </button>
          ))}
        </div>

        {/* Main Content Grid: Recent Conversations, Recent Leads, Upcoming Appointments */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Section 1: Recent conversations */}
          {(activeTab === "all" || activeTab === "conversations") && (
            <Card className="flex flex-col">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <ConversationsIcon className="w-4 h-4 text-indigo-400" />
                  <CardTitle>Recent conversations</CardTitle>
                </div>
                <Badge variant="outline">0 Total</Badge>
              </CardHeader>
              <div className="flex-1 flex flex-col justify-center">
                <EmptyState
                  icon={<ConversationsIcon className="w-6 h-6" />}
                  title="No conversations yet"
                  description="Incoming customer messages across your Web Chat and WhatsApp channels will appear here in real time."
                  actionText="Preview chat interface"
                />
              </div>
            </Card>
          )}

          {/* Section 2: Recent leads */}
          {(activeTab === "all" || activeTab === "leads") && (
            <Card className="flex flex-col">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <LeadsIcon className="w-4 h-4 text-cyan-400" />
                  <CardTitle>Recent leads</CardTitle>
                </div>
                <Badge variant="outline">0 Total</Badge>
              </CardHeader>
              <div className="flex-1 flex flex-col justify-center">
                <EmptyState
                  icon={<LeadsIcon className="w-6 h-6" />}
                  title="No leads captured yet"
                  description="When AI agents interact with potential customers and extract contact information, verified leads will be listed here."
                  actionText="View lead settings"
                />
              </div>
            </Card>
          )}

          {/* Section 3: Upcoming appointments */}
          {(activeTab === "all" || activeTab === "appointments") && (
            <Card className="flex flex-col">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <AppointmentsIcon className="w-4 h-4 text-emerald-400" />
                  <CardTitle>Upcoming appointments</CardTitle>
                </div>
                <Badge variant="outline">0 Total</Badge>
              </CardHeader>
              <div className="flex-1 flex flex-col justify-center">
                <EmptyState
                  icon={<AppointmentsIcon className="w-6 h-6" />}
                  title="No upcoming bookings"
                  description="Customer bookings and appointment slots coordinated by your AI agent will be displayed here."
                  actionText="Configure booking hours"
                />
              </div>
            </Card>
          )}
        </section>

        {/* Business Channels Readiness Overview */}
        <section className="p-6 rounded-xl border border-slate-800/80 bg-slate-900/30">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4 pb-4 border-b border-slate-800/60">
            <div>
              <h4 className="text-sm font-semibold text-white">Channel Integration Status</h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Multi-channel communication endpoints ready for business configuration
              </p>
            </div>
            <Badge variant="default" className="w-fit text-[11px]">
              Multi-Agent Architecture
            </Badge>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800/70 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center text-xs font-semibold">
                  WEB
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-200">Web Chat Widget</p>
                  <p className="text-[11px] text-slate-400">Ready to embed</p>
                </div>
              </div>
              <span className="w-2 h-2 rounded-full bg-slate-600" title="Standby" />
            </div>

            <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800/70 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center text-xs font-semibold">
                  WA
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-200">WhatsApp Cloud</p>
                  <p className="text-[11px] text-slate-400">Cloud API gateway</p>
                </div>
              </div>
              <span className="w-2 h-2 rounded-full bg-slate-600" title="Standby" />
            </div>

            <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800/70 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center text-xs font-semibold">
                  VOX
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-200">Voice Simulator</p>
                  <p className="text-[11px] text-slate-400">Browser audio pipeline</p>
                </div>
              </div>
              <span className="w-2 h-2 rounded-full bg-slate-600" title="Standby" />
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
