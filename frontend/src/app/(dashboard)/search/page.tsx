"use client";

import { useState, useEffect } from "react";
import { SearchIcon, FileTextIcon, FolderIcon } from "lucide-react";
import { api } from "@/lib/api";
import type { Folder, SearchResult } from "@/types";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [selectedFolder, setSelectedFolder] = useState("");
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    api.folders.list().then(setFolders).catch(() => {});
  }, []);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    setSearching(true);
    setSearched(true);

    try {
      const data = await api.search({
        query: query.trim(),
        folder_id: selectedFolder || undefined,
        limit: 20,
      });
      setResults(data.results);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="p-6 max-w-3xl">
      <h1 className="text-xl font-semibold mb-4">Search</h1>

      <form onSubmit={handleSearch} className="flex gap-2 mb-6">
        <div className="flex-1 relative">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your knowledge base..."
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <select
          value={selectedFolder}
          onChange={(e) => setSelectedFolder(e.target.value)}
          className="text-sm border border-border rounded-lg px-3 py-2 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
        >
          <option value="">All folders</option>
          {folders.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={searching || !query.trim()}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {searching ? "Searching..." : "Search"}
        </button>
      </form>

      {searched && results.length === 0 && !searching && (
        <div className="text-center text-muted-foreground py-12">
          <SearchIcon className="h-8 w-8 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No results found</p>
        </div>
      )}

      <div className="space-y-3">
        {results.map((result, i) => (
          <div
            key={`${result.chunk_id}-${i}`}
            className="p-4 rounded-lg border border-border hover:bg-accent/30 transition-colors"
          >
            <div className="flex items-center gap-2 mb-2">
              <FileTextIcon className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">
                {result.document_filename}
              </span>
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <FolderIcon className="h-3 w-3" />
                {result.folder_name}
              </span>
              <span className="ml-auto text-xs text-muted-foreground">
                {Math.round(result.similarity * 100)}% match
              </span>
            </div>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap line-clamp-3">
              {result.content}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
