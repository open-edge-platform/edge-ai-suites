import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 3000,
    proxy: {
      '/stream': {
        target: 'http://ibvs-mediamtx:8888',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/stream/, '/stream'), // Optional path rewrite
      },
      '/search': {
        target: 'http://ibvs-featurematching:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/search/, '/search'), // Optional path rewrite
      },
      '/static/': {
        target: 'http://ibvs-featurematching:8000',
        changeOrigin: true
      },
      '/clear': {
        target: 'http://ibvs-featurematching:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/clear/, '/clear'), // Optional path rewrite
      },
      '/pipelines': {
        target: 'http://ibvs-dlstreamer-pipeline-server:8080',
        changeOrigin: true
      }
    },
  },
});
