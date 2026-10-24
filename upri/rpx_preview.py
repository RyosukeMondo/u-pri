"""Static RPX specimen renderer. Never executes embedded scripts or vendor DLLs.

Template paths are local inputs, not bundled proprietary resources. Output is
always watermarked and uses non-scannable barcode placeholders.
"""
from __future__ import annotations
import io,json,re,hashlib
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

TWIP_TO_PT=1/20
SAMPLE={
 'receiver_zip':'000-0000','receiver_adr_1':'サンプル県サンプル市','receiver_adr_2':'架空町1-2-3','receiver_nm_1':'サンプル 太郎','receiver_tel':'000-0000-0000',
 'kokyaku_zip':'000-0000','kokyaku_adr_1':'サンプル県サンプル市','kokyaku_adr_2':'架空町4-5-6','kokyaku_nm_1':'デモ発送センター','kokyaku_tel':'000-0000-0000',
 'todoke_keisho_kbn_nm':'様','shohin_nm001':'書籍（展示用・発送不可）','shohin_cnt001':'1',
 'item_cnt_bunshi':'1','item_cnt_bunbo':'1','tracking_no_fmt':'DEMO-NOT-VALID',
 'syuka_ymd':'2026/10/24','order_no':'DEMO-0001','ittai_shohin_nm1':'書籍（展示用）','ittai_shohin_cnt1':'1',
}
def styles(value):return {k.strip():v.strip() for k,v in (x.split(':',1) for x in value.split(';') if ':' in x)}
def css_color(value):
 value=value.strip().lower()
 named={'black':(0,0,0),'white':(1,1,1),'red':(1,0,0),'blue':(0,0,1)}
 if value in named:return named[value]
 rgb=re.fullmatch(r'rgb\((\d+),(\d+),(\d+)\)',value.replace(' ',''))
 if rgb:return tuple(int(x)/255 for x in rgb.groups())
 return None
def color(value):
 try:
  n=int(value);return ((n&255)/255,((n>>8)&255)/255,((n>>16)&255)/255)
 except (ValueError,TypeError):return (0,0,0)
def decode_image(text):
 raw=bytes.fromhex(''.join((text or '').split()))
 for signature in (b'\x89PNG\r\n\x1a\n',b'\xff\xd8\xff',b'BM',b'GIF8'):
  pos=raw.find(signature)
  if pos>=0:
   image=Image.open(io.BytesIO(raw[pos:]));image.load();return image
 raise ValueError('Unsupported RPX image payload')
