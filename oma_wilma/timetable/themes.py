"""Lukujärjestyksen teemat: sivun taustakuva (SVG, A4 vaaka, millimetreinä) ja lapsen nimi otsikkona.

Uusi teema: kirjoita funktio, joka palauttaa koko sivun SVG:n (nimi mukaan), ja lisää se THEMES-listaan. Taulukko
piirretään kuvan päälle alueelle TABLE_BOX, joten kuva tehdään sen ympärille.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import unicodedata
from html import escape

PAGE_W, PAGE_H = 297, 210
TABLE_BOX = (32, 38, 233, 126)  # x, y, leveys, korkeus (mm): taulukon paikka (oletus), kuva jättää tämän tyhjäksi
STROKE = 0.4

# ------------------------------------------------------------------------------------------------- pikselifontti 5x7

_FONT: dict[str, list[str]] = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": ["###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
    "J": ["..###", "...#.", "...#.", "...#.", "#..#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "Å": ["..#..", ".....", ".###.", "#...#", "#####", "#...#", "#...#"],
    "Ä": [".#.#.", ".....", ".###.", "#...#", "#####", "#...#", "#...#"],
    "Ö": [".#.#.", ".....", ".###.", "#...#", "#...#", "#...#", ".###."],
    "Ü": [".#.#.", ".....", "#...#", "#...#", "#...#", "#...#", ".###."],
    "-": ["...", "...", "...", "###", "...", "...", "..."],
    " ": ["...", "...", "...", "...", "...", "...", "..."],
}
_ACCENTS = str.maketrans("ÁÀÂÉÈÊËÍÌÎÏÓÒÔÕÚÙÛÑÇ", "AAAEEEEIIIIOOOOUUUNC")


def pixel_text(text: str) -> list[str]:
    """Teksti pikseliruudukoksi (rivit, '#' = ruutu). Tuntemattomat merkit jäävät pois."""
    glyphs = [_FONT[c] for c in text.upper().translate(_ACCENTS) if c in _FONT]
    if not glyphs:
        return []
    return [".".join(g[r] for g in glyphs) for r in range(7)]


# ------------------------------------------------------------------------------------------------- piirtoapuja

def _rect(x: float, y: float, w: float, h: float, extra: str = "") -> str:
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}"{extra}/>'


def _sprite(grid: list[str], x: float, y: float, px: float) -> str:
    """Pikselikuva: jokainen ruutu ääriviivoina, jotta lapsi voi värittää ruutu kerrallaan."""
    return "".join(_rect(x + c * px, y + r * px, px, px)
                   for r, row in enumerate(grid) for c, ch in enumerate(row) if ch not in ". ")


def _svg(body: str) -> str:
    return (f'<svg class="bg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PAGE_W} {PAGE_H}" '
            f'width="{PAGE_W}mm" height="{PAGE_H}mm">'
            f'<g fill="#fff" stroke="#000" stroke-width="{STROKE}" stroke-linejoin="miter">{body}</g></svg>')


def pixel_title(text: str, cx: float, top: float, max_w: float, max_h: float) -> str:
    grid = pixel_text(text)
    if not grid:
        return ""
    px = min(max_h / len(grid), max_w / len(grid[0]))
    x = cx - len(grid[0]) * px / 2
    return f'<g stroke-width="{STROKE * 1.3}">{_sprite(grid, x, top, px)}</g><title>{escape(text)}</title>'


# ------------------------------------------------------------------------------------------------- vihreä: palikkamaailma

_CANOPY = [".LLL.", "LLLLL", "LLLLL", "LLLLL"]


def _cube(cx: float, top: float, s: float) -> str:
    """Palikka kolmiulotteisena: kansi ja kaksi kylkeä, kyljissä ruohon raja ja ruutujako väritettäväksi."""
    def poly(pts):
        return '<polygon points="' + " ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + '"/>'
    out = poly([(cx, top), (cx + s, top + s / 2), (cx, top + s), (cx - s, top + s / 2)])
    out += poly([(cx - s, top + s / 2), (cx, top + s), (cx, top + 2 * s), (cx - s, top + 1.5 * s)])
    out += poly([(cx + s, top + s / 2), (cx, top + s), (cx, top + 2 * s), (cx + s, top + 1.5 * s)])
    g = s / 3  # ruohon raja kylkien yläosassa ja pystyjako
    lines = [((cx - s, top + s / 2 + g), (cx, top + s + g)), ((cx + s, top + s / 2 + g), (cx, top + s + g)),
             ((cx - s / 2, top + 0.75 * s + g), (cx - s / 2, top + 1.75 * s)),
             ((cx + s / 2, top + 0.75 * s + g), (cx + s / 2, top + 1.75 * s)),
             ((cx - s / 2, top + s / 4), (cx + s / 2, top + 0.75 * s)), ((cx + s / 2, top + s / 4), (cx - s / 2, top + 0.75 * s))]
    return out + "".join(f'<path d="M{x1:.2f} {y1:.2f}L{x2:.2f} {y2:.2f}" fill="none"/>' for (x1, y1), (x2, y2) in lines)


def _cloud(x: float, y: float, u: float) -> str:
    pts = [(3, 0), (7, 0), (7, 1), (9, 1), (9, 2), (10, 2), (10, 3), (0, 3), (0, 2), (1, 2), (1, 1), (3, 1)]
    return '<polygon points="' + " ".join(f"{x + a * u:.2f},{y + b * u:.2f}" for a, b in pts) + '"/>'


def _sun(x: float, y: float) -> str:
    """Neliöaurinko: keskusta 12 mm, säteet 3 mm ruutuina ympärillä."""
    out = _rect(x, y, 12, 12) + _rect(x + 3, y + 3, 6, 6)
    for dx, dy in [(4.5, -5), (4.5, 14), (-5, 4.5), (14, 4.5), (-3.5, -4), (12.5, -4), (-3.5, 13), (12.5, 13)]:
        out += _rect(x + dx, y + dy, 3, 3)
    return out


def _tree(cx: float, ground: float, cell: float = 5, trunk_cells: int = 9) -> str:
    out = ""
    for i in range(trunk_cells):  # runko: puupalikat, joissa vuosirengasviiva
        y = ground - (i + 1) * cell
        out += _rect(cx - cell / 2, y, cell, cell)
        out += f'<path d="M{cx - cell / 2 + 1.2:.2f} {y + 1:.2f}V{y + cell - 1:.2f}" fill="none"/>'
    top = ground - trunk_cells * cell - len(_CANOPY) * cell
    out += _sprite(_CANOPY, cx - 2.5 * cell, top, cell)
    for r, row in enumerate(_CANOPY):  # lehtipalikoihin pieni ruutu kuvioksi
        for c, ch in enumerate(row):
            if ch == "L" and (r + c) % 2 == 0:
                out += _rect(cx - 2.5 * cell + c * cell + 1, top + r * cell + 1, 1.4, 1.4)
    return out


def _poly(pts) -> str:
    return '<polygon points="' + " ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + '"/>'


def _line(x1: float, y1: float, x2: float, y2: float) -> str:
    return f'<path d="M{x1:.2f} {y1:.2f}L{x2:.2f} {y2:.2f}" fill="none"/>'


WATER = (13, 20)  # ruohorivin palikat (indeksit), joiden kohdalla on vettä laivaa varten


def _ground(y: float, block: float = 9) -> str:
    """Kaksi riviä palikoita: ylempi ruohopalikoita (ruohon raja porrastettuna) ja keskellä vettä, alempi maata ja malmia."""
    out = ""
    depths = [3, 4.5, 3, 2.2, 3.8, 3]
    step = block / len(depths)
    for i in range(int(PAGE_W // block) + 1):
        x = i * block
        out += _rect(x, y, block, block)
        if WATER[0] <= i < WATER[1]:  # aallot kahtena porrasviivana
            for wy in (y + 3, y + 6.5):
                d = f"M{x:.2f} {wy:.2f}"
                for k in range(3):
                    d += f"h1.5v-1.2h1.5v1.2"
                out += f'<path d="{d}" fill="none"/>'
        else:
            d = f"M{x:.2f} {y + depths[0]:.2f}"
            for k, depth in enumerate(depths):
                d += f"V{y + depth:.2f}H{x + (k + 1) * step:.2f}"
            out += f'<path d="{d}" fill="none"/>'
        out += _rect(x, y + block, block, block)
        if i % 5 == 2:  # malmi: rypäs ruutuja
            out += "".join(_rect(x + a, y + block + b, 2, 2) for a, b in [(2, 2), (4.5, 3), (3, 5)])
        else:
            out += "".join(_rect(x + a, y + block + b, 1.1, 1.1)
                           for a, b in [((i * 3) % 6 + 1, 2), ((i * 5) % 6 + 1.5, 5.5)])
    return out


def _hero(cx: float, gy: float, u: float = 1.25) -> str:
    """Palikkasoturi edestä, miekka ylös nostetussa kädessä."""
    ht = gy - 32 * u          # pään yläreuna
    acx = cx + 6 * u          # nostetun käden keskikohta
    out = _rect(acx - 0.75 * u, gy - 34 * u, 1.5 * u, 3 * u)                          # kahva
    out += _rect(acx - 1 * u, gy - 47 * u, 2 * u, 12 * u)                              # terä
    out += _poly([(acx - 1 * u, gy - 47 * u), (acx, gy - 49 * u), (acx + 1 * u, gy - 47 * u)])
    out += _line(acx, gy - 46 * u, acx, gy - 36 * u)
    out += _rect(acx - 3 * u, gy - 35.2 * u, 6 * u, 1.2 * u)                           # väistin
    out += _rect(cx - 4 * u, gy - 12 * u, 4 * u, 12 * u) + _rect(cx, gy - 12 * u, 4 * u, 12 * u)   # jalat
    out += _line(cx - 4 * u, gy - 2.5 * u, cx + 4 * u, gy - 2.5 * u)                  # kengät
    out += _rect(cx - 4 * u, gy - 24 * u, 8 * u, 12 * u)                               # vartalo
    out += _line(cx - 4 * u, gy - 14 * u, cx + 4 * u, gy - 14 * u)                    # vyö
    out += _rect(cx - 0.8 * u, gy - 14.6 * u, 1.6 * u, 1.2 * u)                        # solki
    out += f'<path d="M{cx - 2 * u:.2f} {gy - 24 * u:.2f}L{cx:.2f} {gy - 22 * u:.2f}L{cx + 2 * u:.2f} {gy - 24 * u:.2f}" fill="none"/>'
    out += _rect(cx - 8 * u, gy - 24 * u, 4 * u, 12 * u)                               # käsi alhaalla
    out += _line(cx - 8 * u, gy - 15 * u, cx - 4 * u, gy - 15 * u)
    out += _rect(cx + 4 * u, gy - 32 * u, 4 * u, 12 * u)                               # käsi ylhäällä
    out += _line(cx + 4 * u, gy - 29 * u, cx + 8 * u, gy - 29 * u)
    out += _rect(cx - 4 * u, ht, 8 * u, 8 * u)                                         # pää
    out += _poly([(cx - 4 * u, ht), (cx + 4 * u, ht), (cx + 4 * u, ht + 3 * u), (cx + 3 * u, ht + 3 * u),
                  (cx + 3 * u, ht + 2 * u), (cx - 3 * u, ht + 2 * u), (cx - 3 * u, ht + 3 * u), (cx - 4 * u, ht + 3 * u)])
    out += _rect(cx - 3 * u, ht + 4 * u, 1.5 * u, 1.5 * u) + _rect(cx + 1.5 * u, ht + 4 * u, 1.5 * u, 1.5 * u)
    out += _rect(cx - 1.5 * u, ht + 6.2 * u, 3 * u, 0.8 * u)
    return out


def _bird(x: float, y: float, u: float = 1.0) -> str:
    """Lentävä palikkalintu sivulta, nokka oikealle."""
    out = _rect(x - 4 * u, y + 7 * u, 4 * u, 3 * u) + _rect(x - 6 * u, y + 9.5 * u, 6 * u, 2.5 * u)   # pyrstö
    out += _rect(x + 6 * u, y - 2 * u, 4 * u, 3.5 * u) + _rect(x + 4 * u, y + 1 * u, 7 * u, 5.5 * u)   # siipi ylhäällä
    out += _line(x + 6.5 * u, y + 1.5 * u, x + 6.5 * u, y + 6 * u) + _line(x + 8.5 * u, y + 1.5 * u, x + 8.5 * u, y + 6 * u)
    out += _rect(x, y + 6 * u, 14 * u, 8 * u)                                                      # vartalo
    out += _rect(x + 2 * u, y + 10 * u, 8 * u, 4 * u)                                               # vatsa
    out += _rect(x + 10 * u, y, 8 * u, 8 * u)                                                       # pää
    out += _rect(x + 18 * u, y + 3 * u, 3 * u, 2 * u) + _rect(x + 18 * u, y + 5 * u, 2 * u, 1.2 * u)  # nokka
    out += _rect(x + 14 * u, y + 2 * u, 2 * u, 2 * u) + _rect(x + 15 * u, y + 2.6 * u, 0.9 * u, 0.9 * u)  # silmä
    return out


def _boat(cx: float, wy: float, u: float = 1.2) -> str:
    """Purjelaiva vedessä: runko, masto, kaksi purjetta ja lippu."""
    top = wy - 2.5 * u
    out = _rect(cx - 0.5 * u, top - 15 * u, 1 * u, 15 * u)                                   # masto
    out += _rect(cx + 0.5 * u, top - 15 * u, 3.5 * u, 2.2 * u)                               # lippu
    out += _rect(cx + 0.8 * u, top - 12 * u, 8 * u, 10 * u)                                  # iso purje
    out += _line(cx + 0.8 * u, top - 8.5 * u, cx + 8.8 * u, top - 8.5 * u) + _line(cx + 0.8 * u, top - 5 * u, cx + 8.8 * u, top - 5 * u)
    out += _rect(cx - 7.8 * u, top - 9 * u, 7 * u, 7 * u)                                   # etupurje
    out += _line(cx - 7.8 * u, top - 5.5 * u, cx - 0.8 * u, top - 5.5 * u)
    out += _poly([(cx - 12 * u, top), (cx + 12 * u, top), (cx + 9 * u, wy + 1.5 * u), (cx - 9 * u, wy + 1.5 * u)])  # runko
    out += _line(cx - 11 * u, top + 1.6 * u, cx + 11 * u, top + 1.6 * u)
    out += "".join(_rect(cx + k * u, top + 0.3 * u, 1.1 * u, 1.1 * u) for k in (-7, -3.5, 0, 3.5, 7) if k)  # ikkunat
    return out


def _sheep(x: float, gy: float, u: float = 1.1) -> str:
    """Palikkalammas sivulta, pää oikealla."""
    out = "".join(_rect(x + k * u, gy - 3 * u, 2 * u, 3 * u) for k in (1, 4, 9, 12))        # jalat
    out += _rect(x, gy - 11 * u, 14 * u, 8 * u)                                              # villa
    out += "".join(_rect(x + a * u, gy - b * u, 1.5 * u, 1.5 * u) for a, b in [(2, 9.5), (5.5, 7), (8.5, 9.5), (3, 5.5), (10, 6)])
    out += _rect(x + 12 * u, gy - 12 * u, 6 * u, 6 * u)                                     # pää
    out += _rect(x + 12 * u, gy - 12 * u, 6 * u, 1.5 * u)                                   # villatukka
    out += _rect(x + 15.5 * u, gy - 9.5 * u, 1.2 * u, 1.2 * u)                              # silmä
    out += _rect(x + 16.5 * u, gy - 7.5 * u, 1.5 * u, 1.5 * u)                              # kuono
    return out


def _chest(x: float, gy: float, u: float = 1.2) -> str:
    """Aarrearkku: kansi, vanteet ja lukko."""
    out = _rect(x, gy - 8 * u, 11 * u, 8 * u)
    out += _line(x, gy - 5 * u, x + 11 * u, gy - 5 * u)
    out += _line(x + 1.2 * u, gy - 8 * u, x + 1.2 * u, gy) + _line(x + 9.8 * u, gy - 8 * u, x + 9.8 * u, gy)
    out += _rect(x + 4.5 * u, gy - 6 * u, 2 * u, 2.5 * u)
    return out


def green(name: str) -> str:
    ground = 184
    water_mid = (WATER[0] + WATER[1]) / 2 * 9
    body = (_sun(12, 10) + _cloud(238, 9, 3) + _cloud(268, 22, 2)
            + _ground(ground)
            + _hero(17, ground) + _tree(PAGE_W - 16, ground)
            + _cube(16.5, 52, 11) + _bird(272, 52)
            + _boat(water_mid, ground) + _sheep(206, ground) + _chest(72, ground)
            + pixel_title(name, PAGE_W / 2, 7, 168, 26))
    return _svg(body)


# ------------------------------------------------------------------------------------------------- sydän: sydämet, tähdet, yksisarvinen

HEART_TABLE_BOX = (42, 40, 213, 130)  # keskellä: sivuille yhtä paljon tilaa


def _heart(cx: float, cy: float, w: float, inner: bool = True) -> str:
    """Sydän, leveys w, keskipiste (cx, cy). Sisällä pieni kiiltoviiva."""
    h = w * 0.9
    top = cy - h * 0.42
    d = (f"M{cx:.2f} {cy + h * 0.5:.2f}"
         f"C{cx - w * 0.15:.2f} {cy + h * 0.32:.2f} {cx - w * 0.5:.2f} {cy + h * 0.1:.2f} {cx - w * 0.5:.2f} {cy - h * 0.15:.2f}"
         f"C{cx - w * 0.5:.2f} {top - h * 0.12:.2f} {cx - w * 0.08:.2f} {top - h * 0.15:.2f} {cx:.2f} {top + h * 0.06:.2f}"
         f"C{cx + w * 0.08:.2f} {top - h * 0.15:.2f} {cx + w * 0.5:.2f} {top - h * 0.12:.2f} {cx + w * 0.5:.2f} {cy - h * 0.15:.2f}"
         f"C{cx + w * 0.5:.2f} {cy + h * 0.1:.2f} {cx + w * 0.15:.2f} {cy + h * 0.32:.2f} {cx:.2f} {cy + h * 0.5:.2f}Z")
    out = f'<path d="{d}"/>'
    if inner and w >= 8:
        out += (f'<path d="M{cx - w * 0.36:.2f} {cy - h * 0.12:.2f}Q{cx - w * 0.36:.2f} {top + h * 0.02:.2f} '
                f'{cx - w * 0.2:.2f} {top + h * 0.0:.2f}" fill="none" stroke-linecap="round"/>')
    return out


def _star(cx: float, cy: float, r: float) -> str:
    import math
    pts = []
    for k in range(10):
        rr = r if k % 2 == 0 else r * 0.45
        a = -math.pi / 2 + k * math.pi / 5
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return '<polygon stroke-linejoin="round" points="' + " ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + '"/>'


def _blob(circles: list[tuple[float, float, float]]) -> str:
    """Ympyröiden yhdistelmän ääriviiva (pilvi, kiharat): ensin paksut reunat, sitten valkoinen täyttö päälle."""
    first = "".join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" stroke-width="{STROKE * 2}"/>' for x, y, r in circles)
    second = "".join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" stroke="none"/>' for x, y, r in circles)
    return first + second


def _rainbow(cx: float, base: float, r: float, band: float, bands: int = 5) -> str:
    out = ""
    for k in range(bands):
        rr = r - k * band
        out += f'<path d="M{cx - rr:.2f} {base:.2f}A{rr:.2f} {rr:.2f} 0 0 1 {cx + rr:.2f} {base:.2f}Z"/>'
    rr = r - bands * band
    out += f'<path d="M{cx - rr:.2f} {base:.2f}A{rr:.2f} {rr:.2f} 0 0 1 {cx + rr:.2f} {base:.2f}Z"/>'
    out += _blob([(cx - r + band * 2.2 + dx, base + dy, rad) for dx, dy, rad in [(-5, 0, 4.5), (0, -2, 5), (5, 0, 4.5)]])
    out += _blob([(cx + r - band * 2.2 + dx, base + dy, rad) for dx, dy, rad in [(-5, 0, 4.5), (0, -2, 5), (5, 0, 4.5)]])
    return out


def _unicorn(x: float, y: float, k: float, mirror: bool = False) -> str:
    """Yksisarvisen pää ja kaula sivulta (katse oikealle, `mirror`: vasemmalle). Piirretty 100 x 160 yksikön alueelle,
    k = mm / yksikkö; (x, y) on alueen vasen yläkulma."""
    mane = [(30, 52, 10), (23, 70, 11), (19, 90, 12), (15, 112, 12), (13, 134, 12), (12, 152, 9), (40, 42, 8)]
    body = (
        '<path d="M42 50L36 22L54 43Z"/>'                                                         # korva
        '<path d="M32 100C28 125 24 145 20 160L72 160C67 140 63 125 61 110Z"/>'                    # kaula
        + _blob(mane)
        + '<path d="M30 100C25 70 35 45 55 42C70 40 80 55 88 75C95 88 98 100 90 108C82 116 66 114 58 108'
          'C50 116 40 112 30 100Z"/>'                                                              # pää
        '<path d="M50 46L64 41L70 2Z" stroke-linejoin="round"/>'                                   # sarvi
        '<path d="M53 35L64 31M57 24L66 21M61 13L68 11" fill="none"/>'                             # sarven kierteet
        '<path d="M57 68Q63 75 70 68" fill="none" stroke-linecap="round"/>'                        # suljettu silmä
        '<path d="M59 71L57 75M63 73L62 77M67 71L68 75" fill="none" stroke-linecap="round"/>'     # ripset
        '<path d="M85 97Q88 100 85 103" fill="none" stroke-linecap="round"/>'                      # sierain
        '<path d="M70 108Q76 111 82 108" fill="none" stroke-linecap="round"/>'                     # hymy
        + _blob([(44, 48, 6), (36, 52, 6)])                                                        # otsatukka
    )
    t = f"translate({x + 100 * k:.2f} {y:.2f}) scale({-k} {k})" if mirror else f"translate({x:.2f} {y:.2f}) scale({k})"
    return f'<g transform="{t}" stroke-width="{STROKE / k:.3f}">{body}</g>'


def outline_title(text: str, cx: float, baseline: float, size: float, max_w: float) -> str:
    """Iso ääriviivateksti väritettäväksi (valkoinen täyttö, musta reuna)."""
    est = len(text) * size * 0.62
    fit = f' textLength="{max_w}" lengthAdjust="spacingAndGlyphs"' if est > max_w else ""
    return (f'<text x="{cx}" y="{baseline}" text-anchor="middle" font-size="{size}" font-weight="700"'
            f' font-family="Chalkboard SE, Marker Felt, Comic Sans MS, sans-serif" stroke-width="{STROKE * 1.4}"'
            f' stroke-linejoin="round" letter-spacing="1"{fit}>{escape(text)}</text>')


def heart(name: str) -> str:
    """Symmetrinen sivu: tähtiryhmät yläkulmissa, sydän-tähtirivit sivuilla, yksisarviset alakulmissa toisiaan kohti ja
    sateenkaari alareunan keskellä."""
    def mirrored(draw, x: float, *args) -> str:
        return draw(x, *args) + draw(PAGE_W - x, *args)

    est = min(len(name) * 26 * 0.62, 160)
    body = (mirrored(_star, 21, 19, 11) + mirrored(_star, 40, 11, 4.5) + mirrored(_star, 9, 37, 3.5)
            + outline_title(name, PAGE_W / 2, 31, 26, 160)
            + mirrored(_heart, PAGE_W / 2 - est / 2 - 10, 20, 10))
    body += mirrored(_star, 21, 58, 8) + mirrored(_heart, 21, 85, 14) + mirrored(_star, 21, 111, 6)
    body += _unicorn(2, 146, 0.36) + _unicorn(PAGE_W - 2 - 36, 146, 0.36, mirror=True)
    body += _rainbow(PAGE_W / 2, 203, 27, 3.4)
    for i, cx in enumerate([108, 94, 80, 66, 52]):
        body += mirrored(_heart, cx, 191, 10) if i % 2 == 0 else mirrored(_star, cx, 191, 6)
    return _svg(body)


# ------------------------------------------------------------------------------------------------- rekisteri

@dataclass(frozen=True)
class Theme:
    name: str
    aliases: tuple[str, ...]
    background: Callable[[str], str]
    table_box: tuple[float, float, float, float] = TABLE_BOX
    font: str = '"Avenir Next", "Helvetica Neue", Helvetica, Arial, sans-serif'


THEMES = [  # ääkkösetön nimi ensin: sopii skripteihin
    Theme("green", ("vihrea", "vihreä"), green),
    Theme("heart", ("sydan", "sydän"), heart, HEART_TABLE_BOX),
]


def get(name: str) -> Theme:
    key = unicodedata.normalize("NFC", (name or "green").strip().casefold())  # ä voi tulla kahtena merkkinä (a + ¨)
    for theme in THEMES:
        if key == theme.name or key in theme.aliases:
            return theme
    raise ValueError(f"tuntematon teema {name!r}; vaihtoehdot: " + ", ".join(t.name for t in THEMES))
