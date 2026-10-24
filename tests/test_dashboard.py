import csv
import io
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient
from upri.api import create_app
from test_api import client, payload, TOKEN


def test_dashboard_private_data_and_preview(client):
    public = TestClient(client.app)
    assert public.get('/').status_code == 200
    assert "frame-ancestors 'none'" in public.get('/').headers['content-security-policy']
    for path in ['/v1/drafts','/v1/batches','/v1/printer']:
        assert public.get(path).status_code == 401
    data=payload()
    data['shipments'][0]['recipient']['name']='<img src=x>'
    r=client.post('/v1/preview',json=data)
    assert r.status_code==200
    v=r.json()
    assert v['rows'][0][15]=='<img src=x>' and len(v['field_names'])==99
    assert not v['label_generated'] and not v['printing_verified']
    assert r.headers['cache-control']=='no-store'
    assert client.get('/v1/batches').json()['total']==0


def test_revision_atomic_prepare_and_freeze(client):
    draft=client.post('/v1/drafts',json=payload()).json()
    route='/v1/drafts/'+draft['id']
    updated=payload();updated['shipments'][0]['items'][0]['name']='変更済み'
    r=client.put(route,json={'revision':1,'batch':updated})
    assert r.status_code==200 and r.json()['revision']==2
    assert client.put(route,json={'revision':1,'batch':payload()}).status_code==409
    assert client.post(route+'/prepare',json={'revision':1}).status_code==409
    with ThreadPoolExecutor(4) as pool:
        results=list(pool.map(lambda _:client.post(route+'/prepare',json={'revision':2}),range(4)))
    assert all(r.status_code==200 for r in results)
    assert len({r.json()['id'] for r in results})==1
    batch=results[0].json()
    assert client.get('/v1/batches').json()['total']==1
    assert client.get('/v1/batches/'+batch['id']+'/preview').json()['rows'][0][82]=='変更済み'
    assert client.put(route,json={'revision':2,'batch':updated}).status_code==409
    assert client.get(route).json()['prepared_batch']==batch['id']


def test_conflicting_reference_does_not_freeze(client):
    a=client.post('/v1/drafts',json=payload()).json()
    b=client.post('/v1/drafts',json=payload()).json()
    assert client.post('/v1/drafts/'+a['id']+'/prepare',json={'revision':1}).status_code==200
    assert client.post('/v1/drafts/'+b['id']+'/prepare',json={'revision':1}).status_code==409
    assert client.get('/v1/drafts/'+b['id']).json()['prepared_batch'] is None
    assert client.get('/v1/batches').json()['total']==1


def test_reports_are_idempotent_and_never_verify_printing(client):
    b=client.post('/v1/batches',json=payload(),headers={'Idempotency-Key':'reports'}).json()
    route='/v1/batches/'+b['id']
    event={'event_id':str(uuid4()),'status':'print_reported','note':'担当者の報告'}
    for _ in range(2):
        r=client.post(route+'/events',json=event)
        assert r.status_code==200
        assert not r.json()['printing_verified']
        assert r.json()['state']=='csv_prepared'
        assert len(r.json()['operator_events'])==1
    event['status']='print_uncertain'
    assert client.post(route+'/events',json=event).status_code==409
    event['event_id']=str(uuid4())
    assert client.post(route+'/events',json=event).json()['operator_status']=='print_uncertain'
    h='お客様側管理番号,お問い合わせ番号\r\nTEST-001,123456789012\r\n'
    r=client.post(route+'/history',content=h.encode('cp932')).json()
    assert r['state']=='history_received' and r['operator_status']=='print_uncertain'
    assert not r['printing_verified']


def test_restart_and_legacy_batch(tmp_path):
    path=tmp_path/'old.db'
    # Exactly the old schema: additive migration must preserve legacy CSV data.
    with sqlite3.connect(path) as c:
        c.executescript('''CREATE TABLE batches(id TEXT PRIMARY KEY,idem TEXT UNIQUE NOT NULL,digest TEXT NOT NULL,csv BLOB NOT NULL,created TEXT NOT NULL);
        CREATE TABLE shipments(reference TEXT PRIMARY KEY,batch_id TEXT NOT NULL REFERENCES batches(id),tracking TEXT UNIQUE);''')
    first=TestClient(create_app(path,TOKEN),headers={'Authorization':'Bearer '+TOKEN})
    draft=first.post('/v1/drafts',json=payload()).json()
    b=first.post('/v1/drafts/'+draft['id']+'/prepare',json={'revision':1}).json()
    raw=first.get(b['csv_url']).content
    second=TestClient(create_app(path,TOKEN),headers={'Authorization':'Bearer '+TOKEN})
    assert second.get(b['csv_url']).content==raw
    assert second.post('/v1/drafts/'+draft['id']+'/prepare',json={'revision':1}).json()['id']==b['id']
    assert second.get('/v1/drafts/'+draft['id']).json()['batch']==draft['batch']


