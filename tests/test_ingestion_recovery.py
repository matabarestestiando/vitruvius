from datetime import timedelta
from app.db import Record,now
from app.ingestion_recovery import recover


def doc(db,**kw):
    row=Record(kind='context',created_at=now()-timedelta(minutes=10),data={'status':'queued','object_key':'synthetic-only','content_type':'application/pdf',**kw});db.add(row);db.commit();return row


def test_recovers_missing_work_without_duplicate_dispatch(db,monkeypatch):
    import app.ingestion_recovery as module
    monkeypatch.setattr(module,'Progress',lambda id:lambda *a,**kw:None)
    missing=doc(db);queued=doc(db);ready=doc(db,status='ready');expired=doc(db,expires_at=(now()-timedelta(seconds=1)).isoformat())
    calls=[]
    assert recover(db,{queued.id},calls.append)==[missing.id]
    assert calls==[missing.id] and missing.data['ingest_recovery_count']==1
    assert recover(db,{queued.id},calls.append)==[]
    assert ready.data['status']=='ready' and expired.data['status']=='queued'


def test_failed_publish_remains_recoverable(db,monkeypatch):
    import app.ingestion_recovery as module
    monkeypatch.setattr(module,'Progress',lambda id:lambda *a,**kw:None)
    d=doc(db)
    def fail(id):raise OSError('Broker unavailable')
    assert recover(db,set(),fail)==[]
    assert d.data['status']=='queued' and d.data['ingest_recovery_count']==1
    d.data={**d.data,'ingest_dispatch_requested_at':(now()-timedelta(minutes=3)).isoformat()};db.commit()
    calls=[];assert recover(db,set(),calls.append)==[d.id]


def test_real_delivery_snapshot_includes_queued_reserved_and_active(monkeypatch):
    import base64,json
    from types import SimpleNamespace
    import app.ingestion_recovery as module
    queued=json.dumps({'headers':{'task':'context.ingest'},'body':base64.b64encode(json.dumps([['queued-doc'],{},{}]).encode()).decode()})
    monkeypatch.setattr(module,'client',lambda:SimpleNamespace(lrange=lambda *args:[queued]))
    inspector=SimpleNamespace(reserved=lambda:{'worker':[{'name':'context.ingest','args':['reserved-doc']}]},active=lambda:{'worker':[{'name':'context.ingest','args':['active-doc']}]})
    celery=SimpleNamespace(conf=SimpleNamespace(task_default_queue='celery'),control=SimpleNamespace(inspect=lambda **kw:inspector))
    assert module.known_deliveries(celery)=={'queued-doc','reserved-doc','active-doc'}
