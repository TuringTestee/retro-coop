import { defineConfig,loadEnv } from 'vite';
import {featuredPlugin} from './featured-plugin.ts';
import react from '@vitejs/plugin-react';
import { existsSync } from 'node:fs';
for (const asset of ['./src/generated/retro_coop_d02.wasm', './public/generated/diagnostic.nes']) {
 if (!existsSync(new URL(asset, import.meta.url))) throw Error('Missing foundation assets: run sh scripts/foundation/prepare.sh');
}
export default defineConfig(({mode})=>({ plugins: [react(),featuredPlugin(process.env.PUBLIC_FEATURED_GAME ?? loadEnv(mode,new URL('.',import.meta.url).pathname,'PUBLIC_').PUBLIC_FEATURED_GAME)], build: { license: { fileName: 'client-licenses.txt' } }, envPrefix: 'PUBLIC_', server: { strictPort: true }, preview: { strictPort: true } }));
