import { defineConfig, externalizeDepsPlugin } from "electron-vite"
import vue from "@vitejs/plugin-vue"
import { resolve } from "path"

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: { rollupOptions: { input: resolve(__dirname, "electron/main/index.ts") } },
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: { rollupOptions: { input: resolve(__dirname, "electron/preload/index.ts") } },
  },
  renderer: {
    root: resolve(__dirname, "src"),
    plugins: [vue()],
    build: { rollupOptions: { input: resolve(__dirname, "src/index.html") } },
  },
})
