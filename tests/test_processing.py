from pathlib import Path
from app.processing import extract_for_ingestion,Progress,read_many


def test_native_pdf_keeps_pages_and_reports_real_progress(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    w=PdfWriter();w.add_blank_page(width=612,height=792)
    page=w.add_blank_page(width=612,height=792)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):w._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 60 720 Td (Actual synthetic page two.) Tj ET');page[NameObject('/Contents')]=w._add_object(stream)
    path=tmp_path/'synthetic.pdf'
    with path.open('wb') as f:w.write(f)
    states=[]
    def progress(stage,**values):states.append((stage,values))
    def layout(*args):raise AssertionError('Digital text must not invoke slow layout model')
    pages=list(extract_for_ingestion(path,'application/pdf',progress,fallback=layout))
    assert len(pages)==2 and pages[0]==(1,'') and 'Actual synthetic' in pages[1][1]
    assert states[-1][1]['pages_done']==2 and states[-1][1]['pages_total']==2 and states[-1][1]['pages_without_text']==1


def test_empty_pdf_uses_explicit_layout_fallback(tmp_path):
    from pypdf import PdfWriter
    w=PdfWriter();w.add_blank_page(width=612,height=792);path=tmp_path/'blank.pdf'
    with path.open('wb') as f:w.write(f)
    stages=[]
    result=list(extract_for_ingestion(path,'application/pdf',lambda stage,**kw:stages.append(stage),fallback=lambda *args:[(1,'Fallback parser result')]))
    assert result==[(1,'Fallback parser result')] and stages==['layout']


def test_progress_store_failure_does_not_break_processing(monkeypatch):
    import app.processing as p
    def fail():raise OSError('Redis unavailable')
    monkeypatch.setattr(p,'client',fail)
    progress=Progress('synthetic');progress('extracting',pages_done=2,pages_total=10)
    assert progress.state['pages_done']==2 and read_many(['synthetic'])=={}
