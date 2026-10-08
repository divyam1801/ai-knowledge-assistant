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
  XIcon,
  EyeIcon,
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
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [previewContent, setPreviewContent] = useState<string>("");
  const [previewTruncated, setPreviewTruncated] = useState(false);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string>("");
  const [previewLoading, setPreviewLoading] = useState(false);

  const loadFolder = useCallback(async () => {
    const data = await api.folders.get(folderId);
    setFolder(data);
    setDocuments(data.documents);
    setLoading(false);
  }, [folderId]);

  useEffect(() => {
    loadFolder();
  }, [loadFolder]);

  useEffect(() => {
    const hasProcessing = documents.some((d) => d.status === "processing");
    if (!hasProcessing) return;
    const interval = setInterval(loadFolder, 3000);
    return () => clearInterval(interval);
  }, [documents, loadFolder]);

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

  async function handlePreview(doc: Document) {
    if (doc.status !== "ready") return;
    setPreviewDoc(doc);
    setPreviewContent("");
    setPreviewTruncated(false);
    if (previewBlobUrl) {
      URL.revokeObjectURL(previewBlobUrl);
      setPreviewBlobUrl("");
    }
    setPreviewLoading(true);
    try {
      if (doc.file_type === "image" || doc.file_type === "pdf") {
        const blobUrl = await api.documents.previewBlob(doc.id);
        setPreviewBlobUrl(blobUrl);
      } else {
        const data = await api.documents.preview(doc.id);
        setPreviewContent(data.content);
        setPreviewTruncated(data.truncated);
      }
    } catch {
      setPreviewContent("Failed to load preview.");
    } finally {
      setPreviewLoading(false);
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
    <div className="flex h-full overflow-hidden">
    <div className={cn("p-6 overflow-y-auto transition-all", previewDoc ? "w-1/2" : "w-full max-w-4xl")}>
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
                  onClick={() => handlePreview(doc)}
                  className={cn(
                    "flex items-center justify-between p-3 rounded-lg border border-border hover:bg-accent/30 transition-colors group",
                    doc.status === "ready" && "cursor-pointer",
                    previewDoc?.id === doc.id && "ring-2 ring-ring bg-accent/30",
                  )}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Icon className="h-5 w-5 shrink-0 text-muted-foreground" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {doc.filename}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatRelativeTime(doc.uploaded_at)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {doc.status === "ready" && (
                      <EyeIcon className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                    )}
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
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(doc.id);
                      }}
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

    {previewDoc && (
      <div className="w-1/2 border-l border-border flex flex-col h-full">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-medium truncate">{previewDoc.filename}</h2>
            <p className="text-xs text-muted-foreground">
              {formatBytes(previewDoc.file_size_bytes)} &middot; {previewDoc.chunk_count ?? 0} chunks
            </p>
          </div>
          <button
            onClick={() => {
              if (previewBlobUrl) URL.revokeObjectURL(previewBlobUrl);
              setPreviewBlobUrl("");
              setPreviewDoc(null);
            }}
            className="p-1 rounded hover:bg-accent transition-colors ml-2"
          >
            <XIcon className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {previewLoading ? (
            <div className="flex items-center justify-center h-32 text-muted-foreground">
              <LoaderIcon className="h-5 w-5 animate-spin mr-2" />
              Loading preview...
            </div>
          ) : previewDoc.file_type === "image" && previewBlobUrl ? (
            <img
              src={previewBlobUrl}
              alt={previewDoc.filename}
              className="max-w-full rounded-lg border border-border"
            />
          ) : previewDoc.file_type === "pdf" && previewBlobUrl ? (
            <iframe
              src={previewBlobUrl}
              title={previewDoc.filename}
              className="w-full h-full min-h-[500px] rounded-lg border border-border"
            />
          ) : (
            <div>
              <div className="text-sm whitespace-pre-wrap leading-relaxed text-foreground/90 font-mono bg-muted/30 rounded-lg p-4 border border-border">
                {previewContent || "No content available."}
              </div>
              {previewTruncated && (
                <p className="text-xs text-muted-foreground mt-2 text-center italic">
                  Preview truncated — showing first ~50,000 characters
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    )}
    </div>
  );
}
