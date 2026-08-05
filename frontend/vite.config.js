import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
export default defineConfig({
    plugins: [react()],
    base: "/wot/",
    build: { outDir: "../backend/app/static", emptyOutDir: true },
    server: {
        proxy: {
            "/wot/api": {
                target: "http://localhost:8000",
                rewrite: function (path) { return path.replace(/^\/wot/, ""); },
            },
        },
    },
});
