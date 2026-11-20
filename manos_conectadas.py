"""Manos conectadas — "red string theory" en ASCII. Solo librería estándar.

Uso:  python manos_conectadas.py     (maximiza la ventana; Ctrl+C para salir)
"""
import math
import os
import shutil
import sys
import time

FPS = 24
WORLD_W, WORLD_H = 124, 104          # mundo en unidades; 1 columna = 1 unidad, 1 fila = 2 unidades
RED, PINK, WHITE, LIGHT, GRAY, DIM = 196, 210, 231, 252, 246, 240
BLUES = (17, 18, 19, 20, 26, 32, 39, 45)

# Tiempos de la animación (segundos)
T_ENTER, T_SAG, T_RISE, T_LOOP = 2.0, 1.5, 3.5, 16.0


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


# ---------------- manos (SDF: distancia con signo, < 0 = dentro) ----------------
def capsule(px, py, ax, ay, bx, by, r):
    dx, dy, ex, ey = px - ax, py - ay, bx - ax, by - ay
    t = max(0.0, min(1.0, (dx * ex + dy * ey) / (ex * ex + ey * ey)))
    return math.hypot(dx - ex * t, dy - ey * t) - r


def finger(px, py, ax, ay, bx, by, r0, r1):
    """Cápsula que se afina de r0 (base) a r1 (punta)."""
    dx, dy, ex, ey = px - ax, py - ay, bx - ax, by - ay
    t = max(0.0, min(1.0, (dx * ex + dy * ey) / (ex * ex + ey * ey)))
    return math.hypot(dx - ex * t, dy - ey * t) - (r0 + (r1 - r0) * t)


def ellipse(px, py, cx, cy, rx, ry):
    return (math.hypot((px - cx) / rx, (py - cy) / ry) - 1) * min(rx, ry)


HAND_Y = 8                           # baja/sube ambas manos
PALM = (-47, -36 + HAND_Y, 12)       # centro y radio de la palma (mano izquierda)


def _finger(angle_deg, length, r0, r1, bend=0.0):
    """Dedo que nace en el borde de la palma, en abanico. bend curva un poco la punta."""
    cx, cy, pr = PALM
    a = math.radians(angle_deg)
    bx, by = cx + math.cos(a) * pr * 0.7, cy + math.sin(a) * pr * 0.7
    a2 = a + math.radians(bend)
    tx, ty = bx + math.cos(a2) * length, by + math.sin(a2) * length
    return (finger, (bx, by, tx, ty, r0, r1)), (tx, ty)


_pinky, PINKY_TIP = _finger(64, 18, 2.4, 1.9, -6)
HAND = [
    (capsule, (-95, PALM[1] - 3, -58, PALM[1] - 1, 5.5)),      # antebrazo
    (ellipse, (PALM[0], PALM[1], PALM[2], PALM[2] * 0.85)),    # palma
    _pinky,                                                    # meñique levantado (lleva el hilo)
    _finger(38, 21, 2.7, 2.1, -12)[0],                         # anular
    _finger(12, 25, 2.8, 2.2, -6)[0],                           # medio
    _finger(-14, 22, 2.8, 2.1, 0)[0],                          # índice
    _finger(-55, 17, 3.3, 2.4, 30)[0],                         # pulgar
]


def hand_sdf(x, y):
    return min(f(x, y, *a) for f, a in HAND)


def render_hand(k, cols, rows):
    """Dibuja la mano izquierda una vez: contorno con trazos según la forma + relleno tenue.
    Devuelve {(col relativo al centro, fila): (char, color)}."""
    half = cols // 2
    world = lambda c, r: ((c - cols / 2) / k, (rows / 2 - r) * 2 / k)
    d = {(c, r): hand_sdf(*world(c, r)) for r in range(rows) for c in range(half + 2)}
    cells = {}
    for (c, r), v in d.items():
        if v >= 0 or c > half:
            continue
        if any(d.get(n, 1) >= 0 for n in ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1))):
            x, y = world(c, r)
            e = 0.05
            gx = hand_sdf(x + e, y) - hand_sdf(x - e, y)
            gy = hand_sdf(x, y + e) - hand_sdf(x, y - e)
            ch = slope_char(-gy, gx)
            if ch == "-" and gy < 0:
                ch = "_"                                   # borde inferior
            cells[(c - half, r)] = (ch, WHITE)
        else:
            depth = -v                                     # relleno tenue: el contorno manda
            cells[(c - half, r)] = ("." if depth < 2 else ":", DIM if depth < 4 else GRAY)
    return cells


# ---------------- hilo ----------------
HEART_DY = 32


def heart(t, s):
    x = 16 * math.sin(t) ** 3
    y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
    return x * s, y * s + HEART_DY


def heart_path(s, n=320):
    """Meñique izq -> cruce en X -> corazón -> cruce -> meñique der. Devuelve [(x, y, es_corazón)]."""
    t0 = 0.78 * math.pi

    def strand(side):
        sx, sy = PINKY_TIP[0] * side, PINKY_TIP[1]
        hx, hy = heart(t0, s)
        hx *= -side                                        # sube por el lado contrario -> X
        c1, c2 = (sx * 0.55, sy + 14), (hx * 1.6, hy - 10)
        pts = []
        for i in range(n):
            u = i / n
            a, b, c, d = (1 - u) ** 3, 3 * u * (1 - u) ** 2, 3 * u * u * (1 - u), u ** 3
            pts.append((a * sx + b * c1[0] + c * c2[0] + d * hx, a * sy + b * c1[1] + c * c2[1] + d * hy, False))
        for i in range(n + 1):
            x, y = heart(t0 * (1 - i / n), s)
            pts.append((-x * side, y, True))
        return pts

    return strand(1) + strand(-1)[::-1]


