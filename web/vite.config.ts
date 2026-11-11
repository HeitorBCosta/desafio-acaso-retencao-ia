import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento, /api vai para a API FastAPI local (uvicorn na porta 8000).
// Em produção, o mesmo caminho é atendido pelo nginx (docker compose) ou pelo CloudFront (AWS).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
