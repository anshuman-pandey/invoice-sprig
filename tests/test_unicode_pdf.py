import unittest,json,io,tempfile
from pathlib import Path
from invoices import Ledger
from pdf import render
from pypdf import PdfReader
class UnicodePDF(unittest.TestCase):
 def test_cjk_and_european_names_remain_extractable(self):
  with tempfile.TemporaryDirectory() as d:
   ledger=Ledger(d+'/test.db');draft=json.loads(Path('examples/draft.json').read_text())
   draft.update(seller='設計工作室 日本語',customer='繁體中文 简体中文 Müller García')
   draft['lines'][0]['description']='设计服务 · デザイン · Entwurf'
   invoice=ledger.get(ledger.issue(draft));data=render(invoice)
   text=''.join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
   for value in [draft['seller'],draft['customer'],draft['lines'][0]['description'],invoice['number']]:self.assertIn(value,text)