def sag_path(n, offset):
    lx, rx, y = PINKY_TIP[0] - offset, -PINKY_TIP[0] + offset, PINKY_TIP[1]
    return [(lx + (rx - lx) * u, y - 15 * math.sin(math.pi * u), False)
            for u in (i / (n - 1) for i in range(n))]


def slope_char(dx, dy):
    a = math.degrees(math.atan2(dy, dx)) % 180
    return "-" if a < 22 or a >= 158 else "/" if a < 68 else "|" if a < 112 else "\\"


# ---------------- cuadro ----------------
class Screen:
    def __init__(self):
        self.size = None

    def setup(self):
        cols, rows = shutil.get_terminal_size((120, 40))
        rows -= 1
        if (cols, rows) != self.size:
            self.size = cols, rows
            self.k = min(cols / WORLD_W, rows * 2 / WORLD_H)       # escala uniforme, se ajusta a la ventana
            self.hand = render_hand(self.k, cols, rows)
            sys.stdout.write("\x1b[2J")

    def to_cell(self, x, y):
        cols, rows = self.size
        return int(round(cols / 2 + x * self.k)), int(round(rows / 2 - y * self.k / 2))

    def frame(self, t):
        cols, rows = self.size
        chars = [[" "] * cols for _ in range(rows)]
        color = [[0] * cols for _ in range(rows)]

        def put(c, r, ch, col):
            if 0 <= c < cols and 0 <= r < rows:
                chars[r][c], color[r][c] = ch, col

        enter = 1 - ease(t / T_ENTER)                      # 1 -> 0 mientras las manos entran
        offset = enter * 45                                # unidades del mundo
        t_rise = t - T_ENTER - T_SAG
        rise = ease(t_rise / T_RISE)
        formed = max(0.0, t_rise - T_RISE)

        # destellos azules detrás del corazón
        if rise > 0.3:
            glow = min(1.0, (rise - 0.3) / 0.7) * (0.8 + 0.2 * math.sin(t * 3))
            cx, cy = 0, HEART_DY - 4
            for k, (length, ch, step) in enumerate(((60, "-", 1), (30, ".", 2), (40, ":", 1), (30, ".", 2)) * 2):
                ang = k * math.pi / 4
                for r in range(3, int(length * glow), step):
                    fade = 1 - r / (length * glow)
                    put(*self.to_cell(cx + math.cos(ang) * r, cy + math.sin(ang) * r), ch,
                        BLUES[int(fade * glow * (len(BLUES) - 1))])
            for i in range(70):                            # chispas que titilan
                if math.sin(t * 2.5 + i * 1.7) > 0.55:
                    ang, r = i * 2.39996, 6 + (i * 7.31) % 34
                    put(*self.to_cell(cx + math.cos(ang) * r * 1.3, cy + math.sin(ang) * r),
                        "+" if i % 5 == 0 else ".", BLUES[4 + i % 4])

        # manos (pre-renderizadas, solo se desplazan)
        shift = int(round(offset * self.k))
        for (c, r), (ch, col) in self.hand.items():
            put(cols // 2 + c - shift, r, ch, col)
            mirror = {"/": "\\", "\\": "/"}.get(ch, ch)
            put(cols // 2 - c - 1 + shift - (cols % 2 == 0), r, mirror, col)

        # hilo: cuelga entre los meñiques y luego sube formando el corazón
        if t > T_ENTER * 0.6:
            beat = 1 + 0.07 * max(0.0, math.sin(formed * 5)) ** 10 if formed else 1
            target = heart_path(0.35 + 0.85 * rise)
            sag = sag_path(len(target), offset)
            show = min(1.0, (t - T_ENTER * 0.6) / T_SAG)   # el hilo se "desenrolla" al principio
            last = max(2, int(len(target) * show))
            prev = None
            for i in range(last):
                hx, hy, is_heart = target[i]
                x = sag[i][0] + (hx - sag[i][0]) * rise
                y = sag[i][1] + (hy - sag[i][1]) * rise
                if is_heart and formed:
                    x, y = x * beat, HEART_DY + (y - HEART_DY) * beat
                if prev:
                    put(*self.to_cell(x, y), slope_char(x - prev[0], (y - prev[1]) / 2), RED if i % 9 else PINK)
                prev = (x, y)

        out = []
        for r in range(rows):
            line, cur = [], None
            for c in range(cols):
                if color[r][c] != cur:
                    cur = color[r][c]
                    line.append(f"\x1b[38;5;{cur}m" if cur else "\x1b[0m")
                line.append(chars[r][c])
            out.append("".join(line) + "\x1b[0m")
        return "\n".join(out)


def main():
    os.system("")                                          # activa colores ANSI en Windows
    sys.stdout.write("\x1b[?25l")
    screen, start = Screen(), time.time()
    try:
        while True:
            screen.setup()
            t = (time.time() - start) % T_LOOP
            sys.stdout.write("\x1b[H" + screen.frame(t))
            sys.stdout.flush()
            time.sleep(1 / FPS)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[0m\x1b[?25h\n")


if __name__ == "__main__":
    main()
