import hashlib
import io
import json
import math
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from mochi.app import create_app
from mochi.config import Settings
from mochi.schema import Draft, Verification, Query
from mochi.models import Ollama
from mochi.retrieval import chunk_pages, tokens
from mochi.ingest import parse_file
from mochi.calculator import Calculation, calculate


class TestModels:
    """Deterministic test double; production always uses FastEmbed models."""
    __test__=False
    def load(self):pass
    def embed(self,texts):
        vectors=[]
        for text in texts:
            v=[0.]*384
            for token in tokens(text):v[int(hashlib.sha256(token.encode()).hexdigest(),16)%384]+=1
            n=math.sqrt(sum(x*x for x in v)) or 1
            vectors.append([x/n for x in v])
        return vectors
    def rerank(self,q,texts):return [float(len(set(tokens(q))&set(tokens(t)))) if set(tokens(q))&set(tokens(t)) else -8. for t in texts]


class TestLLM:
    __test__=False
    settings=SimpleNamespace(vision_model="")
    def plan(self,q):return [q]
    def answer(self,q,hits):return [{"text":hits[0]["text"],"evidence":[{"source":1,"quote":hits[0]["text"]}]}]
    def calculations(self,q,hits):return []


@pytest.fixture
def app():
    return create_app(Settings(database_url="sqlite:///:memory:",origin="https://mochi.test",bridge_key="b"*40),TestModels(),TestLLM(),warmup=False)


def client(app):return TestClient(app,base_url="https://mochi.test",headers={"Origin":"https://mochi.test"})
def init(c):assert c.get('/api/session').status_code==200
def doc(text="Bluebird launches on 14 May with a budget of $2,000."):
    return {"name":"Bluebird.txt","type":"TXT","pages":[{"page":3,"topic":"Bluebird","text":text}]}
def upload(c,text=None):
    response=c.post('/api/documents',json=doc(text) if text else doc())
    assert response.status_code==201,response.text
    return response.json()['document']


def test_sessions_cookie_security(app):
    c=client(app);response=c.get('/api/session')
    assert all(x in response.headers['set-cookie'] for x in ['HttpOnly','Secure','SameSite=lax','Path=/'])
    assert c.get('/api/session').headers.get('set-cookie') is None

def test_anonymous_cannot_read_or_query(app):
    c=client(app)
    assert c.get('/api/documents').status_code==401
    assert c.post('/api/query',json={"question":"secret"}).status_code==401

def test_spoofed_owner_headers_rejected(app):
    c=client(app)
    assert c.get('/api/documents',headers={"X-Mochi-Owner":"victim","Authorization":"Bearer wrong"}).status_code==401

def test_cross_origin_denied(app):
    c=client(app);init(c)
    assert c.post('/api/documents',json=doc(),headers={"Origin":"https://evil.test"}).status_code==403
    assert c.get('/api/session',headers={"Sec-Fetch-Site":"cross-site"}).status_code==403

def test_private_search_and_page_citations(app):
    c=client(app);init(c);saved=upload(c)
    result=c.post('/api/query',json={"question":"When does Bluebird launch?"}).json()
    assert result['answerMode']=='generated'
    assert result['hits'][0]['page']==3
    assert result['hits'][0]['document']==saved['id']
    assert result['claims'][0]['evidence'][0]['quote'] in saved['pages'][0]['text']

def test_cross_workspace_list_read_search_delete(app):
    a,b=client(app),client(app);init(a);init(b);saved=upload(a)
    assert b.get('/api/documents').json()['documents']==[]
    assert b.get('/api/documents/'+saved['id']).status_code==404
    assert b.delete('/api/documents/'+saved['id']).status_code==404
    assert b.post('/api/query',json={"question":"Bluebird"}).json()['hits']==[]

def test_delete_removes_index(app):
    c=client(app);init(c);saved=upload(c)
    assert c.delete('/api/documents/'+saved['id']).status_code==200
    assert c.post('/api/query',json={"question":"Bluebird"}).json()['hits']==[]

def test_unknown_question_abstains(app):
    c=client(app);init(c);upload(c)
    result=c.post('/api/query',json={"question":"Penguin submarines?"}).json()
    assert result['answerMode']=='abstained'

def test_generation_outage_is_explicit(app):
    c=client(app);init(c);upload(c)
    def broken(*args):raise TimeoutError()
    app.state.service.llm.answer=broken
    result=c.post('/api/query',json={"question":"Bluebird"}).json()
    assert result['answerMode']=='unavailable' and result['hits'] and not result['claims']

