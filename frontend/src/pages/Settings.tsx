import { useMutation, useQuery } from "@tanstack/react-query";
import { LogOut, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { api, isAuthenticated, login, logout } from "../lib/api";

export default function Settings() {
  const [phone, setPhone] = useState("");
  const [secret, setSecret] = useState("");
  const [connected, setConnected] = useState(isAuthenticated());
  const [error, setError] = useState<string | null>(null);

  const doLogin = useMutation({
    mutationFn: () => login(phone.trim(), secret.trim()),
    onSuccess: () => {
      setConnected(true);
      setError(null);
    },
    onError: () => setError("Login failed — check phone number and admin secret."),
  });

  const { data: emailStatus } = useQuery({
    queryKey: ["email-status"],
    queryFn: () => api.get("/email/status").then((r) => r.data),
    enabled: connected,
  });

  const { data: calStatus } = useQuery({
    queryKey: ["calendar-status"],
    queryFn: () => api.get("/calendar/status").then((r) => r.data),
    enabled: connected,
  });

  return (
    <div className="p-8 max-w-2xl">
      <h2 className="text-2xl font-bold text-white mb-1">Settings</h2>
      <p className="text-gray-400 mb-6">Dashboard authentication and integrations.</p>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
        <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-indigo-400" /> Dashboard Access
        </h3>
        {connected ? (
          <div className="flex items-center justify-between">
            <p className="text-sm text-green-400">Connected ✓</p>
            <button
              onClick={() => {
                logout();
                setConnected(false);
              }}
              className="flex items-center gap-2 text-xs text-gray-400 hover:text-red-400"
            >
              <LogOut className="w-3 h-3" /> Disconnect
            </button>
          </div>
        ) : (
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              doLogin.mutate();
            }}
          >
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="Phone number (e.g. 14155551234)"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
            />
            <input
              type="password"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              placeholder="Admin secret (ADMIN_SECRET from .env)"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
            />
            {error && <p className="text-xs text-red-400">{error}</p>}
            <button
              type="submit"
              disabled={doLogin.isPending}
              className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
            >
              {doLogin.isPending ? "Connecting…" : "Connect"}
            </button>
          </form>
        )}
      </div>

      {connected && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Integrations</h3>
          <div className="space-y-3 text-sm">
            <IntegrationRow
              label="Email"
              connected={Boolean(emailStatus?.connected)}
              detail={emailStatus?.credentials?.map((c: { provider: string; email_address: string }) => `${c.provider}: ${c.email_address}`).join(", ")}
              connectHint="GET /api/v1/email/auth/gmail or /auth/outlook"
            />
            <IntegrationRow
              label="Google Calendar"
              connected={Boolean(calStatus?.connected)}
              detail={calStatus?.email_address}
              connectHint="GET /api/v1/calendar/auth/google"
            />
          </div>
        </div>
      )}
    </div>
  );
}

function IntegrationRow({
  label,
  connected,
  detail,
  connectHint,
}: {
  label: string;
  connected: boolean;
  detail?: string;
  connectHint: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="text-white">{label}</p>
        <p className="text-xs text-gray-500">{connected ? detail : `Connect via ${connectHint}`}</p>
      </div>
      <span
        className={`text-xs px-2 py-0.5 rounded-full ${
          connected ? "bg-green-500/20 text-green-400" : "bg-gray-700 text-gray-400"
        }`}
      >
        {connected ? "Connected" : "Not connected"}
      </span>
    </div>
  );
}
