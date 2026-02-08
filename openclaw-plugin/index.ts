/**
 * ThoughtVault Memory Plugin for OpenClaw
 * 
 * Provides memory_search and memory_get tools using local Ollama embeddings
 * via ThoughtVault's semantic search infrastructure.
 */

import { execSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { Type } from "@sinclair/typebox";

interface PluginConfig {
  thoughtvaultPath?: string;
  topK?: number;
}

interface SearchResult {
  file: string;
  line: number;
  score: number;
  text: string;
}

function resolvePath(p: string): string {
  if (p.startsWith("~/")) {
    return join(homedir(), p.slice(2));
  }
  return resolve(p);
}

const thoughtvaultMemoryPlugin = {
  id: "thoughtvault-memory",
  name: "ThoughtVault Memory",
  description: "Local semantic memory using ThoughtVault + Ollama embeddings",
  kind: "memory" as const,

  register(api: OpenClawPluginApi) {
    const cfg = (api.pluginConfig || {}) as PluginConfig;
    const tvPath = resolvePath(cfg.thoughtvaultPath || "~/thoughtvault");
    const defaultTopK = cfg.topK || 5;
    const searchScript = join(tvPath, "search.py");

    // Verify ThoughtVault exists
    if (!existsSync(searchScript)) {
      api.logger.warn(`thoughtvault-memory: search.py not found at ${searchScript}`);
      return;
    }

    api.logger.info(`thoughtvault-memory: initialized (path: ${tvPath})`);

    // Register memory_search tool
    api.registerTool(
      {
        name: "memory_search",
        label: "Memory Search",
        description:
          "Semantically search through memory files (MEMORY.md, memory/*.md) to find relevant past context, decisions, preferences, or facts. Use before answering questions about prior work or conversations.",
        parameters: Type.Object({
          query: Type.String({ description: "Search query - what you're looking for" }),
          maxResults: Type.Optional(Type.Number({ description: "Maximum results (default: 5)" })),
          minScore: Type.Optional(Type.Number({ description: "Minimum similarity score 0-1 (default: 0.3)" })),
        }),
        async execute(_toolCallId, params) {
          const { query, maxResults = defaultTopK, minScore = 0.3 } = params as {
            query: string;
            maxResults?: number;
            minScore?: number;
          };

          try {
            // Call ThoughtVault search
            const cmd = `cd "${tvPath}" && python3 search.py "${query.replace(/"/g, '\\"')}" --top ${maxResults} --json 2>/dev/null`;
            const output = execSync(cmd, { encoding: "utf-8", timeout: 30000 });
            
            let results: SearchResult[];
            try {
              results = JSON.parse(output);
            } catch {
              // Fallback: parse text output
              return {
                content: [{ type: "text", text: output || "No results found." }],
                details: { count: 0, raw: output },
              };
            }

            // Filter by minScore
            const filtered = results.filter((r) => r.score >= minScore);

            if (filtered.length === 0) {
              return {
                content: [{ type: "text", text: "No relevant memories found." }],
                details: { count: 0 },
              };
            }

            // Format results
            const formatted = filtered
              .map((r, i) => {
                const score = (r.score * 100).toFixed(0);
                return `${i + 1}. [${score}%] ${r.file}#${r.line}\n   ${r.text.slice(0, 200)}${r.text.length > 200 ? "..." : ""}`;
              })
              .join("\n\n");

            return {
              content: [
                {
                  type: "text",
                  text: `Found ${filtered.length} relevant memories:\n\n${formatted}`,
                },
              ],
              details: {
                count: filtered.length,
                results: filtered.map((r) => ({
                  path: r.file,
                  line: r.line,
                  score: r.score,
                  preview: r.text.slice(0, 100),
                })),
              },
            };
          } catch (err) {
            const msg = err instanceof Error ? err.message : String(err);
            api.logger.warn(`thoughtvault-memory: search failed: ${msg}`);
            return {
              content: [{ type: "text", text: `Memory search failed: ${msg}` }],
              details: { error: msg },
            };
          }
        },
      },
      { name: "memory_search" },
    );

    // Register memory_get tool
    api.registerTool(
      {
        name: "memory_get",
        label: "Memory Get",
        description:
          "Read a specific section from a memory file. Use after memory_search to get full context from a specific location.",
        parameters: Type.Object({
          path: Type.String({ description: "Path to memory file (e.g., MEMORY.md or memory/2026-02-07.md)" }),
          from: Type.Optional(Type.Number({ description: "Starting line number (1-indexed)" })),
          lines: Type.Optional(Type.Number({ description: "Number of lines to read (default: 20)" })),
        }),
        async execute(_toolCallId, params) {
          const { path: filePath, from = 1, lines = 20 } = params as {
            path: string;
            from?: number;
            lines?: number;
          };

          try {
            // Resolve path relative to workspace
            const workspacePath = process.env.OPENCLAW_WORKSPACE || join(homedir(), ".openclaw", "workspace");
            let fullPath: string;

            if (filePath.startsWith("/")) {
              fullPath = filePath;
            } else if (filePath.startsWith("~/")) {
              fullPath = resolvePath(filePath);
            } else {
              fullPath = join(workspacePath, filePath);
            }

            // Security: ensure path is within allowed directories
            const allowedPrefixes = [
              join(homedir(), ".openclaw"),
              workspacePath,
            ];
            const resolved = resolve(fullPath);
            const isAllowed = allowedPrefixes.some((prefix) => resolved.startsWith(prefix));
            
            if (!isAllowed) {
              return {
                content: [{ type: "text", text: `Access denied: ${filePath} is outside memory directories` }],
                details: { error: "access_denied" },
              };
            }

            if (!existsSync(resolved)) {
              return {
                content: [{ type: "text", text: `File not found: ${filePath}` }],
                details: { error: "not_found" },
              };
            }

            const content = readFileSync(resolved, "utf-8");
            const allLines = content.split("\n");
            const startIdx = Math.max(0, from - 1);
            const endIdx = Math.min(allLines.length, startIdx + lines);
            const slice = allLines.slice(startIdx, endIdx);

            return {
              content: [
                {
                  type: "text",
                  text: `${filePath} (lines ${startIdx + 1}-${endIdx}):\n\n${slice.join("\n")}`,
                },
              ],
              details: {
                path: filePath,
                from: startIdx + 1,
                to: endIdx,
                totalLines: allLines.length,
              },
            };
          } catch (err) {
            const msg = err instanceof Error ? err.message : String(err);
            return {
              content: [{ type: "text", text: `Failed to read file: ${msg}` }],
              details: { error: msg },
            };
          }
        },
      },
      { name: "memory_get" },
    );

    // Register CLI commands
    api.registerCli(
      ({ program }) => {
        const tv = program.command("thoughtvault").description("ThoughtVault memory commands");

        tv.command("search")
          .description("Search memories semantically")
          .argument("<query>", "Search query")
          .option("-n, --top <n>", "Number of results", "5")
          .action(async (query: string, opts: { top: string }) => {
            try {
              const cmd = `cd "${tvPath}" && python3 search.py "${query}" --top ${opts.top}`;
              const output = execSync(cmd, { encoding: "utf-8" });
              console.log(output);
            } catch (err) {
              console.error("Search failed:", err);
            }
          });

        tv.command("reindex")
          .description("Reindex memory files")
          .action(async () => {
            try {
              const cmd = `cd "${tvPath}" && python3 index.py`;
              const output = execSync(cmd, { encoding: "utf-8" });
              console.log(output);
            } catch (err) {
              console.error("Reindex failed:", err);
            }
          });

        tv.command("stats")
          .description("Show index statistics")
          .action(async () => {
            try {
              const dbPath = join(tvPath, "data", "thoughtvault.db");
              if (!existsSync(dbPath)) {
                console.log("No index found. Run 'openclaw thoughtvault reindex' first.");
                return;
              }
              const cmd = `sqlite3 "${dbPath}" "SELECT COUNT(*) as chunks, COUNT(DISTINCT file) as files FROM chunks"`;
              const output = execSync(cmd, { encoding: "utf-8" });
              console.log("Index stats:", output.trim());
            } catch (err) {
              console.error("Stats failed:", err);
            }
          });
      },
      { commands: ["thoughtvault"] },
    );

    // Register service
    api.registerService({
      id: "thoughtvault-memory",
      start: () => {
        api.logger.info(`thoughtvault-memory: service started`);
      },
      stop: () => {
        api.logger.info(`thoughtvault-memory: service stopped`);
      },
    });
  },
};

export default thoughtvaultMemoryPlugin;
