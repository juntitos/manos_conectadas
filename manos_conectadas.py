"""Red string theory — animación ASCII en la terminal. Solo librería estándar.

Uso:  python red_string.py      (Ctrl+C para salir)
"""
import math
import os
import sys
import time

W, H = 110, 44          # tamaño en caracteres
FPS = 30
RED, PINK, WHITE, GRAY = 196, 203, 255, 245
BLUES = (17, 18, 19, 20, 27, 33, 39)

# Espacio de dibujo: x = columnas, y = filas*2 (las celdas de la terminal son el doble de altas).
def to_cell(x, y):
    return int(round(W / 2 + x)), int(round(H / 2 - y / 2))


# ---------- figuras (SDF: distancia con signo, <0 = dentro) ----------
def capsule(px, py, ax, ay, bx, by, r):
    dx, dy, ex, ey = px - ax, py - ay, bx - ax, by - ay
    t = max(0.0, min(1.0, (dx * ex + dy * ey) / (ex * ex + ey * ey)))
    return math.hypot(dx - ex * t, dy - ey * t) - r


def ellipse(px, py, cx, cy, rx, ry):
    return (math.hypot((px - cx) / rx, (py - cy) / ry) - 1) * min(rx, ry)


def hand_parts(px, py, side, sway):
    """Partes de la mano izquierda (side=1) o derecha (side=-1, espejo), dedos hacia el centro."""
    x, y = px * side, py - sway
    return (
        capsule(x, y, -62, -22, -47, -23, 5.5),         # antebrazo
        ellipse(x, y, -41, -23, 7, 8),                  # palma
        capsule(x, y, -38, -13, -32, -9, 2.3),          # pulgar
        capsule(x, y, -36, -16.5, -26, -16.5, 2.2),     # índice
        capsule(x, y, -36, -21, -24, -21, 2.2),         # medio
        capsule(x, y, -36, -25.5, -25, -25.5, 2.2),     # anular
        capsule(x, y, -37, -30, -22, -31, 1.9),         # meñique extendido (lleva el hilo)
    )


# ---------- hilo: meñique -> cruce -> mitad del corazón ----------
HEART_S, HEART_DY = 1.5, 12


def heart(t, s=HEART_S):
    x = 16 * math.sin(t) ** 3
    y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
    return x * s, y * s + HEART_DY


def strand(side, n=400):
    """Hilo que sale del meñique de un lado, cruza al centro y sube por la mitad opuesta del corazón."""
    t0 = 0.8 * math.pi
    sx, sy = -20 * side, -31                       # punta del meñique
    hx, hy = heart(t0)
    hx *= side                                     # entra por el lado contrario -> cruce en X
    c1, c2 = (-6 * side, -38), (hx * 0.2, -30)     # controles de la curva
    pts = []
    for i in range(n // 2):                        # bezier cúbica hasta el corazón
        u = i / (n // 2)
        a, b, c, d = (1 - u) ** 3, 3 * u * (1 - u) ** 2, 3 * u * u * (1 - u), u ** 3
        pts.append((a * sx + b * c1[0] + c * c2[0] + d * hx, a * sy + b * c1[1] + c * c2[1] + d * hy))
    for i in range(n // 2 + 1):                    # mitad del corazón, de abajo hacia la muesca superior
        hx2, hy2 = heart(t0 * (1 - i / (n // 2)))
        pts.append((hx2 * side, hy2))
    return pts


STRANDS = [strand(1), strand(-1)]


def slope_char(x0, y0, x1, y1):
    a = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180
    return "-" if a < 22 or a >= 158 else "/" if a < 68 else "|" if a < 112 else "\\"


# ---------- render ----------
def frame(t):
    chars = [[" "] * W for _ in range(H)]
    color = [[0] * W for _ in range(H)]

    def put(cx, cy, ch, col):
        if 0 <= cx < W and 0 <= cy < H:
            chars[cy][cx], color[cy][cx] = ch, col

    draw_time = 4.0                                 # segundos que tarda el hilo en dibujarse
    progress = min(1.0, t / draw_time)
    done = max(0.0, t - draw_time)
    beat = 1 + 0.06 * max(0.0, math.sin(done * 6)) ** 8 if done else 1

    # destellos azules alrededor del corazón
    if done:
        glow = min(1.0, done / 1.5)
        cx, cy = 0, HEART_DY - 6
        for k in range(16):
            ang = k * math.pi / 8 + done * 0.15
            length = (16 + 10 * math.sin(done * 2 + k * 1.7)) * glow
            for r in range(29, int(29 + length)):
                fade = 1 - (r - 29) / max(1.0, length)
                put(*to_cell(cx + math.cos(ang) * r, cy + math.sin(ang) * r * 0.9),
                    "." if fade < 0.5 else ":", BLUES[int(fade * (len(BLUES) - 1))])

    # manos: contorno de cada parte (así se separan los dedos) + relleno tenue
    sway = math.sin(t * 1.3) * 0.8
    for row in range(H):
        for col in range(W):
            x, y = col - W / 2, (H / 2 - row) * 2
            for side in (1, -1):
                ds = hand_parts(x, y, side, sway)
                inside = sorted(ds)
                if any(abs(d) < 0.7 for d in ds) and not (len(inside) > 1 and inside[0] < -0.8 and
                                                          sum(d < 0.7 for d in ds) == 1):
                    put(col, row, ":" if min(ds) < 0 else ".", WHITE)
                elif min(ds) < 0:
                    put(col, row, "." if (col + row) % 3 == 0 else " ", GRAY)

    # hilo rojo (con latido una vez terminado)
    for pts in STRANDS:
        last = max(2, int(len(pts) * progress))
        for i in range(1, last):
            (x0, y0), (x1, y1) = pts[i - 1], pts[i]
            if y1 > -20:                            # solo el corazón late, no el tramo del meñique
                x1, y1 = x1 * beat, HEART_DY + (y1 - HEART_DY) * beat
            put(*to_cell(x1, y1), slope_char(x0, y0, x1, y1), RED if i % 7 else PINK)
        if progress < 1:
            put(*to_cell(*pts[last - 1]), "@", PINK)

    out = []
    for row in range(H):
        line, cur = [], None
        for col in range(W):
            if color[row][col] != cur:
                cur = color[row][col]
                line.append(f"\x1b[38;5;{cur}m" if cur else "\x1b[0m")
            line.append(chars[row][col])
        out.append("".join(line) + "\x1b[0m")
    return "\n".join(out)


def main():
    os.system("")                                   # activa colores ANSI en Windows
    sys.stdout.write("\x1b[2J\x1b[?25l")
    start = time.time()
    try:
        while True:
            sys.stdout.write("\x1b[H" + frame(time.time() - start))
            sys.stdout.flush()
            time.sleep(1 / FPS)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[0m\x1b[?25h\n")


if __name__ == "__main__":
    main()
