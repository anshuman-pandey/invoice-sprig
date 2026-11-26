"""PDF output with explicit font coverage checks; no HTML execution."""
from pathlib import Path
import io
from xml.sax.saxutils import escape
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from reportlab.lib import colors
from invoices import Invalid

def render(invoice):
 path=Path(__file__).parent/'fonts'/'NotoSansSC.ttf'
 if 'Sprig' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('Sprig',str(path)))
 font=pdfmetrics.getFont('Sprig')
 for value in [invoice['seller'],invoice['customer']]+[l['description'] for l in invoice['lines']]:
  if any(ord(c) not in font.face.charToGlyph for c in value):raise Invalid('PDF font does not support a character in this invoice. Choose a supported character; emoji and complex-script shaping are not supported.')
 out=io.BytesIO();style=ParagraphStyle('text',fontName='Sprig',fontSize=10,leading=15,wordWrap='CJK');title=ParagraphStyle('title',parent=style,fontSize=25,leading=30,textColor=colors.HexColor('#245c50'))
 def para(v):return Paragraph(escape(str(v)),style)
 def money(c):return f'{c//100:,}.{c%100:02d}'
 story=[Paragraph('Invoice '+invoice['number'],title),Spacer(1,16),para('Status: '+invoice['status'].upper()+' (manually recorded)'),para('From: '+invoice['seller']),para('Bill to: '+invoice['customer']),para('Issued: '+invoice['issued']+' | Due: '+invoice['due']),para('Currency: '+invoice['currency']),Spacer(1,18)]
 rows=[[para(x) for x in ['Description','Quantity','Unit price','Amount']]]
 for line in invoice['lines']:rows.append([para(line['description']),para(line['quantity']),para(line['unit_price']),para(money(line['cents']))])
 table=Table(rows,colWidths=[260,65,75,75],repeatRows=1,hAlign='LEFT');table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6efea')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),9),('LINEBELOW',(0,0),(-1,0),1,colors.HexColor('#245c50'))]));story.extend([table,Spacer(1,16),para('Subtotal: '+money(invoice['subtotal_cents'])),para('Tax ('+invoice['tax_percent']+'%): '+money(invoice['tax_cents'])),para('Total '+invoice['currency']+': '+money(invoice['total_cents']))])
 SimpleDocTemplate(out,title=invoice['number'],author=invoice['seller'],leftMargin=60,rightMargin=60,topMargin=50,bottomMargin=50).build(story);return out.getvalue()
