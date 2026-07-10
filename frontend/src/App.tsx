import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import AuditLog from "./pages/AuditLog";
import Conversations from "./pages/Conversations";
import Dashboard from "./pages/Dashboard";
import Knowledge from "./pages/Knowledge";
import Memory from "./pages/Memory";
import Research from "./pages/Research";
import Settings from "./pages/Settings";
import Tasks from "./pages/Tasks";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 2, staleTime: 30_000 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="conversations" element={<Conversations />} />
            <Route path="tasks" element={<Tasks />} />
            <Route path="memory" element={<Memory />} />
            <Route path="knowledge" element={<Knowledge />} />
            <Route path="research" element={<Research />} />
            <Route path="audit" element={<AuditLog />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
