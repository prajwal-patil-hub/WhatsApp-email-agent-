import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { api, isAuthenticated } from "../lib/api";
import { NotConnected } from "./Tasks";

interface Report {
  id: string;
  title: string | null;
  status: string;
}

export default function Research() {
  const qc = useQueryClient();
  const [question, setQuestion] = useState("");
  const [report, setReport] = useState<string | null>(null);

  const { data: reports } = useQuery({
    queryKey: ["research-reports"],
    queryFn: () => api.get("/research/reports").then((r) => r.data.items as Report[]),
    enabled: isAuthenticated(),
  });

  const run = useMutation({
    mutationFn: (q: string) => api.post("/research", { question: q }).then((r) => r.data.report as string),
    onSuccess: (r) => {
      setReport(r);
      qc.invalidateQueries({ queryKey: ["research-reports"] });
    },
  });

  if (!isAuthenticated()) return <NotConnected page="Research" />;

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-white mb-1">Research</h2>
      <p className="text-gray-400 mb-6">
        Web search → multi-source synthesis → cited executive report. Reports are saved to your knowledge base.
      </p>

      <form
        className="flex gap-2 mb-6 max-w-2xl"
        onSubmit={(e) => {
          e.preventDefault();
          if (question.trim()) run.mutate(question.trim());
        }}
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Research a topic, e.g. 'Compare local LLM runtimes'"
          className="flex-1 bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          disabled={run.isPending}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
        >
          <Search className="w-4 h-4" /> {run.isPending ? "Researching…" : "Research"}
        </button>
      </form>

      {run.isPending && (
        <p className="text-sm text-gray-500 mb-6">Searching the web, reading sources, synthesizing… this can take a minute with local models.</p>
      )}

      {report && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-sm text-gray-200 whitespace-pre-wrap max-w-3xl mb-8">
          {report}
        </div>
      )}

      <h3 className="text-sm font-semibold text-gray-300 mb-3">Past reports ({reports?.length ?? 0})</h3>
      <div className="space-y-2 max-w-2xl">
        {(reports ?? []).map((r) => (
          <div key={r.id} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <p className="text-sm text-white">{r.title ?? "Untitled report"}</p>
            <p className="text-xs text-gray-500">{r.status} · searchable via Knowledge</p>
          </div>
        ))}
        {(reports ?? []).length === 0 && <p className="text-sm text-gray-600">No reports yet.</p>}
      </div>
    </div>
  );
}
