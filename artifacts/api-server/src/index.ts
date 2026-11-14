// Keep the managed artifact's Node launch contract; all REST requests run in FastAPI.
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../../..", import.meta.url));
const child = spawn("uv", [
  "run", "--project", root, "uvicorn", "backend.main:app",
  "--app-dir", path.join(root, "artifacts/api-server"),
  "--host", "0.0.0.0", "--port", process.env.PORT || "8080",
  "--proxy-headers", "--forwarded-allow-ips", "*",
], { stdio: "inherit", env: process.env });
for (const signal of ["SIGTERM", "SIGINT"] as const) {
  process.on(signal, () => child.kill(signal));
}
child.on("exit", (code) => process.exit(code ?? 1));
child.on("error", () => process.exit(1));