def render(template:Path, output:Path, font:Path):
 raw=template.read_bytes()
 if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('DTD/entities not supported')
 root=ET.fromstring(raw);ps=root.find('PageSettings')
 if ps is None:raise ValueError('Missing page settings')
 detail_node=root.find("./Sections/Section[@Type='Detail']")
 explicit=bool(ps.get('PaperWidth') and ps.get('PaperHeight'))
 width=float(ps.get('PaperWidth') or root.get('PrintWidth','11906'))/20
 height=float(ps.get('PaperHeight') or (detail_node.get('Height') if detail_node is not None else '16838'))/20
 if width<=0 or height<=0:raise ValueError('No positive page/layout dimensions')
 if ps.get('Orientation')=='2':width,height=max(width,height),min(width,height)
 pdfmetrics.registerFont(TTFont('SpecimenJP',str(font)))
 output.parent.mkdir(parents=True,exist_ok=True)
 pdf=canvas.Canvas(str(output),pagesize=(width,height));pdf.setTitle('RPX static specimen — NOT FOR SHIPPING')
 controls=[];unsupported=Counter();clipped=[];images=0
 section=root.find("./Sections/Section[@Type='Detail']")
 if section is None:raise ValueError('No detail section')
 def measure(c,key,default='0'):return float(c.get(key,default))/20
 def text_in_box(text,x,y,w,h,style,name):
  if not text or w<=0 or h<=0:return
  size=float(re.sub('[^0-9.]','',style.get('font-size','10pt')) or 10)
  pdf.saveState();path=pdf.beginPath();path.rect(x,y,w,h);pdf.clipPath(path,stroke=0)
  pdf.setFillColorRGB(*(css_color(style.get('color','black')) or (0,0,0)));pdf.setFont('SpecimenJP',size)
  if style.get('ddo-font-vertical','').strip()=='true':
   if len(text)*size>h:clipped.append(name)
   for i,ch in enumerate(text):pdf.drawString(x+(w-size)/2,y+h-size*(i+1),ch)
  else:
   # Static layout: preserve font size and clip/wrap; no VB resize routines.
   lines=['']
   for ch in text:
    if ch=='\n':lines.append('');continue
    if lines[-1] and pdfmetrics.stringWidth(lines[-1]+ch,'SpecimenJP',size)>w:
     lines.append('')
    lines[-1]+=ch
   if len(lines)*size*1.08>h:clipped.append(name)
   baseline=y+h-size
   if style.get('vertical-align','').strip()=='middle':baseline=y+(h+len(lines)*size*1.08)/2-size
   for line in lines:
    align=style.get('text-align','').strip()
    if align=='center':pdf.drawCentredString(x+w/2,baseline,line)
    elif align=='right':pdf.drawRightString(x+w,baseline,line)
    else:pdf.drawString(x,baseline,line)
    baseline-=size*1.08
  pdf.restoreState()
 for c in section.findall('Control'):
  a=c.attrib;ty=a.get('Type','');name=a.get('Name','');controls.append(a)
  if a.get('Visible')=='0':continue
  x=measure(c,'Left');top=measure(c,'Top');w=measure(c,'Width');h=measure(c,'Height');y=height-top-h
  pdf.setStrokeColorRGB(0,0,0);pdf.setLineWidth(float(a.get('LineWeight','.5')))
  if ty=='AR.Image':
   if (c.text or '').strip():
    pdf.drawImage(ImageReader(decode_image(c.text)),x,y,w,h,mask='auto');images+=1
  elif ty=='AR.Line':
   pdf.line(measure(c,'X1'),height-measure(c,'Y1'),measure(c,'X2'),height-measure(c,'Y2'))
  elif ty=='AR.Shape':
   pdf.setFillColorRGB(*color(a.get('BackColor','16777215')))
   pdf.roundRect(x,y,w,h,min(float(a.get('RoundingRadius','0')),w/2,h/2),stroke=1,fill=1 if a.get('BackStyle')=='1' else 0)
  elif ty=='AR.Barcode':
   pdf.setFillColorRGB(.94,.94,.94);pdf.rect(x,y,w,h,stroke=1,fill=1)
   pdf.setStrokeColorRGB(.6,.6,.6);pdf.line(x,y,x+w,y+h);pdf.line(x,y+h,x+w,y)
   text_in_box('DEMO\n読取不可',x,y,w,h,{'font-size':'7pt','text-align':'center','vertical-align':'middle'},name)
  elif ty in ('AR.Field','AR.Label'):
   st=styles(a.get('Style',''))
   bg=css_color(st.get('background-color',''))
   if bg is not None:
    pdf.setFillColorRGB(*bg);pdf.rect(x,y,w,h,stroke=0,fill=1)
   if 'BackColor' in a:
    pdf.setFillColorRGB(*color(a['BackColor']));pdf.rect(x,y,w,h,stroke=0,fill=1)
   pdf.setLineWidth(.5)
   for edge,pts in [('Left',(x,y,x,y+h)),('Right',(x+w,y,x+w,y+h)),('Top',(x,y+h,x+w,y+h)),('Bottom',(x,y,x+w,y))]:
    if a.get('Border'+edge+'Style','0')!='0':pdf.line(*pts)
   datafield=a.get('DataField')
   text=SAMPLE.get(datafield,'') if datafield else a.get('Text',a.get('Caption',''))
   text_in_box(text,x,y,w,h,st,name)
  else:unsupported[ty]+=1
 # Every page visibly invalid for postage, independent of template contents.
 pdf.saveState();pdf.translate(width/2,height/2);pdf.rotate(24);pdf.setFillColorRGB(.8,.15,.12);pdf.setFillAlpha(.23)
 pdf.setFont('SpecimenJP',39);pdf.drawCentredString(0,0,'DEMO / 発送不可');pdf.restoreState()
 pdf.setFillColorRGB(1,1,.92);pdf.rect(0,0,width,19,stroke=0,fill=1)
 pdf.setFillColorRGB(.6,.1,.1);pdf.setFont('SpecimenJP',7)
 pdf.drawString(8,7,'実RPXの静的再現・本体出力ではありません／VBスクリプト未実行／フォント代替／番号・バーコードは無効')
 pdf.showPage();pdf.save()
 spec={'template':template.name,'sha256':hashlib.sha256(raw).hexdigest(),'units':'twips (1440/in)','page_dimensions_source':'explicit RPX paper dimensions' if explicit else 'layout bounds fallback; paper size not established','page_mm':[round(width*25.4/72,4),round(height*25.4/72,4)],'detail_mm':[round(float(root.get('PrintWidth'))*25.4/1440,4),round(float(section.get('Height'))*25.4/1440,4)],'controls':dict(Counter(c['Type'] for c in controls)),'embedded_images_rendered':images,'unsupported_control_types':dict(unsupported),'limitations':['Embedded VB scripts and expressions are not executed','Conditional visibility and autosizing are not reproduced','OutputFormat and line/shape variants are not fully implemented','Font metrics use IPA Gothic; not original MS fonts','Only a single static Detail section is rendered','Text may be clipped within template boxes'],'text_height_overflow':clipped,'scripts_executed':False,'vendor_dll_executed':False,'font_substitution':'IPA Gothic replaces original template fonts','barcode_mode':'non-scannable crossed placeholders','datafields':sorted({c['DataField'] for c in controls if 'DataField' in c})}
 output.with_suffix('.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2))
 return spec
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('template',type=Path);p.add_argument('output',type=Path);p.add_argument('--font',type=Path,default=Path('/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'))
 args=p.parse_args();print(json.dumps(render(args.template,args.output,args.font),ensure_ascii=False,indent=2))
