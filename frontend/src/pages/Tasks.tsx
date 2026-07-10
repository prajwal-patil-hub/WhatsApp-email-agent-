import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, isAuthenticated } from "../lib/api";

interface Task {
  id: string;
  title: string;
  priority: string;
  status: string;
  due_date: string | null;
  project: string | null;
}

const PRIORITY_COLORS: Record<string, string> = {
  urgent: "bg-red-500/20 text-red-400",
  high: "bg-orange-500/20 text-orange-400",
  medium: "bg-yellow-500/20 text-yellow-400",
  low: "bg-green-500/20 text-green-400",
};

const COLUMNS = [
  { key: "pending", label: "Pending" },
  { key: "in_progress", label: "In Progress" },
  { key: "completed", label: "Completed" },
];

export default function Tasks() {
  const qc = useQueryClient();
  const [newTitle, setNewTitle] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: async () => {
      const results = await Promise.all(
        COLUMNS.map((c) =>
          api.get(`/tasks?status=${c.key}&limit=50`).then((r) => r.data.items as Task[]),
        ),
      );
      return Object.fromEntries(COLUMNS.map((c, i) => [c.key, results[i]]));
    },
    enabled: isAuthenticated(),
  });

  const createTask = useMutation({
    mutationFn: (title: string) => api.post("/tasks", { title }),
    onSuccess: () => {
      setNewTitle("");
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  const completeTask = useMutation({
    mutationFn: (id: string) => api.post(`/tasks/${id}/complete`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const cancelTask = useMutation({
    mutationFn: (id: string) => api.delete(`/tasks/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });

  if (!isAuthenticated()) {
    return <NotConnected page="Tasks" />;
  }

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-white mb-1">Tasks</h2>
      <p className="text-gray-400 mb-6">Task board synced with your WhatsApp assistant.</p>

      <form
        className="flex gap-2 mb-6 max-w-xl"
        onSubmit={(e) => {
          e.preventDefault();
          if (newTitle.trim()) createTask.mutate(newTitle.trim());
        }}
      >
        <input
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          placeholder="Add a task..."
          className="flex-1 bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          disabled={createTask.isPending}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
        >
          <Plus className="w-4 h-4" /> Add
        </button>
      </form>

      {isLoading ? (
        <p className="text-gray-500">Loading tasks…</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {COLUMNS.map((col) => (
            <div key={col.key} className="bg-gray-900 rounded-xl border border-gray-800 p-4">
              <h3 className="text-sm font-semibold text-gray-300 mb-3">
                {col.label}{" "}
                <span className="text-gray-500">({data?.[col.key]?.length ?? 0})</span>
              </h3>
              <div className="space-y-2">
                {(data?.[col.key] ?? []).map((t) => (
                  <div key={t.id} className="bg-gray-800 rounded-lg p-3">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm text-white">{t.title}</p>
                      <span className={`text-xs px-2 py-0.5 rounded-full whitespace-nowrap ${PRIORITY_COLORS[t.priority] ?? ""}`}>
                        {t.priority}
                      </span>
                    </div>
                    {t.due_date && (
                      <p className="text-xs text-gray-400 mt-1">
                        Due {new Date(t.due_date).toLocaleDateString()}
                      </p>
                    )}
                    {col.key !== "completed" && (
                      <div className="flex gap-2 mt-2">
                        <button
                          onClick={() => completeTask.mutate(t.id)}
                          className="flex items-center gap-1 text-xs text-green-400 hover:text-green-300"
                        >
                          <CheckCircle2 className="w-3 h-3" /> Complete
                        </button>
                        <button
                          onClick={() => cancelTask.mutate(t.id)}
                          className="flex items-center gap-1 text-xs text-gray-500 hover:text-red-400"
                        >
                          <Trash2 className="w-3 h-3" /> Cancel
                        </button>
                      </div>
                    )}
                  </div>
                ))}
                {(data?.[col.key] ?? []).length === 0 && (
                  <p className="text-xs text-gray-600">Nothing here.</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function NotConnected({ page }: { page: string }) {
  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-white mb-2">{page}</h2>
      <p className="text-gray-400">
        Connect the dashboard first: go to <span className="text-indigo-400">Settings</span> and
        sign in with your phone number and admin secret.
      </p>
    </div>
  );
}
