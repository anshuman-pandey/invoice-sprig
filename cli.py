import argparse,json,os,sys,sqlite3
from pathlib import Path
from invoices import Ledger,Invalid,time_lines,validate

def write_new(path,data):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f:f.write(data)
def main():
 os.umask(0o077);p=argparse.ArgumentParser(description='Invoice Sprig: local numbered invoices. Issuing is irreversible; review the draft first.');p.add_argument('--database',default='invoices.sqlite3');sub=p.add_subparsers(dest='command',required=True)
 a=sub.add_parser('issue');a.add_argument('draft');a=sub.add_parser('show');a.add_argument('id',type=int);sub.add_parser('list');a=sub.add_parser('status');a.add_argument('id',type=int);a.add_argument('status',choices=['unpaid','paid','void']);a=sub.add_parser('pdf');a.add_argument('id',type=int);a.add_argument('output');a=sub.add_parser('import-time');a.add_argument('source');a.add_argument('rate');a.add_argument('output')
 args=p.parse_args()
 try:
  if args.command=='import-time':write_new(args.output,(json.dumps(time_lines(json.loads(Path(args.source).read_text()),args.rate),indent=2)+'\n').encode());return
  ledger=Ledger(args.database)
  if args.command=='issue':
   from pdf import render
   draft=json.loads(Path(args.draft).read_text());render({'number':'DRAFT','status':'draft',**validate(draft)})
   print(ledger.issue(draft))
  elif args.command=='show':print(json.dumps(ledger.get(args.id),indent=2))
  elif args.command=='list':print(json.dumps(ledger.listing(),indent=2))
  elif args.command=='status':ledger.status(args.id,args.status);print('Status recorded.')
  elif args.command=='pdf':
   from pdf import render
   write_new(args.output,render(ledger.get(args.id)));print('PDF saved.')
 except sqlite3.Error:print('Error: Invoice storage is unavailable. Check the database path and permissions.',file=sys.stderr);return 1
 except (Invalid,OSError,json.JSONDecodeError) as e:print('Error: '+str(e),file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
