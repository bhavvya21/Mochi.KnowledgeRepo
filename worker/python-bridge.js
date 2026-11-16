// Deployment adapter only: FastAPI owns ingestion, indexing, retrieval and generation.
// The existing Sites cookie is retained so users keep access to their documents.
export async function pythonBridge(request, env, user, loadLegacy) {
  const base = new URL(env.MOCHI_PYTHON_URL);
  if (base.protocol !== 'https:' || base.username || base.password || !env.MOCHI_BRIDGE_KEY) {
    return Response.json({error:'Python backend bridge is not configured securely.'},{status:503});
  }
  if (!user) return Response.json({error:'Reload Mochi to initialize your private workspace.'},{status:401});
  const headers = {'Authorization':`Bearer ${env.MOCHI_BRIDGE_KEY}`,'X-Mochi-Owner':user.id};
  const call = (path,options={}) => fetch(new URL(path,base),{...options,redirect:'error',headers:{...headers,...options.headers},signal:AbortSignal.timeout(240000)});
  const path = new URL(request.url).pathname;
  if (!['/api/session','/api/health'].includes(path)) {
    const state = await call('/api/migration-state');
    if (!state.ok) return new Response(state.body,{status:state.status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
    if (!(await state.json()).migrated) {
      const migrated = await call('/api/migrate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({documents:await loadLegacy()})});
      if (!migrated.ok) return new Response(migrated.body,{status:migrated.status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
    }
  }
  const response=await call(path,{method:request.method,headers:request.headers.has('content-type')?{'Content-Type':request.headers.get('content-type')}:{},body:['GET','HEAD'].includes(request.method)?undefined:request.body});
  return new Response(response.body,{status:response.status,headers:{'Content-Type':'application/json','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
}
