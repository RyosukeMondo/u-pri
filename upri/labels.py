"""Printable, deliberately non-carrier demo labels. Never valid postage/tracking."""
import io
import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from threading import Lock

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from reportlab.graphics.barcode.code128 import Code128

from .models import Batch

_FONT_LOCK = Lock()


@lru_cache(maxsize=1)
def label_font():
    paths = [os.environ.get('UPRI_LABEL_FONT', ''),
             str(Path(__file__).parent / 'fonts/ipag.ttf'),
             '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf']
    path = next((Path(p) for p in paths if p and Path(p).is_file()), None)
    if path is None:
        raise RuntimeError('Install fonts-ipafont-gothic or set UPRI_LABEL_FONT to a Japanese TrueType font')
    with _FONT_LOCK:
        pdfmetrics.registerFont(TTFont('UpriJapanese', str(path)))
    return 'UpriJapanese'


def sample_batch():
    return Batch.model_validate({'shipments': [{
        'reference': 'DEMO-SAMPLE-001', 'ship_date': str(date(2026, 10, 24)),
        'recipient': {'name': 'サンプル 太郎（架空）', 'postal_code': '0000000',
                      'address1': 'デモ県サンプル市一丁目2番3号', 'address2': 'デモビル 101号室',
                      'phone': '0000000000'},
        'sender': {'name': 'Upri デモ発送センター', 'postal_code': '0000000',
                   'address1': 'デモ県サンプル市四丁目5番6号', 'phone': '0000000000'},
        'items': [{'name': '展示用の書籍セット', 'quantity': 1}, {'name': '展示用の文具', 'quantity': 2}]
    }]})


def _wrap(text, font, size, width):
    lines, line = [], ''
    for char in text:
        if line and pdfmetrics.stringWidth(line + char, font, size) > width:
            lines.append(line); line = ''
        line += char
    if line:
        lines.append(line)
    return lines


def render_demo_labels(batch: Batch, paper='a4') -> bytes:
    if paper not in ('a4', 'a6'):
        raise ValueError('paper must be a4 or a6')
    font = label_font()
    out = io.BytesIO()
    page_size = (210*mm, 297*mm) if paper == 'a4' else (105*mm, 148*mm)
    c = canvas.Canvas(out, pagesize=page_size, pageCompression=1)
    c.setTitle('UPRI DEMO - NOT VALID FOR SHIPPING')
    c.setAuthor('Upri')
    for index, shipment in enumerate(batch.shipments):
        x, y = (15*mm, page_size[1]-15*mm-148*mm) if paper == 'a4' else (0, 0)
        c.saveState(); c.translate(x, y)

        def text(value, left, top, size=9):
            c.setFont(font, size); c.drawString(left*mm, (148-top)*mm, str(value))

        def box_text(value, left, top, width, height, maximum, minimum=7):
            # Refuse overflow instead of dropping address/name characters.
            size = maximum
            while size >= minimum:
                lines = _wrap(str(value), font, size, width*mm)
                leading = size*1.25
                if len(lines)*leading <= height*mm:
                    for line_no, line in enumerate(lines):
                        c.setFont(font, size)
                        c.drawString(left*mm, (148-top)*mm-size-line_no*leading, line)
                    return
                size -= .5
            raise ValueError('Label text does not fit at readable size; shorten the address, name or item text')

        c.setLineWidth(.35*mm); c.rect(1*mm, 1*mm, 103*mm, 146*mm)
        c.setFillColorRGB(.08,.08,.08); c.rect(3*mm, 131*mm, 99*mm, 14*mm, fill=1, stroke=0)
        c.setFillColorRGB(1,1,1); text('DEMO', 7, 12.5, 19); text('発送不可', 68, 12, 15)
        c.setFillColorRGB(0,0,0)
        text('展示用サンプル / 郵便・宅配便には使用できません', 5, 22, 7.2)
        box_text('管理番号  '+shipment.reference, 5, 25, 95, 4.5, 8, 7)
        text('出荷予定  '+str(shipment.ship_date), 5, 34, 8)
        c.line(5*mm,113*mm,100*mm,113*mm)
        a=shipment.recipient
        text('お届け先（デモ）',5,40,8)
        text('〒 '+a.postal_code,5,46,11)
        box_text(' '.join(v for v in [a.address1,a.address2,a.address3] if v),5,48,95,14,10)
        box_text(a.name,5,63,95,11,13,8)
        text('TEL '+a.phone,5,81,8.5)
        c.line(5*mm,64*mm,100*mm,64*mm)
        a=shipment.sender
        text('ご依頼主（デモ）',5,89,7)
        box_text(a.name,5,90,95,5,9,7)
        box_text('〒 '+a.postal_code+'  '+' '.join(v for v in [a.address1,a.address2,a.address3] if v),5,96,95,10,8.5,7)
        text('TEL '+a.phone,5,110,7.5)
        c.line(5*mm,36*mm,100*mm,36*mm)
        box_text('品名  '+' / '.join(f'{item.name} × {item.quantity}' for item in shipment.items),5,114,95,12,9,7)
        code=f'DEMO-{index+1:04d}'
        barcode=Code128(code,barHeight=9*mm,barWidth=.32*mm,quiet=True)
        barcode.drawOn(c,(105*mm-barcode.width)/2,10*mm)
        text(f'{code}   展示用コード / {index+1} of {len(batch.shipments)}',24,142,7)
        text('Upri  /  105 × 148 mm  /  NOT VALID FOR SHIPPING',12,146,5.8)
        c.restoreState()
        if paper=='a4':
            # A true A6 cut boundary, with marks outside the content border.
            c.setDash(2,2);c.setLineWidth(.25);c.rect(x,y,105*mm,148*mm);c.setDash()
            c.setFont(font,11);c.drawString(15*mm,y-13*mm,'DEMOラベル：枠に沿って切り取り、展示用の荷物に貼付')
            c.setFont(font,9);c.drawString(15*mm,y-21*mm,'印刷設定：A4・倍率100%（実際のサイズ）。「用紙に合わせる」はオフ。')
            c.drawString(15*mm,y-28*mm,'ラベル寸法：105 × 148 mm（A6）。このラベルで実際の発送はできません。')
            c.setLineWidth(.5);c.line(15*mm,y-40*mm,65*mm,y-40*mm)
            for xx in (15,65):c.line(xx*mm,y-42*mm,xx*mm,y-38*mm)
            c.setFont(font,8);c.drawString(15*mm,y-47*mm,'寸法確認用：この線が 50 mm なら倍率は正しい設定です。')
        c.showPage()
    c.save()
    return out.getvalue()
