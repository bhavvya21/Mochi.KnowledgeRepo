const stop = new Set('a an the is are what how when where who why can could should would tell me about find documented according documents and or of to in for with from at by be this that it its as on source cite please'.split(' '));
export const tokenize = text => (String(text).toLowerCase().match(/[a-z0-9]+/g)||[]).filter(t=>!stop.has(t));
const count = tokens => {const m=new Map();tokens.forEach(t=>m.set(t,(m.get(t)||0)+1));return m;};
export function chunkDocuments(docs,strategy='structure') {
 return docs.flatMap(d=>d.pages.flatMap(p=>{
 const words=p.text.split(/\s+/); const windowed=(size,step)=>Array.from({length:Math.ceil(words.length/step)},(_,i)=>words.slice(i*step,i*step+size).join(' ')); const parts=strategy==='fixed'&&words.length>24?windowed(24,20):strategy==='sentence'?(p.text.match(/[^.!?]+[.!?]?/g)||[p.text]).flatMap(s=>{const w=s.split(/\s+/);return w.length>140?Array.from({length:Math.ceil(w.length/120)},(_,i)=>w.slice(i*120,i*120+140).join(' ')):[s]}):words.length>140?windowed(140,120):[p.text];
 return parts.map((text,i)=>({id:`${d.id}:${p.page}:${i}`,document:d.id,name:d.name,type:d.type,collection:d.collection,page:p.page,topic:p.topic,text:text.trim(),value:p.value}));
 }));
}
export function retrieve(query,docs,{mode='hybrid',strategy='structure',limit=5}={}) {
 const chunks=chunkDocuments(docs,strategy), terms=[...new Set(tokenize(query))];
 if(!terms.length||!chunks.length)return [];
 const bags=chunks.map(c=>count(tokenize(c.topic+' '+c.text))), lengths=bags.map(b=>[...b.values()].reduce((a,b)=>a+b,0));
 const avg=lengths.reduce((a,b)=>a+b,0)/chunks.length||1,df=new Map();
 bags.forEach(b=>b.forEach((_,t)=>df.set(t,(df.get(t)||0)+1)));
 const idf=t=>Math.log(1+(chunks.length-(df.get(t)||0)+.5)/((df.get(t)||0)+.5));
 const qnorm=Math.sqrt(terms.reduce((a,t)=>a+idf(t)**2,0))||1;
 const rows=chunks.map((c,i)=>{
 let bm25=0,dot=0,norm=0;
 bags[i].forEach((tf,t)=>norm+=(1+Math.log(tf))**2*idf(t)**2);
 terms.forEach(t=>{const tf=bags[i].get(t)||0;if(tf){bm25+=idf(t)*tf*2.2/(tf+1.2*(.25+.75*lengths[i]/avg));dot+=(1+Math.log(tf))*idf(t)**2;}});
 return {...c,bm25,cosine:dot/(Math.sqrt(norm)*qnorm||1),coverage:terms.filter(t=>bags[i].has(t)).length/terms.length};
 });
 const bm=[...rows].sort((a,b)=>b.bm25-a.bm25), dense=[...rows].sort((a,b)=>b.cosine-a.cosine);
 const ranks1=new Map(bm.map((r,i)=>[r.id,i+1])),ranks2=new Map(dense.map((r,i)=>[r.id,i+1]));
 return rows.filter(r=>r.bm25>0).map(r=>({...r,score:mode==='bm25'?r.bm25:mode==='tfidf'?r.cosine:1/(60+ranks1.get(r.id))+1/(60+ranks2.get(r.id))})).sort((a,b)=>b.score-a.score).slice(0,limit);
}
export function compareVendors(docs,gb=2000,years=1) {
 return docs.filter(d=>d.vendor).map(d=>{const v=d.vendor; const annualOverage=Math.max(0,gb-v.storage)*v.overage*12;let total=v.setup;for(let y=0;y<years;y++)total+=v.base*(1+v.renewal)**y+v.support+annualOverage;return {...v,id:d.id,annualOverage,total,firstYear:v.base+v.setup+v.support+annualOverage};}).sort((a,b)=>a.total-b.total);
}
export function runBenchmark(docs,questions,options={}) {
 const start=performance.now();const rows=questions.map(q=>{const t=performance.now();const results=retrieve(q.question,docs,{...options,limit:10});const rank=results.findIndex(r=>r.document===q.reference.document&&r.page===q.reference.page)+1;return {...q,rank,recall5:rank>0&&rank<=5?1:0,mrr10:rank>0?1/rank:0,latency:performance.now()-t,top:results[0]?{document:results[0].document,page:results[0].page}:null};});
 const times=rows.map(r=>r.latency).sort((a,b)=>a-b);return {count:rows.length,recall5:rows.reduce((a,r)=>a+r.recall5,0)/rows.length,mrr10:rows.reduce((a,r)=>a+r.mrr10,0)/rows.length,p95:times[Math.max(0,Math.ceil(times.length*.95)-1)],duration:performance.now()-start,rows,options,timestamp:new Date().toISOString()};
}
