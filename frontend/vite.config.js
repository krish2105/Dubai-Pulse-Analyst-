import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        // Proxy /api and direct backend routes to the FastAPI server in dev so the
        // frontend can call the backend without CORS friction.
        proxy: {
            "/health": "http://localhost:8000",
            "/insights": "http://localhost:8000",
            "/chat": "http://localhost:8000",
        },
    },
    build: {
        outDir: "dist",
        sourcemap: false,
    },
});
