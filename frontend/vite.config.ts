import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // VITE_* variables come from the root .env
  envDir: "..",
  server: { port: 5173, strictPort: true },
});
