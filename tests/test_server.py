import unittest,tempfile,json,copy,concurrent.futures
from pathlib import Path
from server import create_app
from invoices import Ledger,Invalid
class Server(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=self.tmp.name+'/db';self.c=create_app(self.path,'x'*40).test_client();self.h={'Authorization':'Bearer '+'x'*40,'Idempotency-Key':'test-request-key-0001'};self.d=json.loads(Path('examples/draft.json').read_text())
 def tearDown(self):self.tmp.cleanup()
 def test_auth(self):
  for url in ['/api/invoices','/api/invoices/1','/api/invoices/1/pdf']:self.assertEqual(self.c.get(url).status_code,401)
  self.assertEqual(self.c.post('/api/invoices',json=self.d).status_code,401)
 def test_preview_allocates_nothing(self):
  self.assertEqual(self.c.post('/api/preview',headers=self.h,json=self.d).json['total_cents'],27300);self.assertEqual(self.c.get('/api/invoices',headers=self.h).json,[])
 def test_retry_same_invoice(self):
  a=self.c.post('/api/invoices',headers=self.h,json=self.d);b=self.c.post('/api/invoices',headers=self.h,json=self.d);self.assertEqual(a.status_code,201);self.assertEqual(a.json['id'],b.json['id']);self.assertEqual(len(self.c.get('/api/invoices',headers=self.h).json),1)
 def test_changed_retry_rejected(self):
  self.c.post('/api/invoices',headers=self.h,json=self.d);self.d['customer']='Other';self.assertEqual(self.c.post('/api/invoices',headers=self.h,json=self.d).status_code,400)
 def test_concurrent_retries(self):
  l=Ledger(self.path)
  with concurrent.futures.ThreadPoolExecutor(4) as pool:ids=list(pool.map(lambda _:l.issue(self.d,'same-request-key-0002'),range(8)))
  self.assertEqual(len(set(ids)),1)
 def test_pdf_preflight_rejects_before_number(self):
  self.d['customer']='😀';self.assertEqual(self.c.post('/api/invoices',headers=self.h,json=self.d).status_code,400);self.assertEqual(Ledger(self.path).listing(),[])
 def test_status_and_pdf(self):
  id=self.c.post('/api/invoices',headers=self.h,json=self.d).json['id'];r=self.c.post(f'/api/invoices/{id}/status',headers=self.h,json={'status':'paid'});self.assertEqual(r.json['status'],'paid');r=self.c.get(f'/api/invoices/{id}/pdf',headers=self.h);self.assertTrue(r.data.startswith(b'%PDF'));self.assertIn('attachment',r.headers['Content-Disposition'])
 def test_invalid_body(self):
  self.assertEqual(self.c.post('/api/preview',headers=self.h,json=[]).status_code,400)
  self.assertEqual(self.c.post('/api/preview',headers=self.h,data='x').status_code,415)

 def test_oversized_invoice_ids_preserve_records_and_events(self):
  ledger=Ledger(self.path);id=ledger.issue(self.d);before=ledger.get(id)
  for bad in [0,2**63,10**100]:
   base=f'/api/invoices/{bad}'
   for response in [self.c.get(base,headers=self.h),self.c.get(base+'/pdf',headers=self.h),self.c.post(base+'/status',headers=self.h,json={'status':'paid'})]:
    self.assertEqual(response.status_code,400);self.assertIn('invoice ID',response.json['error'])
   self.assertEqual(ledger.get(id),before)
  self.assertEqual(ledger.issue(self.d),id+1)
 def test_in_range_missing_invoice_is_coherent_error(self):
  response=self.c.get('/api/invoices/9223372036854775807',headers=self.h)
  self.assertEqual(response.status_code,400);self.assertEqual(response.json['error'],'Invoice not found.')
