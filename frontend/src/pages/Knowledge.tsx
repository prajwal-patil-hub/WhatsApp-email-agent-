import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Search, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { api, isAuthenticated } from "../lib/api";
import { NotConnected } from "./Tasks";

interface KnowledgeItem {
  id: string;
  title: string | null;
  source_type: string;
  status: string;
  chunk_count: number;
}

export default function Knowledge() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => api.get("/knowledge").then((r) => r.data.items as KnowledgeItem[]),
    enabled: isAuthenticated(),
  });

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.post("/knowledge/upload", form);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["knowledge"] }),
  });

  const ask = useMutation({
    mutationFn: (q: string) => api.post("/knowledge/ask", { question: q }).then((r) => r.data.answer as string),
    onSuccess: (a) => setAnswer(a),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/knowledge/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["knowledge"] }),
  });

  if (!isAuthenticated()) return <NotConnected page="Knowledge" />;

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-white mb-1">Knowledge Base</h2>
      <p className="text-gray-400 mb-6">RAG over your documents — PDF, DOCX, TXT, Markdown.</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-5xl">
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-300">Documents ({data?.length ?? 0})</h3>
            <button
              onClick={() => fileRef.current?.click()}
              disabled={upload.isPending}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-3 py-1.5 rounded-lg disabled:opacity-50"
            >
              <Upload className="w-3 h-3" /> {upload.isPending ? "Ingesting…" : "Upload"}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) upload.mutate(f);
                e.target.value = "";
              }}
            />
          </div>
          <div className="space-y-2">
            {(data ?? []).map((item) => (
              <div key={item.id} className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg p-3">
                <FileText className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">{item.title ?? "Untitled"}</p>
                  <p className="text-xs text-gray-500">
                    {item.source_type} · {item.chunk_count} chunks · {item.status}
                  </p>
                </div>
                <button onClick={() => remove.mutate(item.id)} className="text-gray-600 hover:text-red-400">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
            {(data ?? []).length === 0 && <p className="text-sm text-gray-600">No documents yet.</p>}
          </div>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-gray-300 mb-3">Ask your knowledge base</h3>
          <form
            className="flex gap-2 mb-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (question.trim()) ask.mutate(question.trim());
            }}
          >
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What does the handbook say about…"
              className="flex-1 bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={ask.isPending}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-4 py-2 rounded-lg disabled:opacity-50"
            >
              <Search className="w-4 h-4" />
            </button>
          </form>
          {ask.isPending && <p className="text-sm text-gray-500">Searching + synthesizing…</p>}
          {answer && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-sm text-gray-200 whitespace-pre-wrap">
              {answer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
