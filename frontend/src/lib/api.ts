import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = axios.create({ baseURL: `${API_URL}/api/v1` });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
    }
    return Promise.reject(error);
  },
);

export function isAuthenticated(): boolean {
  return Boolean(localStorage.getItem("access_token"));
}

export async function login(phoneNumber: string, adminSecret: string): Promise<void> {
  const { data } = await api.post("/auth/token", {
    phone_number: phoneNumber,
    admin_secret: adminSecret,
  });
  localStorage.setItem("access_token", data.access_token);
}

export function logout(): void {
  localStorage.removeItem("access_token");
}
