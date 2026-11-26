"""Immutable numbered invoices with exact-cent arithmetic and manual status."""
import sqlite3,json,datetime,re
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from contextlib import contextmanager
class Invalid(ValueError):pass

def text(v,limit):
 if not isinstance(v,str) or not v.strip() or len(v)>limit or any(ord(c)<32 for c in v):raise Invalid('Use nonempty text without control characters within the field limit.')
 return v.strip()
def decimal(v,max_value,places):
 if not isinstance(v,str) or len(v)>30 or not re.fullmatch(r'\d+(?:\.\d{1,'+str(places)+r'})?',v):raise Invalid('Use a nonnegative decimal string with the supported precision.')
 n=Decimal(v)
 if n>max_value:raise Invalid('Amount exceeds the supported limit.')
 return n
def cents(v):return int((v*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def validate(d):
 if not isinstance(d,dict):raise Invalid('Invoice must be an object.')
 out={k:text(d.get(k),lim) for k,lim in [('seller',500),('customer',500)]}
 out['currency']=d.get('currency')
 if out['currency'] not in ['USD','EUR','GBP','CAD','AUD']:raise Invalid('Choose USD, EUR, GBP, CAD or AUD.')
 try:
  issued=datetime.date.fromisoformat(d['issued']);due=datetime.date.fromisoformat(d['due'])
 except (ValueError,KeyError,TypeError):raise Invalid('Use ISO dates for issued and due dates.')
 if due<issued:raise Invalid('Due date cannot precede issue date.')
 out.update(issued=issued.isoformat(),due=due.isoformat())
 lines=d.get('lines')
 if not isinstance(lines,list) or not 1<=len(lines)<=100:raise Invalid('Use 1 to 100 invoice lines.')
 out['lines']=[]
 for line in lines:
  if not isinstance(line,dict):raise Invalid('Each line must be an object.')
  description=text(line.get('description'),500);quantity=decimal(line.get('quantity'),Decimal('1000000'),6);rate=decimal(line.get('unit_price'),Decimal('1000000'),2)
  if quantity<=0:raise Invalid('Quantity must be positive.')
  seconds=line.get('seconds')
  if seconds is not None and (type(seconds)!=int or not 0<seconds<=604800):raise Invalid('Invalid source time duration.')
  exact=Decimal(seconds)/3600 if seconds is not None else quantity
  if seconds is not None and quantity!=exact.quantize(Decimal('.000001'),rounding=ROUND_HALF_UP):raise Invalid('Displayed quantity does not match source seconds.')
  out['lines'].append({'description':description,'quantity':str(quantity),'unit_price':str(rate),'seconds':seconds,'cents':cents(exact*rate)})
 subtotal=sum(l['cents'] for l in out['lines'])
 if subtotal>100000000000:raise Invalid('Subtotal exceeds one billion currency units.')
 tax=decimal(d.get('tax_percent','0'),Decimal('100'),4)
 out.update(subtotal_cents=subtotal,tax_percent=str(tax),tax_cents=int((Decimal(subtotal)*tax/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP)))
 out['total_cents']=out['subtotal_cents']+out['tax_cents'];return out

class Ledger:
 def __init__(self,path):
  self.path=path
  with self.db() as c:c.executescript('CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL, status TEXT NOT NULL DEFAULT "unpaid"); CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, invoice INTEGER NOT NULL REFERENCES invoices(id), at TEXT NOT NULL, status TEXT NOT NULL); CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY, body TEXT NOT NULL, invoice INTEGER NOT NULL REFERENCES invoices(id));')
 @contextmanager
 def db(self):
  c=sqlite3.connect(self.path,timeout=5);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
  try:c.execute('BEGIN IMMEDIATE');yield c;c.commit()
  except:c.rollback();raise
  finally:c.close()
 def issue(self,d,request_key=None):
  body=validate(d);encoded=json.dumps(body,sort_keys=True)
  if request_key is not None and (not isinstance(request_key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',request_key)):raise Invalid('Use a valid request key.')
  with self.db() as c:
   if request_key is not None:
    previous=c.execute('SELECT body,invoice FROM requests WHERE key=?',(request_key,)).fetchone()
    if previous:
     if previous['body']!=encoded:raise Invalid('This request key belongs to a different draft. Start a new request.')
     return previous['invoice']
   id=c.execute('INSERT INTO invoices(body) VALUES(?)',(json.dumps(body),)).lastrowid
   c.execute('INSERT INTO events(invoice,at,status) VALUES(?,?,?)',(id,datetime.datetime.now(datetime.timezone.utc).isoformat(),'unpaid'))
   if request_key is not None:c.execute('INSERT INTO requests(key,body,invoice) VALUES(?,?,?)',(request_key,encoded,id))
   return id
 def status(self,id,status):
  if status not in ['unpaid','paid','void']:raise Invalid('Status must be unpaid, paid or void.')
  with self.db() as c:
   row=c.execute('SELECT status FROM invoices WHERE id=?',(id,)).fetchone()
   if not row:raise Invalid('Invoice not found.')
   if row['status']=='void' and status!='void':raise Invalid('Voided invoices cannot be reopened.')
   if row['status']==status:return
   c.execute('UPDATE invoices SET status=? WHERE id=?',(status,id));c.execute('INSERT INTO events(invoice,at,status) VALUES(?,?,?)',(id,datetime.datetime.now(datetime.timezone.utc).isoformat(),status))
 def get(self,id):
  with self.db() as c:
   row=c.execute('SELECT * FROM invoices WHERE id=?',(id,)).fetchone()
   if not row:raise Invalid('Invoice not found.')
   return {'id':row['id'],'number':f'INV-{row["id"]:06d}','status':row['status'],**json.loads(row['body']),'events':[dict(e) for e in c.execute('SELECT at,status FROM events WHERE invoice=? ORDER BY id',(id,))]}
 def listing(self):
  with self.db() as c:return [{'id':r['id'],'number':f'INV-{r["id"]:06d}','status':r['status']} for r in c.execute('SELECT id,status FROM invoices ORDER BY id DESC')]

def time_lines(data,rate):
 """Convert completed Tempo Field rows to draft lines. Caller reviews before issue."""
 decimal(rate,Decimal('1000000'),2)
 if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('entries'),list):raise Invalid('Expected a Tempo Field version-1 JSON export.')
 result=[];seen=set()
 for e in data['entries']:
  if not isinstance(e,dict):raise Invalid('Invalid time record.')
  if e.get('end') is None:continue
  id=e.get('id')
  if type(id)!=int or id in seen:raise Invalid('Duplicate or invalid time record identifier.')
  seen.add(id);a=e.get('start');b=e.get('end')
  if type(a)!=int or type(b)!=int or not 0<=a<b or b-a>604800:raise Invalid('Invalid completed time interval.')
  quantity=(Decimal(b-a)/3600).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP)
  result.append({'description':text(e.get('note'),450)+' (time entry '+str(id)+')','quantity':str(quantity),'unit_price':rate,'seconds':b-a})
 if not 1<=len(result)<=100:raise Invalid('Import requires 1 to 100 completed time records.')
 return result
