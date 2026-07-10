import { useQuery } from "@tanstack/react-query";
import { Activity, BrainCircuit, CheckSquare, MessageSquare } from "lucide-react";
import { api, isAuthenticated } from "../lib/api";

interface HealthResponse {
  status: string;
  version: string;
  phase: number;
  uptime_seconds: number;
}

interface SystemHealth {
  postgres: string;
  redis: string;
  qdrant: string;
  ollama: string;
}

interface TaskAnalytics {
  pending: number;
  in_progress: number;
  completed: number;
  completed_last_7_days: number;
}

export default function Dashboard() {
  const authed = isAuthenticated();

  const { data: health, isLoading } = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: () => api.get("/health").then((r) => r.data),
    refetchInterval: 30_000,
  });

  const { data: sysHealth } = useQuery<SystemHealth>({
    queryKey: ["system-health"],
    queryFn: () => api.get("/admin/system/health").then((r) => r.data),
    enabled: authed,
    refetchInterval: 30_000,
  });

  const { data: taskStats } = useQuery<TaskAnalytics>({
    queryKey: ["task-analytics"],
    queryFn: () => api.get("/admin/analytics/tasks").then((r) => r.data),
    enabled: authed,
    refetchInterval: 60_000,
  });

  const stats = [
    { label: "API Status", value: isLoading ? "..." : health?.status ?? "unknown", icon: Activity, color: "text-green-400" },
    { label: "Tasks Pending", value: taskStats ? String(taskStats.pending) : "—", icon: CheckSquare, color: "text-yellow-400" },
    { label: "Done This Week", value: taskStats ? String(taskStats.completed_last_7_days) : "—", icon: CheckSquare, color: "text-green-400" },
    { label: "Uptime", value: health ? formatUptime(health.uptime_seconds) : "—", icon: BrainCircuit, color: "text-purple-400" },
  ];

  return (
    <div className="p-8">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">Dashboard</h2>
        <p className="text-gray-400 mt-1">Personal AI Chief of Staff — all 7 phases live</p>
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
        <ServiceHealth sysHealth={sysHealth} authed={authed} />
        <Capabilities />
      </div>
    </div>
  );
}

function ServiceHealth({ sysHealth, authed }: { sysHealth?: SystemHealth; authed: boolean }) {
  const services = [
    { key: "postgres", label: "PostgreSQL" },
    { key: "redis", label: "Redis" },
    { key: "qdrant", label: "Qdrant" },
    { key: "ollama", label: "Ollama" },
  ] as const;

  return (
    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
      <h3 className="text-lg font-semibold text-white mb-4">Service Health</h3>
      {!authed ? (
        <p className="text-sm text-gray-500">Sign in via Settings to see live service status.</p>
      ) : (
        <div className="space-y-3">
          {services.map(({ key, label }) => {
            const ok = sysHealth?.[key] === "ok";
            return (
              <div key={key} className="flex items-center justify-between">
                <span className="text-sm text-gray-300">{label}</span>
                <span className={`flex items-center gap-2 text-xs ${ok ? "text-green-400" : "text-red-400"}`}>
                  <span className={`w-2 h-2 rounded-full ${ok ? "bg-green-500" : "bg-red-500"}`} />
                  {sysHealth ? (ok ? "healthy" : "down") : "checking…"}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Capabilities() {
  const items = [
    { icon: MessageSquare, label: "WhatsApp text + voice", desc: "Whisper STT in, Edge TTS voice replies out" },
    { icon: MessageSquare, label: "Email (Gmail + Outlook)", desc: "Read, draft, send from chat" },
    { icon: CheckSquare, label: "Tasks + Calendar", desc: "NL commands, recurrence, reminders, conflict checks" },
    { icon: BrainCircuit, label: "Knowledge + Research", desc: "RAG over your docs, cited web research reports" },
    { icon: Activity, label: "Automations", desc: "Morning briefing, meeting prep, weekly review, overdue nudges" },
  ];

  return (
    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
      <h3 className="text-lg font-semibold text-white mb-4">Live Capabilities</h3>
      <div className="space-y-3">
        {items.map(({ icon: Icon, label, desc }) => (
          <div key={label} className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-600/20 flex items-center justify-center flex-shrink-0">
              <Icon className="w-4 h-4 text-indigo-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-white">{label}</p>
              <p className="text-xs text-gray-400">{desc}</p>
            </div>
          </div>
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
