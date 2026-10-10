export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface Folder {
  id: string;
  name: string;
  description: string | null;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface Document {
  id: string;
  folder_id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: "processing" | "ready" | "failed";
  chunk_count: number | null;
  uploaded_at: string;
  updated_at: string;
}

export interface ChatSession {
  id: string;
  title: string | null;
  folder_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  created_at: string;
  is_error?: boolean;
  error_type?: string;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  snippet: string;
  similarity: number;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  folder_name: string;
  content: string;
  similarity: number;
  chunk_index: number;
  metadata: Record<string, unknown> | null;
}
