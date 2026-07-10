import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, isAuthenticated } from "../lib/api";
import { NotConnected } from "./Tasks";

interface Memory {
  id: string;
  memory_type: string;
  content: string;
  summary: string | null;
  importance: number;
  created_at: string;
}

const TYPES = ["all", "fact", "goal", "preference", "project"];

export default function Memory() {
  const [typeFilter, setTypeFilter] = useState("all");

  const { data } = useQuery({
    queryKey: ["memories", typeFilter],
    queryFn: () => {
      const params = typeFilter === "all" ? "" : `&memory_type=${typeFilter}`;
      return api.get(`/memory?limit=100${params}`).then((r) => r.data.items as Memory[]);
    },
    enabled: isAuthenticated(),
  });

  if (!isAuthenticated()) return <NotConnected page="Memory" />;

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-white mb-1">Memory</h2>
      <p className="text-gray-400 mb-6">Long-term memories with semantic search over Qdrant.</p>

      <div className="flex gap-2 mb-6">
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={`text-xs px-3 py-1.5 rounded-full ${
              typeFilter === t ? "bg-indigo-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="space-y-3 max-w-3xl">
        {(data ?? []).map((m) => (
          <div key={m.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded-full">
                {m.memory_type}
              </span>
              <span className="text-xs text-gray-500">
                importance {m.importance.toFixed(1)} · {new Date(m.created_at).toLocaleDateString()}
              </span>
            </div>
            <p className="text-sm text-gray-200">{m.summary ?? m.content}</p>
          </div>
        ))}
        {(data ?? []).length === 0 && <p className="text-sm text-gray-600">No memories stored yet.</p>}
      </div>
    </div>
  );
}
