"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  FolderIcon,
  PlusIcon,
  MessageCircleIcon,
  FileTextIcon,
  LogOutIcon,
  BookOpenIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { removeToken } from "@/lib/auth";
import type { Folder, ChatSession } from "@/types";
import { cn } from "@/lib/utils";

export default function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const [folders, setFolders] = useState<Folder[]>([]);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [foldersOpen, setFoldersOpen] = useState(true);
  const [chatsOpen, setChatsOpen] = useState(true);
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");

  useEffect(() => {
    loadFolders();
    loadChats();
  }, []);

  async function loadFolders() {
    try {
      const data = await api.folders.list();
      setFolders(data);
    } catch {
      // will redirect to login if 401
    }
  }

  async function loadChats() {
    try {
      const data = await api.chat.listSessions();
      setChatSessions(data);
    } catch {
      // ignore
    }
  }

  async function handleCreateFolder() {
    if (!newFolderName.trim()) return;
    await api.folders.create({ name: newFolderName.trim() });
    setNewFolderName("");
    setShowNewFolder(false);
    loadFolders();
  }

  async function handleNewChat() {
    const session = await api.chat.createSession({ title: "New chat" });
    loadChats();
    router.push(`/chat/${session.id}`);
  }

  function handleLogout() {
    removeToken();
    router.push("/login");
  }

  return (
    <aside className="w-60 h-screen border-r border-border bg-muted/30 flex flex-col">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <BookOpenIcon className="h-5 w-5 text-primary" />
          <span className="font-semibold text-sm">Knowledge Assistant</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2">
        {/* Folders section */}
        <div className="mb-1">
          <button
            onClick={() => setFoldersOpen(!foldersOpen)}
            className="w-full flex items-center justify-between px-2 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider hover:text-foreground"
          >
            <span>Folders</span>
            {foldersOpen ? (
              <ChevronDownIcon className="h-3.5 w-3.5" />
            ) : (
              <ChevronRightIcon className="h-3.5 w-3.5" />
            )}
          </button>

          {foldersOpen && (
            <div className="space-y-0.5">
              {folders.map((folder) => (
                <button
                  key={folder.id}
                  onClick={() => router.push(`/folders/${folder.id}`)}
                  className={cn(
                    "w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors",
                    pathname === `/folders/${folder.id}`
                      ? "bg-accent text-accent-foreground font-medium"
                      : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                  )}
                >
                  <FolderIcon className="h-4 w-4 shrink-0" />
                  <span className="truncate">{folder.name}</span>
                  <span className="ml-auto text-xs opacity-60">
                    {folder.document_count}
                  </span>
                </button>
              ))}

              {showNewFolder ? (
                <div className="px-2 py-1">
                  <input
                    autoFocus
                    type="text"
                    placeholder="Folder name"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleCreateFolder();
                      if (e.key === "Escape") setShowNewFolder(false);
                    }}
                    onBlur={() => {
                      if (!newFolderName.trim()) setShowNewFolder(false);
                    }}
                    className="w-full px-2 py-1 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              ) : (
                <button
                  onClick={() => setShowNewFolder(true)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                >
                  <PlusIcon className="h-4 w-4" />
                  <span>Add folder</span>
                </button>
              )}
            </div>
          )}
        </div>

        {/* Chat section */}
        <div className="mt-4 mb-1">
          <button
            onClick={() => setChatsOpen(!chatsOpen)}
            className="w-full flex items-center justify-between px-2 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider hover:text-foreground"
          >
            <span>Chat</span>
            {chatsOpen ? (
              <ChevronDownIcon className="h-3.5 w-3.5" />
            ) : (
              <ChevronRightIcon className="h-3.5 w-3.5" />
            )}
          </button>

          {chatsOpen && (
            <div className="space-y-0.5">
              <button
                onClick={handleNewChat}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              >
                <PlusIcon className="h-4 w-4" />
                <span>New chat</span>
              </button>

              {chatSessions.slice(0, 10).map((session) => (
                <button
                  key={session.id}
                  onClick={() => router.push(`/chat/${session.id}`)}
                  className={cn(
                    "w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors",
                    pathname === `/chat/${session.id}`
                      ? "bg-accent text-accent-foreground font-medium"
                      : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                  )}
                >
                  <MessageCircleIcon className="h-4 w-4 shrink-0" />
                  <span className="truncate">
                    {session.title || "Untitled chat"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Notes section */}
        <div className="mt-4 mb-1">
          <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Quick notes
          </div>
          <button
            onClick={() => {
              setShowNewFolder(false);
              // navigate to a notes view or open an upload dialog
              const defaultFolder = folders[0];
              if (defaultFolder) {
                router.push(`/folders/${defaultFolder.id}`);
              }
            }}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-muted-foreground hover:bg-accent/50 hover:text-foreground"
          >
            <FileTextIcon className="h-4 w-4" />
            <span>Add notes</span>
          </button>
        </div>
      </div>

      {/* Bottom */}
      <div className="border-t border-border px-2 py-2">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-muted-foreground hover:bg-accent/50 hover:text-foreground"
        >
          <LogOutIcon className="h-4 w-4" />
          <span>Sign out</span>
        </button>
      </div>
    </aside>
  );
}
