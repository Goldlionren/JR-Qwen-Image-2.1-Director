import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'web/dist', emptyOutDir: true,
    lib: { entry: 'frontend/main.ts', formats: ['es'], fileName: () => 'director.js', cssFileName: 'director' },
    rollupOptions: { external: ['/scripts/app.js'] },
  },
});