def test_all_chunking_strategies_are_indexed(app):
    c=client(app);init(c);upload(c)
    for strategy in ['fixed','structure','sentence','semantic']:
        result=c.post('/api/query',json={"question":"Bluebird","strategy":strategy,"generate":False}).json()
        assert result['hits'] and result['strategy']==strategy

def test_raw_text_upload(app):
    c=client(app);init(c)
    response=c.post('/api/upload',files={"file":('brief.txt',b'Bluebird ships on May 14.','text/plain')})
    assert response.status_code==201,response.text
    assert response.json()['document']['pages'][0]['text']=='Bluebird ships on May 14.'

def test_invalid_type_and_duplicate_pages(app):
    c=client(app);init(c);payload=doc();payload['pages']*=2
    assert c.post('/api/documents',json=payload).status_code==422
    assert c.post('/api/upload',files={"file":('evil.exe',b'abc')}).status_code==400

def test_workspace_quota(app):
    app.state.settings.max_documents=1
    c=client(app);init(c);upload(c)
    assert c.post('/api/documents',json=doc()).status_code==400

def test_rate_budget(app):
    c=client(app);init(c)
    for _ in range(30):assert c.post('/api/query',json={"question":"Bluebird","generate":False}).status_code==200
    assert c.post('/api/query',json={"question":"Bluebird"}).status_code==429

def test_trusted_bridge_migration_is_idempotent(app):
    c=client(app)
    c.headers.update({"Authorization":"Bearer "+"b"*40,"X-Mochi-Owner":"old-user"})
    assert not c.get('/api/migration-state').json()['migrated']
    payload={"documents":[dict(doc(),id='old-id')]}
    assert c.post('/api/migrate',json=payload).status_code==200
    assert c.post('/api/migrate',json=payload).status_code==200
    docs=c.get('/api/documents').json()['documents'];assert len(docs)==1
    c.delete('/api/documents/'+docs[0]['id'])
    c.post('/api/migrate',json=payload)
    assert not c.get('/api/documents').json()['documents']

def test_untrusted_migration_denied(app):
    c=client(app);init(c)
    assert c.post('/api/migrate',json={"documents":[]}).status_code==403

def test_long_chunks_preserve_pages():
    pages=[{"page":7,"text":" ".join(['hello']*600),"topic":"test"}]
    for strategy in ['fixed','semantic','structure','sentence']:
        chunks=chunk_pages(pages,strategy,TestModels())
        assert all(c['page']==7 and len(c['text'].split())<=140 for c in chunks)

def test_quote_validation_and_entailment_gate():
    llm=Ollama(Settings())
    drafts=[Draft.model_validate({"supported":True,"claims":[{"text":"Invented","evidence":[{"source":1,"quote":"not in source"}]}]})]
    llm.structured=lambda *args,**kwargs:drafts.pop(0)
    assert llm.answer('when',[{"text":"Bluebird May 14","name":"doc","page":1}])==[]
    drafts.extend([Draft.model_validate({"supported":True,"claims":[{"text":"May 15","evidence":[{"source":1,"quote":"May 14"}]}]}),Verification(supported=[False])])
    assert llm.answer('when',[{"text":"Bluebird May 14","name":"doc","page":1}])==[]

def test_calculator_rejects_invented_operands():
    hits=[{"text":"Base cost $2,000; setup cost $500."}]
    proposal=Calculation(label='Total',operation='sum',unit='USD',operands=[{"source":1,"quote":hits[0]['text'],"value":"2000"},{"source":1,"quote":hits[0]['text'],"value":"500"}])
    assert calculate([proposal],hits)[0]['result']=='2500.00'
    proposal.operands[1].value='999'
    assert calculate([proposal],hits)==[]

def test_xlsx_parsing_preserves_sheet_citations():
    from openpyxl import Workbook
    book=Workbook();book.active.title='Costs';book.active.append(['Vendor','Cost']);book.active.append(['A',2000])
    stream=io.BytesIO();book.save(stream)
    parsed,warnings=parse_file('costs.xlsx',stream.getvalue(),TestLLM())
    assert 'A | 2000' in parsed.pages[0].text
    assert parsed.pages[0].page==1 and 'Costs' in parsed.pages[0].topic

def test_csv_and_json_parsing():
    parsed,_=parse_file('data.csv',b'Name,Cost\nA,2000',TestLLM())
    assert 'Name | Cost' in parsed.pages[0].text
    with pytest.raises(ValueError):parse_file('data.json',b'{broken',TestLLM())
