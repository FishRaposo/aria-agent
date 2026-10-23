import { spawn, execFileSync, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

export class LiveBackend {
  readonly root = path.resolve(process.cwd(), "..");
  readonly python = process.env.ARIA_TEST_PYTHON ?? path.join(this.root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  readonly port = process.env.ARIA_LIVE_API_PORT ?? "8100";
  readonly url = `http://127.0.0.1:${this.port}`;
  readonly directory: string;
  readonly database: string;
  readonly sandbox: string;
  private child: ChildProcess | null = null;
  constructor() {
    fs.mkdirSync(path.join(this.root, ".tmp"), { recursive: true });
    this.directory = fs.mkdtempSync(path.join(this.root, ".tmp", "live-e2e-"));
    this.database = path.join(this.directory, "app.db");
    this.sandbox = path.join(this.directory, "sandbox");
    fs.mkdirSync(this.sandbox);
    fs.writeFileSync(path.join(this.sandbox, "notes.txt"), "Synthetic local runbook. No credentials.\n");
    fs.writeFileSync(path.join(this.directory, "outside.txt"), "FORBIDDEN_OUTSIDE_SENTINEL");
  }
  private environment(timeout = 300): NodeJS.ProcessEnv {
    return { ...process.env, PYTHONUTF8: "1", DATABASE_URL: `sqlite:///${this.database.replaceAll("\\", "/")}`,
      AGENT_MODE: "approval_gated", ARIA_SAFETY_MODE: "block", AGENT_ROUTING: "keyword",
      ARIA_PLANNING_MODE: "single", APPROVAL_TIMEOUT_SECONDS: String(timeout), DB_PROBE_TIMEOUT: "1",
      CORS_ALLOWED_ORIGINS: `http://localhost:${process.env.ARIA_LIVE_FRONTEND_PORT ?? "3102"}`,
      ARIA_SANDBOX_DIR: this.sandbox, ARIA_SEARCH_API_URL: "", OPENAI_API_KEY: "", ANTHROPIC_API_KEY: "", GITHUB_TOKEN: "",
    };
  }
  async start(timeout = 300): Promise<void> {
    if (this.child) throw new Error("Test backend is already running");
    try { await fetch(`${this.url}/health`, { signal: AbortSignal.timeout(500) }); throw new Error(`Port ${this.port} is occupied; refusing to reuse another API`); }
    catch (error) { if (error instanceof Error && error.message.includes("occupied")) throw error; }
    const env = this.environment(timeout);
    const migration = execFileSync(this.python, ["-m", "alembic", "upgrade", "head"], { cwd: this.root, env, encoding: "utf8", windowsHide: true });
    fs.appendFileSync(path.join(this.directory, "migration.log"), migration);
    const child = spawn(this.python, ["-m", "uvicorn", "aria.main:app", "--app-dir", "src", "--host", "127.0.0.1", "--port", this.port], { cwd: this.root, env, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    this.child = child;
    let log = "";
    for (const stream of [child.stdout, child.stderr]) stream?.on("data", chunk => { const value = chunk.toString(); log = (log + value).slice(-12_000); fs.appendFileSync(path.join(this.directory, "api.log"), value); });
    const deadline = Date.now() + 45_000;
    while (Date.now() < deadline) {
      if (child.exitCode !== null) throw new Error(`Actual API exited ${child.exitCode}: ${log}`);
      if (log.includes("Application startup complete")) {
        try { const response = await fetch(`${this.url}/health`, { signal: AbortSignal.timeout(1500) }); if (response.ok) return; } catch { /* bounded readiness polling */ }
      }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    await this.stop(); throw new Error(`Actual API readiness timed out: ${log}`);
  }
  async stop(): Promise<void> {
    const child = this.child; this.child = null;
    if (!child || child.exitCode !== null) return;
    const exited = new Promise<void>(resolve => child.once("exit", () => resolve()));
    child.kill();
    await Promise.race([exited, new Promise<void>((_, reject) => setTimeout(() => reject(new Error("Owned API process did not stop")), 5000))]);
  }
  async restart(timeout = 300): Promise<void> { await this.stop(); await this.start(timeout); }
  sql(statement: string, parameters: unknown[] = []): unknown[][] {
    // Executes only against this fixture's own database, never the owner's app.
    return JSON.parse(execFileSync(this.python, ["-c", "import json,sqlite3,sys; c=sqlite3.connect(sys.argv[1]); rows=c.execute(sys.argv[2],json.loads(sys.argv[3])).fetchall(); c.commit(); print(json.dumps(rows)); c.close()", this.database, statement, JSON.stringify(parameters)], { cwd: this.root, encoding: "utf8", windowsHide: true }));
  }
}
