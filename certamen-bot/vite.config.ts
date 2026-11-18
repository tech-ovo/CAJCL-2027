import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';
import {defineConfig, type Plugin} from 'vite';

/* THE ARENA WEARS THE SITE'S CLOTHES, NOT A COPY OF THEM.
 *
 * The build lands in frontend/public/certamen/, one level below the site, so
 * `../tokens.css` and `../app.css` are the very files the convention pages
 * load. Linking them rather than bundling them means a commissioner who
 * re-skins tokens.css re-skins the arena too, with no rebuild.
 *
 * The tags are injected AFTER Vite has processed the HTML, so it never tries
 * to resolve or hash them. In dev the same paths are served straight out of
 * frontend/public by the middleware below. */
const SITE = path.resolve(__dirname, '../frontend/public');
const SITE_FILES = /^\/(tokens\.css|app\.css|fonts\/[\w.-]+\.woff2|img\/[\w.-]+)$/;

function siteStylesheets(): Plugin {
  return {
    name: 'cajcl-site-stylesheets',
    transformIndexHtml: {
      order: 'post',
      handler: () => [
        ...['literata-600', 'plex-sans-400', 'literata-400'].map((font) => ({
          tag: 'link',
          attrs: {rel: 'preload', href: `../fonts/${font}.woff2`, as: 'font', type: 'font/woff2', crossorigin: ''},
          injectTo: 'head-prepend' as const,
        })),
        {tag: 'link', attrs: {rel: 'icon', href: '../img/favicon.ico', sizes: '16x16 32x32 48x48'}, injectTo: 'head-prepend' as const},
        {tag: 'link', attrs: {rel: 'stylesheet', href: '../tokens.css'}, injectTo: 'head-prepend' as const},
        {tag: 'link', attrs: {rel: 'stylesheet', href: '../app.css'}, injectTo: 'head-prepend' as const},
      ],
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url || '').split('?')[0];
        const match = SITE_FILES.exec(url);
        if (!match) return next();
        const file = path.join(SITE, match[1]);
        if (!fs.existsSync(file)) return next();
        const type = file.endsWith('.css') ? 'text/css'
          : file.endsWith('.woff2') ? 'font/woff2'
          : file.endsWith('.ico') ? 'image/x-icon' : 'application/octet-stream';
        res.setHeader('Content-Type', type);
        fs.createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig(() => {
  return {
    base: './',
    plugins: [react(), siteStylesheets()],
    build: {
      outDir: path.resolve(__dirname, '../frontend/public/certamen'),
      emptyOutDir: true,
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      hmr: process.env.DISABLE_HMR !== 'true',
      // Disable file watching when DISABLE_HMR is true to save CPU during agent edits.
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
  };
});