def test_draft_create_idempotency_and_pagination(client):
    a=client.post('/v1/drafts',json=payload(),headers={'Idempotency-Key':'retry-draft'})
    b=client.post('/v1/drafts',json=payload(),headers={'Idempotency-Key':'retry-draft'})
    assert a.status_code==201 and b.status_code==200 and a.json()['id']==b.json()['id']
    assert client.post('/v1/drafts',json=payload('other'),headers={'Idempotency-Key':'retry-draft'}).status_code==409
    assert client.get('/v1/drafts?limit=1&offset=0').json()['total']==1
    assert client.get('/v1/drafts?limit=1&offset=1').json()['items']==[]


def test_csv_import_review_is_private_and_lossless(client):
    data=payload('IMPORT-1')
    batch=client.post('/v1/batches',json=data,headers={'Idempotency-Key':'import-test'}).json()
    raw=client.get(batch['csv_url']).content
    from upri.models import Batch
    for content in (raw,raw.decode('cp932').encode('utf-8')):
        r=client.post('/v1/import-preview',content=content)
        assert r.status_code==200,r.text
        assert r.json()['batch']==Batch.model_validate(data).model_dump(mode='json')
        assert r.json()['saved'] is False
    assert client.get('/v1/drafts').json()['total']==0
    assert TestClient(client.app).post('/v1/import-preview',content=raw).status_code==401
    rows=list(csv.reader(io.StringIO(raw.decode('cp932'))))
    rows[0][1]='123456789012'  # unsupported preassigned tracking must not be dropped
    buffer=io.StringIO();csv.writer(buffer).writerows(rows)
    assert client.post('/v1/import-preview',content=buffer.getvalue().encode('cp932')).status_code==422
    assert client.post('/v1/import-preview',content=b'x'*1048577).status_code==413


def test_public_demo_does_not_open_data_endpoints(client):
    public=TestClient(client.app)
    assert public.get('/demo').status_code==200
    assert public.get('/assets/demo.js').status_code==200
    assert public.get('/v1/batches').status_code==401
    assert public.get('/v1/drafts').status_code==401


def test_printable_demo_is_public_but_custom_contents_require_auth(client):
    from pypdf import PdfReader
    public=TestClient(client.app)
    for paper,expected in [('a4',(210,297)),('a6',(105,148))]:
        r=public.get('/demo-label.pdf?paper='+paper)
        assert r.status_code==200 and r.headers['content-type']=='application/pdf'
        assert r.headers['cache-control']=='no-store'
        reader=PdfReader(io.BytesIO(r.content));assert len(reader.pages)==1
        page=reader.pages[0]
        assert tuple(round(float(v)*25.4/72,2) for v in [page.mediabox.width,page.mediabox.height])==expected
        text=page.extract_text()
        assert '発送不可' in text and 'サンプル 太郎' in text and 'DEMO-0001' in text
    assert public.post('/v1/demo-labels/pdf',json=payload()).status_code==401
    data=payload();data['shipments'].append(payload('SECOND')['shipments'][0])
    r=client.post('/v1/demo-labels/pdf?paper=a6',json=data)
    assert r.status_code==200
    pages=PdfReader(io.BytesIO(r.content)).pages
    assert len(pages)==2 and all('発送不可' in p.extract_text() for p in pages)
    assert 'SECOND' in pages[1].extract_text() and 'DEMO-0002' in pages[1].extract_text()
    assert client.get('/v1/batches').json()['total']==0
    assert public.get('/demo-label.pdf?paper=letter').status_code==422


def test_demo_pdf_refuses_text_overflow(client):
    data=payload()
    for key in ['address1','address2','address3']:
        data['shipments'][0]['sender'][key]='長'*50
    r=client.post('/v1/demo-labels/pdf',json=data)
    assert r.status_code==422
