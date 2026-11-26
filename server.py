import os,secrets,sqlite3
from flask import Flask,request,jsonify,send_from_directory,Response
from invoices import Ledger,Invalid,validate,time_lines
from pdf import render

def create_app(path,key):
 if len(key)<32:raise ValueError('SPRIG_OWNER_KEY must be at least 32 characters.')
 app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=1024*1024;ledger=Ledger(path)
 @app.before_request
 def auth():
  if request.path.startswith('/api/') and not secrets.compare_digest(request.headers.get('Authorization','').encode(),('Bearer '+key).encode()):return jsonify(error='Owner access denied.'),401
 @app.after_request
 def headers(r):
  r.headers['Cache-Control']='no-store';r.headers['X-Content-Type-Options']='nosniff';r.headers['Referrer-Policy']='no-referrer';r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'";return r
 @app.errorhandler(Invalid)
 def invalid(e):return jsonify(error=str(e)),400
 @app.errorhandler(sqlite3.Error)
 def storage(e):return jsonify(error='Storage unavailable. Retry with the same request key.'),503
 @app.errorhandler(400)
 @app.errorhandler(413)
 @app.errorhandler(415)
 def bad(e):return jsonify(error='Send a valid JSON object smaller than 1 MiB.'),e.code
 def body():
  b=request.get_json()
  if not isinstance(b,dict):raise Invalid('Send a JSON object.')
  return b
 @app.get('/')
 def index():return send_from_directory('static','index.html')
 @app.get('/api/invoices')
 def listing():return jsonify(ledger.listing())
 @app.post('/api/preview')
 def preview():
  b=validate(body());render({'number':'DRAFT','status':'draft',**b});return jsonify(b)
 @app.post('/api/invoices')
 def issue():
  b=body();req=request.headers.get('Idempotency-Key')
  if not req:raise Invalid('An Idempotency-Key is required to issue an invoice.')
  checked=validate(b);render({'number':'DRAFT','status':'draft',**checked})
  return jsonify(ledger.get(ledger.issue(b,req))),201
 @app.get('/api/invoices/<int:id>')
 def get(id):return jsonify(ledger.get(id))
 @app.post('/api/invoices/<int:id>/status')
 def status(id):ledger.status(id,body().get('status'));return jsonify(ledger.get(id))
 @app.get('/api/invoices/<int:id>/pdf')
 def pdf(id):return Response(render(ledger.get(id)),mimetype='application/pdf',headers={'Content-Disposition':f'attachment; filename="INV-{id:06d}.pdf"'})
 @app.post('/api/import-time')
 def times():
  b=body();return jsonify(lines=time_lines(b.get('source'),b.get('rate')))
 return app
if __name__=='__main__':
 os.umask(0o077);create_app(os.environ.get('SPRIG_DATABASE','invoices.sqlite3'),os.environ.get('SPRIG_OWNER_KEY','')).run(host='127.0.0.1',port=8126)
