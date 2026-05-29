import { useQuery } from "@tanstack/react-query";
import { Activity, BrainCircuit, CheckSquare, MessageSquare } from "lucide-react";
import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface HealthResponse {
  status: string;
  version: string;
  phase: number;
  uptime_seconds: number;
}

export default function Dashboard() {
  const { data: health, isLoading } = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: () => axios.get(`${API_URL}/api/v1/health`).then((r) => r.data),
    refetchInterval: 30_000,
  });

  const stats = [
    { label: "Status", value: isLoading ? "..." : health?.status ?? "unknown", icon: Activity, color: "text-green-400" },
    { label: "Phase", value: health?.phase ? `Phase ${health.phase}` : "—", icon: CheckSquare, color: "text-indigo-400" },
    { label: "Uptime", value: health ? formatUptime(health.uptime_seconds) : "—", icon: Activity, color: "text-blue-400" },
    { label: "Version", value: health?.version ?? "—", icon: BrainCircuit, color: "text-purple-400" },
  ];

  return (
    <div className="p-8">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">Dashboard</h2>
        <p className="text-gray-400 mt-1">Personal AI Chief of Staff — System Overview</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-gray-400">{label}</span>
              <Icon className={`w-4 h-4 ${color}`} />
            </div>
            <p className={`text-xl font-semibold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PhaseRoadmap />
        <QuickActions />
      </div>
    </div>
  );
}

function PhaseRoadmap() {
  const phases = [
    { n: 1, label: "Core WhatsApp Assistant", status: "active" },
    { n: 2, label: "Email Integration", status: "planned" },
    { n: 3, label: "Task Management", status: "planned" },
    { n: 4, label: "Knowledge Base + Calendar", status: "planned" },
    { n: 5, label: "Research Agent", status: "planned" },
    { n: 6, label: "Admin Dashboard", status: "planned" },
    { n: 7, label: "Advanced Automations", status: "planned" },
  ];

  return (
    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
      <h3 className="text-lg font-semibold text-white mb-4">Implementation Roadmap</h3>
      <div className="space-y-3">
        {phases.map(({ n, label, status }) => (
          <div key={n} className="flex items-center gap-3">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${
              status === "active" ? "bg-green-500 text-white" : "bg-gray-700 text-gray-400"
            }`}>
              {n}
            </div>
            <span className={`text-sm ${status === "active" ? "text-white font-medium" : "text-gray-400"}`}>
              {label}
            </span>
            {status === "active" && (
              <span className="ml-auto text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full">
                Active
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function QuickActions() {
  const actions = [
    { label: "View Conversations", icon: MessageSquare, desc: "Browse WhatsApp message history" },
    { label: "Browse Memory", icon: BrainCircuit, desc: "View stored long-term memories" },
    { label: "Manage Tasks", icon: CheckSquare, desc: "Coming in Phase 3" },
  ];

  return (
    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
      <h3 className="text-lg font-semibold text-white mb-4">Quick Actions</h3>
      <div className="space-y-3">
        {actions.map(({ label, icon: Icon, desc }) => (
          <button
            key={label}
            className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-gray-800 transition-colors text-left"
          >
            <div className="w-9 h-9 rounded-lg bg-indigo-600/20 flex items-center justify-center flex-shrink-0">
              <Icon className="w-4 h-4 text-indigo-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-white">{label}</p>
              <p className="text-xs text-gray-400">{desc}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}
