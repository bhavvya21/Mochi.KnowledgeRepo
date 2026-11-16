import test from 'node:test';
import assert from 'node:assert/strict';
import {pythonBridge} from '../worker/python-bridge.js';

test('Python bridge denies insecure configuration and missing identity',async()=>{
  const req=new Request('https://mochi.test/api/documents');
  assert.equal((await pythonBridge(req,{MOCHI_PYTHON_URL:'http://api.test',MOCHI_BRIDGE_KEY:'secret'},{id:'a'},()=>[])).status,503);
  assert.equal((await pythonBridge(req,{MOCHI_PYTHON_URL:'https://api.test',MOCHI_BRIDGE_KEY:'secret'},null,()=>[])).status,401);
});

test('Python bridge uses server identity, migrates once, and omits caller credentials',async()=>{
  const original=globalThis.fetch,calls=[];
  globalThis.fetch=async(url,options)=>{calls.push([url.pathname,options]);if(url.pathname==='/api/migration-state')return Response.json({migrated:false});if(url.pathname==='/api/migrate')return Response.json({migrated:true});return Response.json({documents:[]});};
  try{
    const req=new Request('https://mochi.test/api/documents',{headers:{'X-Mochi-Owner':'victim','Authorization':'Bearer attacker','Cookie':'private-cookie'}});
    const response=await pythonBridge(req,{MOCHI_PYTHON_URL:'https://api.test',MOCHI_BRIDGE_KEY:'server-secret'},{id:'actual-owner'},async()=>[{id:'old'}]);
    assert.equal(response.status,200);
    assert.deepEqual(calls.map(c=>c[0]),['/api/migration-state','/api/migrate','/api/documents']);
    for(const [,options] of calls){assert.equal(options.headers['X-Mochi-Owner'],'actual-owner');assert.equal(options.headers.Authorization,'Bearer server-secret');assert.equal(options.headers.Cookie,undefined);}
  }finally{globalThis.fetch=original;}
});
