# -*- coding: utf-8 -*-
"""Mixi, the Mixsmith mascot: a small round sound creature with headphones, drawn with QPainter (no image assets).

draw(p, cx, cy, size, t, mouth=0..1, blink=0..1, pose="talk"|"wave"|"point", point_to=(x, y) or None)
(cx, cy) is the bottom centre (where the feet touch the ground), size the body height in pixels."""
import math
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient, QLinearGradient, QPainterPath

TEAL_T, TEAL_B, TEAL_D = QColor("#6fe6ef"), QColor("#23a3b4"), QColor("#157382")
VIOLET, AMBER, AMBER_D, INK, PINK = QColor("#8b7cf6"), QColor("#f7b53b"), QColor("#d98c14"), QColor("#10202a"), QColor(255, 128, 160)

def _blob(r):
    """Soft rounded body (slightly pear-shaped)."""
    x, y, w, h = r.x(), r.y(), r.width(), r.height(); p = QPainterPath()
    p.moveTo(x+w*0.5, y)
    p.cubicTo(x+w*0.92, y, x+w*1.02, y+h*0.45, x+w*0.98, y+h*0.70)
    p.cubicTo(x+w*0.95, y+h*0.95, x+w*0.75, y+h, x+w*0.5, y+h)
    p.cubicTo(x+w*0.25, y+h, x+w*0.05, y+h*0.95, x+w*0.02, y+h*0.70)
    p.cubicTo(x-w*0.02, y+h*0.45, x+w*0.08, y, x+w*0.5, y)
    return p

def _arm(p, base, angle_deg, length, width, color):
    a = math.radians(angle_deg); tip = QPointF(base.x()+math.cos(a)*length, base.y()+math.sin(a)*length)
    pen = QPen(color, width, Qt.SolidLine, Qt.RoundCap); p.setPen(pen); p.drawLine(base, tip)
    p.setPen(Qt.NoPen); p.setBrush(color); p.drawEllipse(tip, width*0.62, width*0.62)
    return tip

