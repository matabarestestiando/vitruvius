import base64
from app import chat_repositories as r


def test_only_explicit_github_root(monkeypatch):
    monkeypatch.setattr(r,'github_json',lambda p: (_ for _ in ()).throw(AssertionError('network')))
    assert r.snapshot('una pregunta sin repo') is None
    assert r.snapshot('https://github.com.evil/owner/repo') is None
    assert 'enlace raíz' in r.snapshot('https://github.com/owner/repo/tree/main')


def test_snapshot_scopes_and_filters(monkeypatch):
    seen=[]
    def api(path):
        seen.append(path)
        if '/commits/' in path:return {'sha':'a'*40}
        if '/trees/' in path:return {'tree':[{'type':'blob','mode':'100644','path':p,'sha':'b'*40,'size':20} for p in ['README.md','.env','credentials.txt','app/main.py','secrets.json']]+[{'type':'blob','mode':'120000','path':'link.py','sha':'b'*40,'size':20}], 'truncated':True}
        return {'content':base64.b64encode(b'real code').decode()}
    monkeypatch.setattr(r,'github_json',api)
    out=r.snapshot('Revise https://github.com/org/repo.git')
    assert 'real code' in out and 'a'*40 in out and 'incompleto' in out
    assert '.env' not in out and 'credentials.txt' not in out and 'link.py' not in out
    assert all(p.startswith('/repos/org/repo/') for p in seen)


def test_unavailable_is_explicit(monkeypatch):
    def api(path):raise r.SourceAccessError('Repositorio privado sin acceso')
    monkeypatch.setattr(r,'github_json',api)
    assert 'sin acceso' in r.snapshot('https://github.com/org/private')
