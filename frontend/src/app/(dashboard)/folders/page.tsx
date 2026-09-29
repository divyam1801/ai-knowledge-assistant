"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FolderIcon, PlusIcon } from "lucide-react";
import { api } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";
import type { Folder } from "@/types";

export default function FoldersPage() {
  const router = useRouter();
  const [folders, setFolders] = useState<Folder[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.folders.list().then((data) => {
      setFolders(data);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        Loading...
      </div>
    );
  }

  if (folders.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
        <FolderIcon className="h-12 w-12 text-muted-foreground/40" />
        <div>
          <h2 className="text-lg font-medium">No folders yet</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Create a folder to start organizing your knowledge base.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Your folders</h1>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {folders.map((folder) => (
          <button
            key={folder.id}
            onClick={() => router.push(`/folders/${folder.id}`)}
            className="text-left p-4 rounded-lg border border-border hover:border-ring hover:bg-accent/30 transition-colors"
          >
            <div className="flex items-center gap-3 mb-2">
              <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center">
                <FolderIcon className="h-4 w-4 text-primary" />
              </div>
            </div>
            <p className="font-medium text-sm">{folder.name}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {folder.document_count} docs · {formatRelativeTime(folder.updated_at)}
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}
