import unittest,json,tempfile,concurrent.futures,io,copy
from pathlib import Path
from invoices import Ledger,Invalid,validate,time_lines
from pdf import render
from pypdf import PdfReader
class Invoices(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.l=Ledger(self.tmp.name+'/invoices.db');self.d=json.loads(Path('examples/draft.json').read_text())
 def tearDown(self):self.tmp.cleanup()
 def test_exact_totals(self):
  d=validate(self.d);self.assertEqual(d['total_cents'],27300)
 def test_round_half_up(self):
  self.d['lines']=[{'description':'Small','quantity':'0.5','unit_price':'0.01'}];self.d['tax_percent']='50';d=validate(self.d);self.assertEqual((d['subtotal_cents'],d['tax_cents']),(1,1))
 def test_numbers_concurrent(self):
  with concurrent.futures.ThreadPoolExecutor(4) as e:ids=list(e.map(lambda _:self.l.issue(self.d),range(8)))
  self.assertEqual(sorted(ids),list(range(1,9)))
 def test_invalid_issue_does_not_consume_number(self):
  with self.assertRaises(Invalid):self.l.issue({})
  self.assertEqual(self.l.issue(self.d),1)
 def test_immutable_after_caller_edit(self):
  id=self.l.issue(self.d);self.d['customer']='Changed';self.assertNotEqual(self.l.get(id)['customer'],'Changed')
 def test_void_permanent_and_history(self):
  id=self.l.issue(self.d);self.l.status(id,'paid');self.l.status(id,'void')
  with self.assertRaises(Invalid):self.l.status(id,'unpaid')
  self.assertEqual([e['status'] for e in self.l.get(id)['events']],['unpaid','paid','void'])
 def test_status_idempotent(self):
  id=self.l.issue(self.d);self.l.status(id,'unpaid');self.assertEqual(len(self.l.get(id)['events']),1)
 def test_invalid_money(self):
  for x in ['NaN','Infinity','-1','1e2',1.5,'1.001']:
   d=copy.deepcopy(self.d);d['lines'][0]['unit_price']=x
   with self.assertRaises(Invalid):validate(d)
 def test_due_before_issued(self):
  self.d['due']='2025-01-01'
  with self.assertRaises(Invalid):validate(self.d)
 def test_time_import_and_exact_seconds(self):
  lines=time_lines({'version':1,'entries':[{'id':1,'start':0,'end':1,'note':'Brief'},{'id':2,'end':None}]},'999999.99');self.d['lines']=lines;d=validate(self.d);self.assertEqual(d['subtotal_cents'],27778)
 def test_import_duplicates(self):
  row={'id':1,'start':0,'end':60,'note':'Work'}
  with self.assertRaises(Invalid):time_lines({'version':1,'entries':[row,row]},'50')
 def test_pdf_extractable_number_totals_and_text(self):
  id=self.l.issue(self.d);data=render(self.l.get(id));reader=PdfReader(io.BytesIO(data));text=''.join(p.extract_text() for p in reader.pages);self.assertIn('INV-000001',text);self.assertIn('273.00',text);self.assertIn('Sample Client',text)
 def test_pdf_multipage(self):
  self.d['lines']=[{'description':'Line '+str(i)+' '+('Detailed work '*15),'quantity':'1','unit_price':'1.00'} for i in range(100)];id=self.l.issue(self.d);r=PdfReader(io.BytesIO(render(self.l.get(id))));self.assertGreater(len(r.pages),1);self.assertIn('Line 99',''.join(p.extract_text() for p in r.pages))
 def test_pdf_rejects_unsupported_glyph(self):
  self.d['customer']='😀';id=self.l.issue(self.d)
  with self.assertRaises(Invalid):render(self.l.get(id))
 def test_pdf_literal_markup(self):
  self.d['customer']='<b>Not markup</b>';id=self.l.issue(self.d);r=PdfReader(io.BytesIO(render(self.l.get(id))));self.assertIn('<b>Not markup</b>',r.pages[0].extract_text())
