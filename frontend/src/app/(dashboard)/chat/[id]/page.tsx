"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useSearchParams } from "next/navigation";
import {
  SendIcon,
  LoaderIcon,
  FileTextIcon,
  FolderIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ChatMessage, ChatSession, Citation, Folder } from "@/types";

export default function ChatPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const paramId = params.id as string;
  const isNew = paramId === "new";
  const resetKey = searchParams.get("t") || "";
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const sessionIdRef = useRef<string | null>(isNew ? null : paramId);

  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamContent, setStreamContent] = useState("");
  const [streamCitations, setStreamCitations] = useState<Citation[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>("");
  const [expandedCitation, setExpandedCitation] = useState<string | null>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const streamingRef = useRef(false);

  useEffect(() => {
    if (isNew) {
      setSession(null);
      setMessages([]);
      setInput("");
      setStreaming(false);
      streamingRef.current = false;
      setStreamContent("");
      setStreamCitations([]);
      sessionIdRef.current = null;
      setExpandedCitation(null);
    }
  }, [resetKey]);

  useEffect(() => {
    async function load() {
      if (isNew) {
        const folderData = await api.folders.list();
        setFolders(folderData);
        return;
      }
      if (streamingRef.current) return;
      const [sessionData, folderData] = await Promise.all([
        api.chat.getSession(paramId),
        api.folders.list(),
      ]);
      setSession(sessionData);
      setMessages(sessionData.messages);
      setFolders(folderData);
      if (sessionData.folder_id) {
        setSelectedFolder(sessionData.folder_id);
      }
    }
    load();
  }, [paramId, isNew]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamContent, scrollToBottom]);

  async function handleSend() {
    const content = input.trim();
    if (!content || streaming) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      citations: null,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setStreaming(true);
    streamingRef.current = true;
    setStreamContent("");
    setStreamCitations([]);

    try {
      let activeSessionId = sessionIdRef.current;

      if (!activeSessionId) {
        const newSession = await api.chat.createSession({
          title: content.slice(0, 50).trim(),
          folder_id: selectedFolder || undefined,
        });
        activeSessionId = newSession.id;
        sessionIdRef.current = activeSessionId;
        setSession(newSession);
      }

      const streamStart = performance.now();
      const response = await api.chat.streamMessage(activeSessionId, {
        content,
        folder_id: selectedFolder || undefined,
      });
      console.log(`[CHAT] stream request sent — ${Math.round(performance.now() - streamStart)}ms`);

      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        const errMsg = errBody?.error?.message || errBody?.detail || "Stream failed";
        let errorType = "server_error";
        if (response.status === 429 || errBody?.error?.type === "rate_limit_error") {
          errorType = "gateway_rate_limit";
        } else if (response.status === 503) {
          errorType = "service_unavailable";
        }
        const error = new Error(
          errorType === "gateway_rate_limit"
            ? "Sorry for the inconvenience, you have hit the Gateway API rate limit. Please try again in a moment."
            : errorType === "service_unavailable"
              ? "The AI service is temporarily unavailable. Please try again later."
              : "Something went wrong. We are investigating the issue."
        );
        (error as any).errorType = errorType;
        throw error;
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";
      let citations: Citation[] = [];
      let firstTokenLogged = false;

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") continue;

              try {
                const parsed = JSON.parse(data);
                if (parsed.type === "token" && parsed.content) {
                  if (!firstTokenLogged) {
                    console.log(`[CHAT] first token — ${Math.round(performance.now() - streamStart)}ms`);
                    firstTokenLogged = true;
                  }
                  accumulated += parsed.content;
                  setStreamContent(accumulated);
                }
                if (parsed.type === "done" && parsed.citations) {
                  console.log(`[CHAT] stream complete — ${Math.round(performance.now() - streamStart)}ms`);
                  citations = parsed.citations;
                  setStreamCitations(citations);
                }
                if (parsed.type === "error") {
                  console.error(`[CHAT] stream error — ${parsed.error_type}: ${parsed.content}`);
                  const err = new Error(parsed.content || "Something went wrong");
                  (err as any).errorType = parsed.error_type;
                  throw err;
                }
              } catch (parseErr) {
                if (parseErr instanceof Error && (parseErr as any).errorType) throw parseErr;
              }
            }
          }
        }
      }

      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: accumulated,
        citations: citations.length > 0 ? citations : null,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorType = err instanceof Error ? (err as any).errorType : undefined;
      const errorContent = err instanceof Error ? err.message : "Something went wrong. We are investigating the issue.";
      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: errorContent,
        citations: null,
        created_at: new Date().toISOString(),
        is_error: true,
        error_type: errorType,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setStreaming(false);
      streamingRef.current = false;
      setStreamContent("");
      setStreamCitations([]);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border">
        <h1 className="text-sm font-medium truncate">
          {session?.title || "Chat"}
        </h1>
        <div className="flex items-center gap-2">
          <FolderIcon className="h-4 w-4 text-muted-foreground" />
          <select
            value={selectedFolder}
            onChange={(e) => setSelectedFolder(e.target.value)}
            className="text-xs border border-border rounded-md px-2 py-1 bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">All folders</option>
            {folders.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {messages.length === 0 && !streaming && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
              <SendIcon className="h-5 w-5 text-primary" />
            </div>
            <h2 className="text-lg font-medium">Ask anything</h2>
            <p className="text-sm text-muted-foreground mt-1 max-w-sm">
              Ask questions about your documents. Select a folder to scope the
              search, or search across all folders.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            expandedCitation={expandedCitation}
            onToggleCitation={setExpandedCitation}
          />
        ))}

        {streaming && streamContent && (
          <div className="flex gap-3">
            <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
              <span className="text-xs font-medium text-primary">AI</span>
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm markdown-content">
                <MarkdownContent content={streamContent} />
              </div>
              {streamCitations.length > 0 && (
                <CitationList
                  citations={streamCitations}
                  expandedCitation={expandedCitation}
                  onToggleCitation={setExpandedCitation}
                />
              )}
              <LoaderIcon className="h-3 w-3 animate-spin text-muted-foreground mt-2" />
            </div>
          </div>
        )}

        {streaming && !streamContent && (
          <div className="flex gap-3">
            <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
              <span className="text-xs font-medium text-primary">AI</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <LoaderIcon className="h-3 w-3 animate-spin" />
              Thinking...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border px-6 py-3">
        <div className="flex gap-2 max-w-3xl mx-auto">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Ask a question..."
            className="flex-1 resize-none px-3 py-2 text-sm rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
            style={{ maxHeight: 120 }}
            onInput={(e) => {
              const el = e.target as HTMLTextAreaElement;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
            }}
          />
          <button
            onClick={handleSend}
            disabled={streaming || !input.trim()}
            className="px-3 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            <SendIcon className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  expandedCitation,
  onToggleCitation,
}: {
  message: ChatMessage;
  expandedCitation: string | null;
  onToggleCitation: (id: string | null) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-primary text-primary-foreground px-4 py-2.5 rounded-2xl rounded-br-md">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  if (message.is_error) {
    return (
      <div className="flex gap-3">
        <div className="h-7 w-7 rounded-full bg-amber-500/10 flex items-center justify-center shrink-0 mt-0.5">
          <span className="text-xs font-medium text-amber-500">AI</span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-3 text-amber-700 dark:text-amber-300">
            {message.content}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
        <span className="text-xs font-medium text-primary">AI</span>
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm markdown-content">
          <MarkdownContent content={message.content} />
        </div>
        {message.citations && message.citations.length > 0 && (
          <CitationList
            citations={message.citations}
            expandedCitation={expandedCitation}
            onToggleCitation={onToggleCitation}
          />
        )}
      </div>
    </div>
  );
}

function MarkdownContent({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++;
      elements.push(
        <pre key={elements.length} className="overflow-x-auto">
          <code className={lang ? `language-${lang}` : ""}>
            {codeLines.join("\n")}
          </code>
        </pre>
      );
      continue;
    }

    if (line.startsWith("### ")) {
      elements.push(<h3 key={elements.length}>{formatInline(line.slice(4))}</h3>);
    } else if (line.startsWith("## ")) {
      elements.push(<h2 key={elements.length}>{formatInline(line.slice(3))}</h2>);
    } else if (line.startsWith("# ")) {
      elements.push(<h1 key={elements.length}>{formatInline(line.slice(2))}</h1>);
    } else if (/^\d+\.\s/.test(line)) {
      const items: string[] = [line.replace(/^\d+\.\s/, "")];
      while (i + 1 < lines.length && /^\d+\.\s/.test(lines[i + 1])) {
        i++;
        items.push(lines[i].replace(/^\d+\.\s/, ""));
      }
      elements.push(
        <ol key={elements.length}>
          {items.map((item, j) => (
            <li key={j}>{formatInline(item)}</li>
          ))}
        </ol>
      );
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      const items: string[] = [line.slice(2)];
      while (
        i + 1 < lines.length &&
        (lines[i + 1].startsWith("- ") || lines[i + 1].startsWith("* "))
      ) {
        i++;
        items.push(lines[i].slice(2));
      }
      elements.push(
        <ul key={elements.length}>
          {items.map((item, j) => (
            <li key={j}>{formatInline(item)}</li>
          ))}
        </ul>
      );
    } else if (line.trim() === "") {
      // skip blank lines
    } else {
      elements.push(<p key={elements.length}>{formatInline(line)}</p>);
    }
    i++;
  }

  return <>{elements}</>;
}

