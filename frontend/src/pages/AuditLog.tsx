import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, isAuthenticated } from "../lib/api";
import { NotConnected } from "./Tasks";

interface AuditEntry {
  id: string;
  action: string;
  resource_type: string | null;
  status: string;
  created_at: string;
}

const FILTERS = ["all", "email", "task", "calendar", "knowledge", "research", "auth", "coordinator"];

export default function AuditLog() {
  const [filter, setFilter] = useState("all");

  const { data } = useQuery({
    queryKey: ["audit", filter],
    queryFn: () => {
      const params = filter === "all" ? "" : `&action=${filter}`;
      return api.get(`/admin/audit?limit=100${params}`).then((r) => r.data.items as AuditEntry[]);
    },
    enabled: isAuthenticated(),
    refetchInterval: 30_000,
  });

  if (!isAuthenticated()) return <NotConnected page="Audit Log" />;

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-white mb-1">Audit Log</h2>
      <p className="text-gray-400 mb-6">Append-only trail of every agent action.</p>

      <div className="flex gap-2 mb-6 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs px-3 py-1.5 rounded-full ${
              filter === f ? "bg-indigo-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden max-w-4xl">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b border-gray-800">
              <th className="px-4 py-3">Action</th>
              <th className="px-4 py-3">Resource</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Time</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((a) => (
              <tr key={a.id} className="border-b border-gray-800/50">
                <td className="px-4 py-2.5 text-gray-200 font-mono text-xs">{a.action}</td>
                <td className="px-4 py-2.5 text-gray-400 text-xs">{a.resource_type ?? "—"}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      a.status === "success" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
                    }`}
                  >
                    {a.status}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-gray-500 text-xs">
                  {new Date(a.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {(data ?? []).length === 0 && (
          <p className="text-sm text-gray-600 p-4">No audit entries match this filter.</p>
        )}
      </div>
    </div>
  );
}
