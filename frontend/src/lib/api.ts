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

  const start = performance.now();
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  const elapsed = Math.round(performance.now() - start);
  console.log(`[API] ${options.method || "GET"} ${path} — ${response.status} ${elapsed}ms`);

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
    preview: (id: string) =>
      request<{ id: string; filename: string; file_type: string; content: string; truncated: boolean }>(
        `/api/documents/${id}/preview`,
      ),
    previewBlob: async (id: string): Promise<string> => {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const response = await fetch(`${API_BASE}/api/documents/${id}/preview`, { headers });
      if (!response.ok) throw new Error("Preview fetch failed");
      const blob = await response.blob();
      return URL.createObjectURL(blob);
    },
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
    updateSession: (id: string, data: { title?: string }) =>
      request<import("@/types").ChatSession>(`/api/chat/sessions/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
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

  summarize: {
    folder: (folderId: string) =>
      request<{ summary: string }>(`/api/summarize/folder/${folderId}`),
    document: (documentId: string) =>
      request<{ summary: string }>(`/api/summarize/document/${documentId}`),
    date: (date: string, folderId?: string) => {
      const params = folderId ? `?folder_id=${folderId}` : "";
      return request<{ summary: string }>(`/api/summarize/date/${date}${params}`);
    },
  },

  ephemeral: {
    upload: (file: File, question: string) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("question", question);
      return request<{ temp_id: string; answer: string; citations: import("@/types").Citation[] | null }>(
        "/api/chat/upload",
        { method: "POST", body: formData },
      );
    },
    save: (tempId: string, folderId: string) =>
      request<{ id: string; filename: string; status: string }>(
        "/api/chat/upload/save",
        { method: "POST", body: JSON.stringify({ temp_id: tempId, folder_id: folderId }) },
      ),
  },
};

export { ApiError };
