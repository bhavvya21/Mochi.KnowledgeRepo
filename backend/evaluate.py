"""Evaluate actual Python retrieval; optionally include Ollama generation.

Run from repository root: PYTHONPATH=backend python backend/evaluate.py --output work/evaluation.json
The supplied 180 questions are development fixtures, not independent evidence of quality.
"""
import argparse
import json
import statistics
from pathlib import Path
from mochi.config import Settings
from mochi.db import database
from mochi.models import LocalModels, Ollama
from mochi.service import RagService
from mochi.schema import Query


def evaluate(service,questions,mode="hybrid",strategy="structure",generate=False):
    rows=[]
    for q in questions:
        result=service.query("samples",Query(question=q['question'],scope='samples',mode=mode,strategy=strategy,generate=generate,decompose=generate))
        rank=next((i for i,h in enumerate(result['hits'],1) if h['document']==q['reference']['document'] and h['page']==q['reference']['page']),0)
        refs=[(e,result['hits'][e['source']-1]) for c in result['claims'] for e in c['evidence'] if e['source']<=len(result['hits'])]
        valid=sum(' '.join(e['quote'].split()) in ' '.join(h['text'].split()) for e,h in refs)
        rows.append({**q,"rank":rank,"latencyMs":result['elapsed'],"answerMode":result['answerMode'],
                     "answerContainsReference":q['answer'].casefold() in result['answer'].casefold() if generate else None,
                     "validatedQuotes":valid,"totalQuotes":len(refs),"generatedAnswer":result['answer'],
                     "claims":result['claims'],"manualCorrect":None,"manualUnsupportedClaims":None})
    n=len(rows);times=sorted(r['latencyMs'] for r in rows)
    total=sum(r['totalQuotes'] for r in rows)
    return {"dataset":"180-question synthetic development corpus","count":n,"mode":mode,"strategy":strategy,
            "generationEnabled":generate,"recallAt5":sum(0<r['rank']<=5 for r in rows)/n,
            "mrrAt10":sum(1/r['rank'] if r['rank'] else 0 for r in rows)/n,
            "latencyP95Ms":times[max(0,__import__('math').ceil(.95*n)-1)],
            "exactQuoteValidity":sum(r['validatedQuotes'] for r in rows)/total if total else None,
            "answerReferenceContainment":sum(bool(r['answerContainsReference']) for r in rows)/n if generate else None,
            "citationSemanticCorrectness":None,"answerAccuracy":None,"hallucinationRate":None,
            "note":"Semantic citation correctness, answer accuracy and hallucination rate require manual adjudication; exact quote validity is not entailment accuracy.","rows":rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True);parser.add_argument('--generate',action='store_true')
    parser.add_argument('--mode',choices=['hybrid','dense','bm25'],default='hybrid')
    parser.add_argument('--strategy',choices=['structure','fixed','sentence','semantic'],default='structure')
    args=parser.parse_args();settings=Settings();engine,factory=database(settings.database_url)
    service=RagService(factory,settings,LocalModels(settings),Ollama(settings));service.seed()
    questions=json.loads(Path('benchmarks/questions-180.json').read_text(encoding='utf-8'))
    report=evaluate(service,questions,args.mode,args.strategy,args.generate)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
