import unittest,tempfile,json,subprocess,sys
from pathlib import Path
from invoices import Ledger
class CLI(unittest.TestCase):
 def test_unsupported_pdf_text_does_not_consume_invoice_number(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);draft=json.loads(Path('examples/draft.json').read_text());draft['customer']='Unsupported 😀';(p/'draft.json').write_text(json.dumps(draft))
   cmd=[sys.executable,'cli.py','--database',str(p/'invoice.db'),'issue',str(p/'draft.json')]
   result=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(result.returncode,1);self.assertIn('font does not support',result.stderr);self.assertEqual(Ledger(str(p/'invoice.db')).listing(),[])
   draft['customer']='日本語';(p/'draft.json').write_text(json.dumps(draft));result=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'1')
