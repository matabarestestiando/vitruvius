from app.db import Record
from app.seed import seed
from app.grounding import primary_author_matches


def test_legacy_spelling_correction_preserves_expert_and_source_links(db):
    expert=Record(kind='expert',data={'name':'Micheal Lanham','specialty':'Implementación de agentes','primary_source_ids':['existing-source'],'principles':'Keep custom method'})
    db.add(expert);db.commit();id=expert.id
    seed(db);seed(db)
    assert expert.id==id and expert.data['name']=='Michael Lanham'
    assert expert.data['primary_source_ids']==['existing-source'] and expert.data['principles']=='Keep custom method'
    assert primary_author_matches(expert,{'author':'Michael Lanham'})
    assert not primary_author_matches(expert,{'author':'Antonio Gulli'})
