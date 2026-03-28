import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === "serve" ? "/" : "/static/web/",
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:5000",
      "/auth": "http://127.0.0.1:5000",
      "/app": "http://127.0.0.1:5000",
      "/studio": "http://127.0.0.1:5000",
      "/channels": "http://127.0.0.1:5000",
      "/settings": "http://127.0.0.1:5000",
      "/diagnostics": "http://127.0.0.1:5000",
      "/oauth": "http://127.0.0.1:5000",
      "/static": "http://127.0.0.1:5000",
    },
  },
  build: {
    outDir: path.resolve(rootDir, "../static/web"),
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: path.resolve(rootDir, "index.html"),
      output: {
        entryFileNames: "assets/app.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
}));
