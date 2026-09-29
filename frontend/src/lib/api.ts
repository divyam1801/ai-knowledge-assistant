import { getToken } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.detail || "Request failed");
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  auth: {
    register: (data: { email: string; name: string; password: string }) =>
      request<{ id: string }>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    login: (data: { email: string; password: string }) =>
      request<{ access_token: string }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    me: () => request<import("@/types").User>("/api/auth/me"),
  },

  folders: {
    list: () => request<import("@/types").Folder[]>("/api/folders"),
    get: (id: string) =>
      request<import("@/types").Folder & { documents: import("@/types").Document[] }>(
        `/api/folders/${id}`,
      ),
    create: (data: { name: string; description?: string }) =>
      request<import("@/types").Folder>("/api/folders", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: string, data: { name?: string; description?: string }) =>
      request<import("@/types").Folder>(`/api/folders/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<void>(`/api/folders/${id}`, { method: "DELETE" }),
  },

  documents: {
    upload: (folderId: string, file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return request<import("@/types").Document>(
        `/api/folders/${folderId}/documents`,
        { method: "POST", body: formData },
      );
    },
    get: (id: string) =>
      request<import("@/types").Document>(`/api/documents/${id}`),
    status: (id: string) =>
      request<{ id: string; status: string; chunk_count: number | null }>(
        `/api/documents/${id}/status`,
      ),
    delete: (id: string) =>
      request<void>(`/api/documents/${id}`, { method: "DELETE" }),
  },

  chat: {
    createSession: (data: { title?: string; folder_id?: string }) =>
      request<import("@/types").ChatSession>("/api/chat/sessions", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    listSessions: () =>
      request<import("@/types").ChatSession[]>("/api/chat/sessions"),
    getSession: (id: string) =>
      request<
        import("@/types").ChatSession & { messages: import("@/types").ChatMessage[] }
      >(`/api/chat/sessions/${id}`),
    deleteSession: (id: string) =>
      request<void>(`/api/chat/sessions/${id}`, { method: "DELETE" }),
    sendMessage: (sessionId: string, data: { content: string; folder_id?: string }) =>
      request<import("@/types").ChatMessage>(
        `/api/chat/sessions/${sessionId}/messages`,
        { method: "POST", body: JSON.stringify(data) },
      ),
    streamMessage: (
      sessionId: string,
      data: { content: string; folder_id?: string },
    ) => {
      const token = getToken();
      return fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(data),
      });
    },
  },

  search: (data: { query: string; folder_id?: string; limit?: number }) =>
    request<{
      query: string;
      results: import("@/types").SearchResult[];
      total: number;
    }>("/api/search", { method: "POST", body: JSON.stringify(data) }),
};

export { ApiError };
