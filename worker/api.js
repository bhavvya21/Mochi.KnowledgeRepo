import {documents as samples} from '../src/data.js';
import {retrieve} from '../src/retrieval.js';
export class HttpError extends Error {constructor(status,message){super(message);this.status=status;}}
const fail=(status,message)=>{throw new HttpError(status,message)};
const cookieName='__Host-mochi_session',sessionSeconds=90*24*60*60;
const hex=bytes=>Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
async function digest(token){return hex(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token))));}
export async function identity(request,env){
 const token=request.headers.get('cookie')?.split(';').map(x=>x.trim()).find(x=>x.startsWith(cookieName+'='))?.slice(cookieName.length+1);
 if(token&&/^[a-f0-9]{64}$/.test(token)&&env.DB){const session=await env.DB.prepare('SELECT owner, expires FROM browser_sessions WHERE token_hash = ? AND expires > ?').bind(await digest(token),Date.now()).first();if(session)return {id:session.owner,kind:'browser',label:'Private browser workspace',expires:session.expires};}
 const id=request.headers.get('oai-authenticated-user-id'),email=request.headers.get('oai-authenticated-user-email');return id&&email?{id,email,kind:'account',label:email}:null;
}
async function startSession(env){storage(env);const token=hex(crypto.getRandomValues(new Uint8Array(32))),owner='browser:'+crypto.randomUUID(),expires=Date.now()+sessionSeconds*1000;await env.DB.prepare('INSERT INTO browser_sessions (token_hash,owner,expires) VALUES (?,?,?)').bind(await digest(token),owner,expires).run();return {user:{id:owner,kind:'browser',label:'Private browser workspace',expires},cookie:`${cookieName}=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${sessionSeconds}`};}
const json=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Vary':'Cookie'}});
export function validateDocument(input){
 if(!input||typeof input!=='object')fail(400,'Invalid document.');
 const name=typeof input.name==='string'?input.name.trim():'';
 if(!name||name.length>240)fail(400,'Document name must contain 1–240 characters.');
 const types=['PDF','XLSX','CSV','TXT','MD','JSON','IMAGE'];if(!types.includes(input.type))fail(400,'Unsupported document type.');
 if(!Array.isArray(input.pages)||!input.pages.length||input.pages.length>150)fail(400,'Provide 1–150 source pages.');
 let chars=0;const seen=new Set();const pages=input.pages.map(p=>{if(!p||!Number.isInteger(p.page)||p.page<1||p.page>10000||seen.has(p.page)||typeof p.text!=='string'||!p.text.trim())fail(400,'Pages must have unique positive page numbers and nonempty text.');seen.add(p.page);chars+=p.text.length;return {page:p.page,topic:String(p.topic||name).slice(0,300),text:p.text};}).sort((a,b)=>a.page-b.page);
 if(chars>100000)fail(413,'This version supports up to 100,000 extracted characters per document.');
 return {name,type:input.type,collection:typeof input.collection==='string'&&input.collection.trim()?input.collection.trim().slice(0,80):'My uploads',pages,chars,size:Number.isFinite(input.size)?Math.max(0,Math.round(input.size)):0};
}
async function body(request,maxBytes=700000){
 if(!request.headers.get('content-type')?.startsWith('application/json'))fail(415,'Send application/json.');
 if(Number(request.headers.get('content-length'))>maxBytes)fail(413,'Request is too large.');
 if(!request.body)fail(400,'Request body is required.');let size=0;const reader=request.body.getReader(),parts=[];
 for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>maxBytes){await reader.cancel();fail(413,'Request is too large.')}parts.push(value);}
 const bytes=new Uint8Array(size);let offset=0;for(const part of parts){bytes.set(part,offset);offset+=part.length;}try{return JSON.parse(new TextDecoder().decode(bytes))}catch{fail(400,'Invalid JSON.');}
}
function storage(env){if(!env.DB||!env.BUCKET)fail(503,'Document storage is not configured. Please try again later.');}
async function rows(env,owner){const {results}=await env.DB.prepare('SELECT * FROM documents WHERE owner = ? ORDER BY created DESC').bind(owner).all();return results;}
async function loadDocument(env,row){const object=await env.BUCKET.get(row.object_key);if(!object)fail(503,'A saved document is temporarily unavailable.');const doc=await object.json();return {...doc,id:row.id,uploaded:true,cloud:true,updated:row.created};}
async function loadOwned(env,owner){const found=await rows(env,owner);let docs=[];for(let i=0;i<found.length;i+=5)docs.push(...await Promise.all(found.slice(i,i+5).map(row=>loadDocument(env,row))));return docs;}
function options(input){return {mode:['hybrid','bm25','tfidf'].includes(input.mode)?input.mode:'hybrid',strategy:['structure','fixed','sentence'].includes(input.strategy)?input.strategy:'structure',limit:5};}
export async function handleApi(request,env){try{
 const url=new URL(request.url),path=url.pathname;let user=await identity(request,env);
 if(!['GET','POST','DELETE'].includes(request.method))fail(405,'Method not allowed.');
 if(request.method!=='GET'){
 const origin=request.headers.get('origin');if(!origin||origin!==url.origin||request.headers.get('sec-fetch-site')==='cross-site')fail(403,'Cross-origin writes are not allowed.');
 }
 if(path==='/api/session'&&request.method==='GET'){
 if(request.headers.get('sec-fetch-site')==='cross-site')fail(403,'Open Mochi directly to initialize your workspace.');
 let cookie;if(!user){const created=await startSession(env);user=created.user;cookie=created.cookie;}
 const response=json({user:{email:user.email,label:user.label,kind:user.kind,expiresAt:user.expires||null},storage:!!(env.DB&&env.BUCKET),answerMode:'extractive',limits:{documents:50,charactersPerDocument:100000,totalCharacters:1000000}});if(cookie)response.headers.set('Set-Cookie',cookie);return response;
 }
 if(path==='/api/health'&&request.method==='GET')return json({status:'ok',version:2,answerMode:'extractive'});
 if(path==='/api/query'&&request.method==='POST'){
 const input=await body(request,12000);if(typeof input.question!=='string'||!input.question.trim()||input.question.length>2000)fail(400,'Enter a question of 1–2,000 characters.');
 const scope=input.scope||'uploads';if(!['uploads','samples'].includes(scope))fail(400,'Select uploaded documents or sample knowledge.');
 if(scope==='uploads'&&!user)fail(401,'Your private workspace session is missing or expired. Reload Mochi and allow its secure cookie.');
 const start=performance.now();let docs=samples;if(scope==='uploads'){storage(env);docs=await loadOwned(env,user.id);}
 const collection=String(input.collection||'All knowledge');docs=docs.filter(d=>collection==='All knowledge'||d.collection===collection);
 const opts=options(input),hits=retrieve(input.question,docs,opts);
 return json({question:input.question,hits,elapsed:performance.now()-start,collection,mode:opts.mode,strategy:opts.strategy,scope,answerMode:'extractive',isComparison:scope==='samples'&&/compar|cheap|cost.efficient|hidden charge/i.test(input.question)&&/vendor|proposal|atlas|bloom|cobalt/i.test(input.question)&&docs.filter(d=>d.vendor).length===3});
 }
 if(path.startsWith('/api/documents')){
 if(!user)fail(401,'Your private workspace session is missing or expired. Reload Mochi and allow its secure cookie.');storage(env);
 if(path==='/api/documents'&&request.method==='GET')return json({documents:await loadOwned(env,user.id)});
 if(path==='/api/documents'&&request.method==='POST'){
 const doc=validateDocument(await body(request)),id=crypto.randomUUID(),key=`documents/${id}.json`,created=new Date().toISOString();
 await env.BUCKET.put(key,JSON.stringify(doc),{httpMetadata:{contentType:'application/json'}});
 try{const result=await env.DB.prepare('INSERT INTO documents (id,owner,name,type,collection,object_key,size,chars,pages,created) SELECT ?,?,?,?,?,?,?,?,?,? WHERE (SELECT COUNT(*) FROM documents WHERE owner=?) < 50 AND (SELECT COALESCE(SUM(chars),0) FROM documents WHERE owner=?) + ? <= 1000000').bind(id,user.id,doc.name,doc.type,doc.collection,key,doc.size,doc.chars,doc.pages.length,created,user.id,user.id,doc.chars).run();if(!result.meta.changes)fail(413,'Your workspace limit is 50 documents and 1,000,000 extracted characters. Remove a document before adding more.');}
 catch(error){await env.BUCKET.delete(key);throw error;}
 return json({document:{...doc,id,uploaded:true,cloud:true,updated:created}},201);
 }
 const match=path.match(/^\/api\/documents\/([a-z0-9-]{36})$/);
 if(match){const row=await env.DB.prepare('SELECT * FROM documents WHERE id = ? AND owner = ?').bind(match[1],user.id).first();if(!row)fail(404,'Document not found.');
 if(request.method==='GET')return json({document:await loadDocument(env,row)});
 if(request.method==='DELETE'){await env.BUCKET.delete(row.object_key);await env.DB.prepare('DELETE FROM documents WHERE id = ? AND owner = ?').bind(row.id,user.id).run();return json({deleted:true});}}
 }
 fail(404,'Endpoint not found.');
 }catch(error){if(error instanceof HttpError)return json({error:error.message},error.status);console.error('Mochi backend error',error?.name||'Error');return json({error:'The document service could not complete this request. Please try again.'},503);}}
