import {writeFileSync} from 'node:fs';
import {documents,benchmark} from '../src/data.js';
import {runBenchmark} from '../src/retrieval.js';
writeFileSync(new URL('./corpus.json',import.meta.url),JSON.stringify(documents,null,2));
writeFileSync(new URL('./questions-180.json',import.meta.url),JSON.stringify(benchmark,null,2));
const reports=['hybrid','bm25','tfidf'].map(mode=>runBenchmark(documents,benchmark,{mode,strategy:'structure'}));
writeFileSync(new URL('./development-results.json',import.meta.url),JSON.stringify({notice:'Synthetic regression dataset; not an independent held-out evaluation. Latency is Node retrieval only.',reports},null,2));
console.log(JSON.stringify(reports.map(({options,count,recall5,mrr10,p95})=>({options,count,recall5,mrr10,p95})),null,2));
