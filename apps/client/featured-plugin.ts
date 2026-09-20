import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import type {Plugin} from 'vite';
import {featuredGame,featuredAssetPath} from '../../packages/contracts/src/catalog.ts';

/** Verify once at startup and serve identical, content-addressed bytes in dev and builds. */
export function featuredPlugin(selection:string|undefined):Plugin {
 if(selection && selection!==featuredGame.id) throw Error('PUBLIC_FEATURED_GAME must be from-below-1.0 or empty');
 const bytes=selection ? readFileSync(new URL('./src/assets/from-below-1.0.nes',import.meta.url)) : undefined;
 if(bytes && (bytes.byteLength!==featuredGame.bytes || createHash('sha256').update(bytes).digest('hex')!==featuredGame.sha256)) throw Error('Included game differs from the approved artifact');
 return {
  name:'verified-featured-game',
  resolveId(id){if(id==='virtual:featured-game')return '\0virtual:featured-game';},
  load(id){if(id==='\0virtual:featured-game')return `export const featuredAvailable=${!!bytes};`;},
  generateBundle(){if(bytes)this.emitFile({type:'asset',fileName:featuredAssetPath.slice(1),source:bytes});},
  configureServer(server){server.middlewares.use((request,response,next)=>{
   if(!bytes || request.url!==featuredAssetPath)return next();
   if(request.method!=='GET' && request.method!=='HEAD'){response.writeHead(405).end();return;}
   response.setHeader('Content-Type','application/octet-stream');response.setHeader('Content-Length',bytes.length);
   response.setHeader('Cache-Control','public, max-age=31536000, immutable');response.end(request.method==='HEAD'?undefined:bytes);
  });},
 };
}
