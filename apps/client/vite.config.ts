import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { existsSync } from 'node:fs';
for (const asset of ['retro_coop_d02.wasm', 'diagnostic.nes']) {
 if (!existsSync(new URL('./public/generated/' + asset, import.meta.url))) throw Error('Missing foundation assets: run sh scripts/foundation/prepare.sh');
}
export default defineConfig({ plugins: [react()], envPrefix: 'PUBLIC_', server: { strictPort: true }, preview: { strictPort: true } });