function formatInline(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const regex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const m = match[0];
    if (m.startsWith("`")) {
      parts.push(<code key={parts.length}>{m.slice(1, -1)}</code>);
    } else if (m.startsWith("**")) {
      parts.push(<strong key={parts.length}>{m.slice(2, -2)}</strong>);
    } else if (m.startsWith("*")) {
      parts.push(<em key={parts.length}>{m.slice(1, -1)}</em>);
    }
    lastIndex = match.index + m.length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts.length === 1 ? parts[0] : <>{parts}</>;
}

function CitationList({
  citations,
  expandedCitation,
  onToggleCitation,
}: {
  citations: Citation[];
  expandedCitation: string | null;
  onToggleCitation: (id: string | null) => void;
}) {
  return (
    <div className="mt-3 space-y-1.5">
      <p className="text-xs font-medium text-muted-foreground">Sources</p>
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c, i) => (
          <button
            key={`${c.chunk_id}-${i}`}
            onClick={() =>
              onToggleCitation(
                expandedCitation === c.chunk_id ? null : c.chunk_id,
              )
            }
            className={cn(
              "inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md border transition-colors",
              expandedCitation === c.chunk_id
                ? "border-ring bg-accent"
                : "border-border hover:bg-accent/50",
            )}
          >
            <FileTextIcon className="h-3 w-3" />
            <span className="truncate max-w-[120px]">
              {c.document_filename}
            </span>
            <span className="text-muted-foreground">
              {Math.round(c.similarity * 100)}%
            </span>
          </button>
        ))}
      </div>
      {expandedCitation && (
        <div className="mt-2">
          {citations
            .filter((c) => c.chunk_id === expandedCitation)
            .map((c) => (
              <div
                key={c.chunk_id}
                className="text-xs bg-muted/50 border border-border rounded-lg p-3"
              >
                <p className="font-medium mb-1 text-muted-foreground">
                  {c.document_filename}
                </p>
                <p className="whitespace-pre-wrap">{c.snippet}</p>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
