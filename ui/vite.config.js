import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/ping": "http://localhost:8080",
      "/invocations": "http://localhost:8080",
      "/upload": "http://localhost:8080"
    }
  }
});
