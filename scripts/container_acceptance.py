"""Exercise unique disposable Docker resources, never an existing user ledger."""
import http.client,io,json,os,secrets,subprocess,tempfile,time,urllib.request,urllib.error
from pathlib import Path
from pypdf import PdfReader
from backup import backup
IMAGE=os.environ.get('SPRIG_TEST_IMAGE','invoice-sprig:acceptance')
tag='sprig-check-'+secrets.token_hex(6);volumes=[tag+'-source',tag+'-restore'];names=[tag+'-a',tag+'-b'];key=secrets.token_urlsafe(40)
def docker(*args):return subprocess.check_output(['docker',*args],text=True).strip()
def address(name):
 for _ in range(50):
  info=json.loads(docker('inspect',name))[0];ports=info['NetworkSettings']['Ports'].get('8126/tcp')
  if ports:return 'http://127.0.0.1:'+ports[0]['HostPort']
  if not info['State']['Running']:raise RuntimeError(docker('logs',name))
  time.sleep(.2)
 raise RuntimeError('Port mapping unavailable')
def start(name,volume):
 docker('run','-d','--name',name,'--read-only','--tmpfs','/tmp','--cap-drop','ALL','--security-opt','no-new-privileges:true','-p','127.0.0.1::8126','-v',volume+':/data','-e','SPRIG_OWNER_KEY='+key,IMAGE)
 return address(name)
def request(base,path,method='GET',body=None,request_key='recovery-request-key-0001'):
 data=None if body is None else json.dumps(body).encode()
 req=urllib.request.Request(base+'/api/'+path,data=data,method=method,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Idempotency-Key':request_key})
 with urllib.request.urlopen(req,timeout=5) as r:return r.read()
def ready(base):
 for _ in range(100):
  try:return json.loads(request(base,'invoices'))
  except (urllib.error.URLError,TimeoutError,ConnectionError,http.client.RemoteDisconnected):time.sleep(.2)
 raise RuntimeError('Container did not become ready')
def pdf_text(data):return '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
try:
 for v in volumes:docker('volume','create',v)
 a=start(names[0],volumes[0]);ready(a)
 assert docker('exec',names[0],'id','-u')=='10001'
 for asset in ['/','/static/app.js','/static/style.css']:
  with urllib.request.urlopen(a+asset,timeout=5) as r:assert r.status==200
 draft=json.loads((Path(__file__).resolve().parents[1]/'examples/draft.json').read_text())
 original=json.loads(request(a,'invoices','POST',draft));id=original['id'];path='invoices/'+str(id)
 request(a,path+'/status','POST',{'status':'paid'})
 before=request(a,path);pdf_before=pdf_text(request(a,path+'/pdf'))
 docker('restart',names[0]);a=address(names[0]);ready(a)
 assert request(a,path)==before
 assert json.loads(request(a,'invoices','POST',draft))['id']==id
 docker('stop',names[0])
 with tempfile.TemporaryDirectory() as folder:
  source=Path(folder)/'source.sqlite3';saved=Path(folder)/'backup.sqlite3'
  docker('cp',names[0]+':/data/invoices.sqlite3',str(source));backup(source,saved)
  assert saved.stat().st_mode&0o777==0o600
  try:backup(source,saved)
  except FileExistsError:pass
  else:raise AssertionError('Backup overwritten')
  docker('run','--rm','--user','0','-v',volumes[1]+':/data','-v',folder+':/backup:ro','--entrypoint','python',IMAGE,'-c',"import shutil,os; shutil.copyfile('/backup/backup.sqlite3','/data/invoices.sqlite3'); os.chown('/data',10001,10001); os.chown('/data/invoices.sqlite3',10001,10001); os.chmod('/data/invoices.sqlite3',0o600)")
 b=start(names[1],volumes[1]);ready(b)
 assert request(b,path)==before
 assert pdf_text(request(b,path+'/pdf'))==pdf_before
 assert json.loads(request(b,'invoices','POST',draft))['id']==id
 new=json.loads(request(b,'invoices','POST',draft,request_key='recovery-request-key-0002'));assert new['id']==id+1
 request(b,path+'/status','POST',{'status':'void'});assert json.loads(request(b,path))['events'][-1]['status']=='void'
 print('PASS: non-root/read-only runtime, assets, restart, private backup/clean-volume restore, exact invoice/history, PDF text, issuance deduplication, sequential numbering and fresh status writes')
finally:
 for name in names:subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 for v in volumes:subprocess.run(['docker','volume','rm',v],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
