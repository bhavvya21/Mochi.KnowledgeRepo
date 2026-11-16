import {readFileSync,writeFileSync,mkdirSync,readdirSync,cpSync} from 'node:fs';
import {resolve,relative,extname} from 'node:path';
import {build} from 'esbuild';
const root=process.cwd();const assets={};const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.png':'image/png'};
function walk(dir){for(const ent of readdirSync(dir,{withFileTypes:true})){const path=resolve(dir,ent.name);if(ent.isDirectory())walk(path);else assets['/'+relative(resolve(root,'build-client'),path).replaceAll('\\','/')]={type:types[extname(path)]||'application/octet-stream',body:readFileSync(path).toString('base64')};}}
walk(resolve(root,'build-client'));writeFileSync('worker/assets.generated.js','export default '+JSON.stringify(assets));mkdirSync('dist/server',{recursive:true});mkdirSync('dist/.openai',{recursive:true});
await build({entryPoints:['worker/index.js'],outfile:'dist/server/index.js',bundle:true,format:'esm',platform:'browser',target:'es2022',minify:true});
cpSync('.openai/hosting.json','dist/.openai/hosting.json');cpSync('drizzle','dist/.openai/drizzle',{recursive:true});
console.log('Built hosted Worker, assets, and database migrations.');
