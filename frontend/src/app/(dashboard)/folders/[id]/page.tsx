"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  UploadIcon,
  FileTextIcon,
  FileIcon,
  ImageIcon,
  TrashIcon,
  CheckCircleIcon,
  LoaderIcon,
  AlertCircleIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn, formatBytes, formatRelativeTime } from "@/lib/utils";
import type { Document, Folder } from "@/types";

const FILE_TYPE_ICONS: Record<string, typeof FileTextIcon> = {
  txt: FileTextIcon,
  md: FileTextIcon,
  pdf: FileIcon,
  image: ImageIcon,
};

const STATUS_CONFIG = {
  ready: {
    icon: CheckCircleIcon,
    label: "Ready",
    className: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-400",
  },
  processing: {
    icon: LoaderIcon,
    label: "Processing",
    className: "bg-yellow-50 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-400",
  },
  failed: {
    icon: AlertCircleIcon,
    label: "Failed",
    className: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-400",
  },
};

export default function FolderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const folderId = params.id as string;
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [folder, setFolder] = useState<Folder | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const loadFolder = useCallback(async () => {
    const data = await api.folders.get(folderId);
    setFolder(data);
    setDocuments(data.documents);
    setLoading(false);
  }, [folderId]);

  useEffect(() => {
    loadFolder();
  }, [loadFolder]);

  async function handleUpload(files: FileList | File[]) {
    setUploading(true);
    for (const file of Array.from(files)) {
      await api.documents.upload(folderId, file);
    }
    setUploading(false);
    loadFolder();
  }

  async function handleDelete(docId: string) {
    await api.documents.delete(docId);
    loadFolder();
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length) {
      handleUpload(e.dataTransfer.files);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        Loading...
      </div>
    );
  }

  if (!folder) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        Folder not found
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">{folder.name}</h1>
          {folder.description && (
            <p className="text-sm text-muted-foreground mt-1">
              {folder.description}
            </p>
          )}
          <p className="text-xs text-muted-foreground mt-1">
            {documents.length} documents
          </p>
        </div>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg border border-border hover:bg-accent transition-colors disabled:opacity-50"
        >
          {uploading ? (
            <LoaderIcon className="h-4 w-4 animate-spin" />
          ) : (
            <UploadIcon className="h-4 w-4" />
          )}
          Upload
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".txt,.md,.pdf,.png,.jpg,.jpeg,.webp"
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) handleUpload(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={cn(
          "transition-colors",
          dragOver && "ring-2 ring-ring ring-offset-2 rounded-lg",
        )}
      >
        {documents.length === 0 ? (
          <div className="border-2 border-dashed border-border rounded-lg p-12 text-center">
            <UploadIcon className="h-8 w-8 mx-auto text-muted-foreground/40 mb-3" />
            <p className="text-sm font-medium">Drop files here or click upload</p>
            <p className="text-xs text-muted-foreground mt-1">
              Supports TXT, MD, PDF, and images
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {documents.map((doc) => {
              const Icon = FILE_TYPE_ICONS[doc.file_type] || FileIcon;
              const status = STATUS_CONFIG[doc.status];
              const StatusIcon = status.icon;

              return (
                <div
                  key={doc.id}
                  className="flex items-center justify-between p-3 rounded-lg border border-border hover:bg-accent/30 transition-colors group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Icon className="h-5 w-5 shrink-0 text-muted-foreground" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {doc.filename}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatBytes(doc.file_size_bytes)}
                        {doc.chunk_count !== null && ` · ${doc.chunk_count} chunks`}
                        {" · "}
                        {formatRelativeTime(doc.uploaded_at)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full",
                        status.className,
                      )}
                    >
                      <StatusIcon
                        className={cn(
                          "h-3 w-3",
                          doc.status === "processing" && "animate-spin",
                        )}
                      />
                      {status.label}
                    </span>
                    <button
                      onClick={() => handleDelete(doc.id)}
                      className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}

            {/* Drop hint at bottom */}
            <div className="border border-dashed border-border rounded-lg p-4 text-center text-xs text-muted-foreground">
              Drop files here to upload
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
