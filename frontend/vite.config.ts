import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { execSync } from "node:child_process";

function safeGitShortSha(): string {
  try {
    return execSync("git rev-parse --short HEAD", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
  } catch {
    return "unknown";
  }
}

const buildTime = new Date().toISOString();
const gitSha = safeGitShortSha();
const projectName = "XHS_ALL_IN_ONE";

export default defineConfig({
  base: process.env.VITE_APP_BASE || "/",
  plugins: [react()],
  envPrefix: ["VITE_"],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes) => {
            if (proxyRes.headers["content-type"]?.includes("text/event-stream")) {
              proxyRes.headers["cache-control"] = "no-cache";
              proxyRes.headers["x-accel-buffering"] = "no";
            }
          });
        },
      },
    },
  },
  define: {
    "import.meta.env.VITE_BUILD_SHA": JSON.stringify(gitSha),
    "import.meta.env.VITE_BUILD_TIME": JSON.stringify(buildTime),
    "import.meta.env.VITE_PROJECT_NAME": JSON.stringify(projectName),
  },
});