def draw(p, cx, cy, size, t, mouth=0.0, blink=0.0, pose="talk", point_to=None, facing=1):
    p.save(); p.setRenderHint(QPainter.Antialiasing)
    bob = math.sin(t*2.4)*size*0.025 + (mouth*size*0.02)                 # breathing, a little bounce while speaking
    squash = 1.0 + 0.03*math.sin(t*4.8) + 0.04*mouth
    H = size*squash; W = size*1.05/squash**0.5
    top = cy-H-size*0.10-bob; body = QRectF(cx-W/2, top, W, H)
    # ground shadow
    sh = QRadialGradient(QPointF(cx, cy), W*0.55); sh.setColorAt(0, QColor(0, 0, 0, 110)); sh.setColorAt(1, QColor(0, 0, 0, 0))
    p.setPen(Qt.NoPen); p.setBrush(sh); p.drawEllipse(QPointF(cx, cy), W*0.55, size*0.07)
    # feet
    for s in (-1, 1):
        p.setBrush(TEAL_D); p.drawEllipse(QPointF(cx+s*W*0.2, cy-size*0.07-bob*0.3), W*0.14, size*0.07)
    # arms behind/at the sides
    shoulder_l = QPointF(cx-W*0.44, top+H*0.62); shoulder_r = QPointF(cx+W*0.44, top+H*0.62)
    arm_w = size*0.085; front = None                      # the gesturing arm is drawn in front of the body
    if pose == "wave":
        front = (QPointF(cx+W*0.40, top+H*0.55), -50+28*math.sin(t*7.0), size*0.42)
        _arm(p, shoulder_l, 125, size*0.22, arm_w, TEAL_B)
    elif pose == "point" and point_to is not None:
        right = point_to[0] >= cx; side = QPointF(cx+(1 if right else -1)*W*0.40, top+H*0.58)
        ang = math.degrees(math.atan2(point_to[1]-side.y(), point_to[0]-side.x()))
        front = (side, ang+3*math.sin(t*5), size*0.45)
        _arm(p, shoulder_r if not right else shoulder_l, 60 if not right else 120, size*0.22, arm_w, TEAL_B)
    else:
        sw = 6*math.sin(t*3.0)
        _arm(p, shoulder_l, 125+sw, size*0.23, arm_w, TEAL_B); _arm(p, shoulder_r, 55-sw, size*0.23, arm_w, TEAL_B)
    # body
    g = QLinearGradient(body.topLeft(), body.bottomLeft()); g.setColorAt(0, TEAL_T); g.setColorAt(1, TEAL_B)
    p.setBrush(g); p.setPen(QPen(TEAL_D, size*0.018)); p.drawPath(_blob(body))
    belly = QRectF(cx-W*0.26, top+H*0.52, W*0.52, H*0.40); bg = QColor(255, 255, 255, 60); p.setPen(Qt.NoPen); p.setBrush(bg); p.drawEllipse(belly)
    # a little equalizer on the belly (the logo's bars)
    bars = [0.35, 0.6, 1.0, 0.6, 0.35]; bw = W*0.035
    for i, b in enumerate(bars):
        hh = H*0.16*b*(0.7+0.3*abs(math.sin(t*5+i))) if mouth > 0.05 else H*0.16*b*0.7
        x = cx+(i-2)*bw*1.9-bw/2; c = AMBER if i == 2 else QColor(255, 255, 255, 200)
        p.setBrush(c); p.drawRoundedRect(QRectF(x, belly.center().y()-hh/2, bw, hh), bw/2, bw/2)
    # shine
    p.setBrush(QColor(255, 255, 255, 70)); p.drawEllipse(QRectF(cx-W*0.34, top+H*0.10, W*0.20, H*0.12))
    # eyes
    ey = top+H*0.36; ex = W*0.18; look = 0.0
    if point_to is not None and pose == "point": look = max(-1, min(1, (point_to[0]-cx)/400.0))
    for s in (-1, 1):
        ecx = cx+s*ex; rw, rh = W*0.13, H*0.155*(1-0.92*blink)
        p.setBrush(QColor("white")); p.setPen(QPen(TEAL_D, size*0.01)); p.drawEllipse(QPointF(ecx, ey), rw, rh)
        if blink < 0.6:
            p.setPen(Qt.NoPen); p.setBrush(INK); pr = rw*0.62
            pc = QPointF(ecx+look*rw*0.28+facing*rw*0.05, ey+rh*0.12); p.drawEllipse(pc, pr, min(pr*1.1, rh*0.85))
            p.setBrush(QColor("white")); p.drawEllipse(QPointF(pc.x()-pr*0.35, pc.y()-pr*0.38), pr*0.34, pr*0.34)
            p.drawEllipse(QPointF(pc.x()+pr*0.30, pc.y()+pr*0.30), pr*0.14, pr*0.14)
    # cheeks
    ck = QColor(PINK); ck.setAlpha(110); p.setBrush(ck); p.setPen(Qt.NoPen)
    for s in (-1, 1): p.drawEllipse(QPointF(cx+s*W*0.30, top+H*0.50), W*0.075, H*0.042)
    # mouth
    my = top+H*0.50; mw = W*0.13
    if mouth < 0.08:
        pen = QPen(INK, size*0.022, Qt.SolidLine, Qt.RoundCap); p.setPen(pen); p.setBrush(Qt.NoBrush)
        path = QPainterPath(); path.moveTo(cx-mw*0.6, my); path.quadTo(cx, my+H*0.06, cx+mw*0.6, my); p.drawPath(path)
    else:
        mh = H*(0.035+0.11*mouth); p.setPen(Qt.NoPen); p.setBrush(INK)
        path = QPainterPath(); path.moveTo(cx-mw*0.7, my); path.quadTo(cx, my-mh*0.25, cx+mw*0.7, my); path.quadTo(cx+mw*0.6, my+mh, cx, my+mh); path.quadTo(cx-mw*0.6, my+mh, cx-mw*0.7, my)
        p.drawPath(path); p.setBrush(PINK); p.drawEllipse(QPointF(cx, my+mh*0.72), mw*0.34, mh*0.24)
    # headphones: band over the head, amber cups at the sides
    band = QRectF(cx-W*0.56, top-H*0.10, W*1.12, H*0.90)
    p.setBrush(Qt.NoBrush); p.setPen(QPen(VIOLET, size*0.07, Qt.SolidLine, Qt.RoundCap)); p.drawArc(band, 20*16, 140*16)
    p.setPen(QPen(QColor(255, 255, 255, 80), size*0.018, Qt.SolidLine, Qt.RoundCap)); p.drawArc(band.adjusted(W*0.05, H*0.03, -W*0.05, 0), 70*16, 50*16)
    for s in (-1, 1):
        cup = QRectF(cx+s*W*0.50-W*0.09, top+H*0.24, W*0.18, H*0.30)
        cg = QLinearGradient(cup.topLeft(), cup.bottomLeft()); cg.setColorAt(0, AMBER); cg.setColorAt(1, AMBER_D)
        p.setPen(QPen(QColor("#a86a0a"), size*0.012)); p.setBrush(cg); p.drawRoundedRect(cup, W*0.07, W*0.07)
    if front is not None:
        tip = _arm(p, front[0], front[1], front[2], arm_w*1.05, TEAL_B)
        p.setPen(QPen(TEAL_D, size*0.012)); p.setBrush(TEAL_T); p.drawEllipse(tip, arm_w*0.7, arm_w*0.7)
    # a tiny floating note while talking
    if mouth > 0.1 or pose == "wave":
        ph = (t*0.6) % 1.0; nx = cx+W*0.62+ph*size*0.15; ny = top-ph*size*0.35; a = int(255*(1-ph))
        c = QColor(AMBER); c.setAlpha(a); p.setPen(QPen(c, size*0.02, Qt.SolidLine, Qt.RoundCap)); p.setBrush(c)
        p.drawEllipse(QPointF(nx, ny), size*0.035, size*0.028); p.drawLine(QPointF(nx+size*0.033, ny), QPointF(nx+size*0.033, ny-size*0.11))
    p.restore()

if __name__ == "__main__":
    import sys
    from PySide6.QtGui import QImage, QGuiApplication
    app = QGuiApplication(sys.argv)
    img = QImage(1500, 420, QImage.Format_ARGB32); img.fill(QColor("#0d1117")); p = QPainter(img)
    for i, (pose, mouth, blink) in enumerate((("talk", 0.0, 0.0), ("talk", 0.8, 0.0), ("wave", 0.3, 0.0), ("point", 0.5, 0.0), ("talk", 0.0, 1.0))):
        draw(p, 150+i*300, 390, 250, 1.3+i, mouth, blink, pose, point_to=(1500, 0) if pose == "point" else None)
    p.end(); out = sys.argv[1] if len(sys.argv) > 1 else "mascot_preview.png"; img.save(out); print(out)
