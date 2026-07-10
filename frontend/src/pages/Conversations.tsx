import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, isAuthenticated } from "../lib/api";
import { NotConnected } from "./Tasks";

interface Conversation {
  id: string;
  channel: string;
  status: string;
  title: string | null;
  created_at: string;
}

interface Message {
  id: string;
  role: string;
  content: string;
  message_type: string;
  created_at: string;
}

export default function Conversations() {
  const [selected, setSelected] = useState<string | null>(null);

  const { data: conversations } = useQuery({
    queryKey: ["conversations"],
    queryFn: () =>
      api.get("/messages/conversations?limit=50").then((r) => r.data.items as Conversation[]),
    enabled: isAuthenticated(),
  });

  const { data: messages } = useQuery({
    queryKey: ["messages", selected],
    queryFn: () =>
      api.get(`/messages/conversations/${selected}?limit=100`).then((r) => r.data.items as Message[]),
    enabled: isAuthenticated() && Boolean(selected),
  });

  if (!isAuthenticated()) return <NotConnected page="Conversations" />;

  return (
    <div className="flex h-full">
      <div className="w-80 border-r border-gray-800 overflow-y-auto p-4">
        <h2 className="text-lg font-bold text-white mb-4">Conversations</h2>
        {(conversations ?? []).map((c) => (
          <button
            key={c.id}
            onClick={() => setSelected(c.id)}
            className={`w-full text-left p-3 rounded-lg mb-2 text-sm ${
              selected === c.id ? "bg-indigo-600/30 text-white" : "text-gray-300 hover:bg-gray-800"
            }`}
          >
            <p className="font-medium truncate">{c.title ?? "WhatsApp chat"}</p>
            <p className="text-xs text-gray-500">
              {c.channel} · {new Date(c.created_at).toLocaleDateString()}
            </p>
          </button>
        ))}
        {(conversations ?? []).length === 0 && (
          <p className="text-sm text-gray-600">No conversations yet.</p>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        {!selected ? (
          <p className="text-gray-500 mt-8 text-center">Select a conversation to view messages.</p>
        ) : (
          <div className="space-y-3 max-w-3xl mx-auto">
            {(messages ?? []).map((m) => (
              <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap ${
                    m.role === "user"
                      ? "bg-indigo-600 text-white rounded-br-sm"
                      : "bg-gray-800 text-gray-100 rounded-bl-sm"
                  }`}
                >
                  {m.message_type === "voice" && <span className="text-xs opacity-70">🎤 voice · </span>}
                  {m.content}
                  <p className="text-[10px] opacity-50 mt-1">
                    {new Date(m.created_at).toLocaleTimeString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
