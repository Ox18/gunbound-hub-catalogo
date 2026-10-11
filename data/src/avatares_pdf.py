"""Catálogos de avatares en PDF A4 (primer cuadro de cada sprite), con la UI del catálogo de funcionalidades.

    avatares_pdf.py db  <salida.pdf>   → avatares capturados de origen dragonbound (BD + hojas locales)
    avatares_pdf.py gis <salida.pdf>   → avatares del cliente (gis/png)

Cada sección se imprime aparte con Chrome (menos memoria) y al final se unen con pypdf.
"""
import base64, io, json, os, subprocess, sys, tempfile
from PIL import Image
from pypdf import PdfWriter

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DB_JSON = os.path.join(HERE, "db_avatars.json")
LOCAL_AVA = "/Users/x/gunbound/dragonbound/src/web/public_html/data/images/ava/"
HUB_AVA = "/Users/x/Documents/www-dragonbound-hack/se-business-dragonbound-hub/app/storage/avatars/"
GIS_PNG = "/Users/x/gunbound/gis/png/"
FRAMES_JSON = "/Users/x/gunbound/data/avatars.json"

TYPES = [("h", "Cabeza"), ("b", "Cuerpo"), ("g", "Gafas"), ("f", "Bandera"), ("1", "Fondo"), ("2", "Primer plano"), ("x", "Accesorio")]
GENDER = {"m": "Chico", "f": "Chica"}
THUMB = 80
DL_AVA = os.path.join(HERE, "ava_dl") + "/"


def thumb(im):
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    s = min(THUMB / im.width, THUMB / im.height, 2.0)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=70, method=4)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def first_block(img):
    """Ancho del primer cuadro de una tira horizontal sin datos de cuadros: hasta la primera columna
    transparente después del dibujo (si no hay hueco, un cuadrado de la altura de la tira)."""
    alpha = img.getchannel("A")
    w, h = img.size
    cols = [alpha.crop((x, 0, x + 1, h)).getbbox() is not None for x in range(min(w, h * 4))]
    start = next((x for x, c in enumerate(cols) if c), 0)
    end = next((x for x in range(start, len(cols)) if not cols[x]), None)
    if end is None or end - start > h * 2:
        end = min(w, start + h)
    return max(1, end)


def wide_frame(img):
    """Fondos y primeros planos sin datos: sus cuadros miden entre 2 y 3,5 veces su altura. Se busca el ancho
    con esa proporción que divide la tira exacta; si no hay, 2,45 veces la altura (la proporción más común)."""
    w, h = img.size
    for n in range(1, 200):
        if w % n == 0 and 2.0 <= (w // n) / h <= 3.5:
            return w // n
    return min(w, round(h * 2.45))


# --- Avatares capturados (BD) --------------------------------------------------------------------
def db_items():
    rows = json.load(open(DB_JSON))
    frames = {a["file"]: a["g"][0] for a in json.load(open(FRAMES_JSON))["avatars"] if a.get("g") and isinstance(a["g"][0], list)}
    hub = {f.split("-", 1)[1][:-4]: f for f in os.listdir(HUB_AVA) if "-" in f}
    out, skipped = {t: [] for t, _ in TYPES}, 0
    for r in rows:
        fn = r["filename"]
        path = next((p for p in (LOCAL_AVA + fn + ".png", DL_AVA + fn + ".png") if os.path.exists(p)), None)
        if not path and fn in hub:
            path = HUB_AVA + hub[fn]
        f0 = r["f0"] if isinstance(r["f0"], list) else frames.get(fn)
        if not path or r["type"] not in out:
            skipped += 1
            continue
        try:
            img = Image.open(path).convert("RGBA")
            if f0:
                w, h = min(f0[0], img.width), min(f0[1], img.height)
            elif r["type"] in "12":
                w, h = wide_frame(img), img.height
            else:
                w, h = first_block(img), img.height
            src = thumb(img.crop((0, 0, w, h)))
        except Exception:
            skipped += 1
            continue
        g = r["gender"] if r["gender"] in GENDER else (fn[0] if fn[:1] in GENDER and r["type"] in "hbgf" else None)
        out[r["type"]].append({"src": src, "id": str(r["game_id"]), "name": (r["name"] or "").strip() or "Exclusivo",
                               "set": (r["set_name"] or "").strip(), "gender": GENDER.get(g, "Unisex"),
                               "shop": bool(r["in_shop"])})
    return out, skipped


# --- Avatares del cliente (gis/png) --------------------------------------------------------------
GIS_PREFIX = {"mh": ("h", "m"), "fh": ("h", "f"), "mb": ("b", "m"), "fb": ("b", "f"), "mg": ("g", "m"), "fg": ("g", "f"),
              "mf": ("f", "m"), "ff": ("f", "f"), "b": ("1", None), "f": ("2", None)}


def gis_first(name):
    img = Image.open(GIS_PNG + name + ".png").convert("RGBA")
    meta = json.load(open(GIS_PNG + name + ".json"))
    anims = meta.get("animations") or {}
    i = anims["normal"]["steps"][0][0] if anims.get("normal", {}).get("steps") else 0
    f = meta["frames"][i]
    x, y, w, h = f[:4]
    part = img.crop((x, y, x + w, y + h))
    if len(f) > 6 and f[6] == 3:
        r, g, b, a = part.split()
        part = Image.merge("RGBA", (g, b, a, r))
    return part


def gis_items():
    import re
    out, skipped = {t: [] for t, _ in TYPES}, 0
    def order(n):
        m = re.fullmatch(r"([a-zA-Z]+)(\d+)(.*)", n)
        return (m.group(1), int(m.group(2)), m.group(3)) if m else (n, 0, "")
    names = sorted((n[:-4] for n in os.listdir(GIS_PNG) if n.endswith(".png")), key=order)
    for n in names:
        m = re.fullmatch(r"(mh|fh|mb|fb|mg|fg|mf|ff|b|f)(\d{5,6})", n)
        if not m or not os.path.exists(GIS_PNG + n + ".json"):
            continue
        t, g = GIS_PREFIX[m.group(1)]
        try:
            src = thumb(gis_first(n))
        except Exception:
            skipped += 1
            continue
        out[t].append({"src": src, "id": m.group(2), "name": "", "set": "", "gender": GENDER.get(g, "Unisex"), "shop": None})
    return out, skipped


# --- HTML y PDF ----------------------------------------------------------------------------------
CSS = """
:root{--sky-1:#cfe3fb;--sky-2:#8dbcf0;--sky-3:#4f93e6;--tab:#244f99;--tab-2:#163a78;--navy:#0b2540;--ink:#0d1d3a;--pill:#7fd8ff;--gold:#ffd21f;--paper:#fff;--line:#cfe3fb;--pink:#f3c1d6;
--display:"Lilita One","Arial Rounded MT Bold","Trebuchet MS",sans-serif;--body:"Nunito","Arial Rounded MT Bold",system-ui,sans-serif;}
*{box-sizing:border-box}html,body{margin:0;background:#fff;color:var(--ink);font:600 9pt/1.35 var(--body)}
@page{size:A4;margin:12mm 11mm 13mm}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}
h1,h2{font-family:var(--display);font-weight:400;margin:0;line-height:1.05}
.cover{height:270mm;display:grid;align-content:center;gap:9mm;padding:14mm 12mm;border-radius:6px;background:linear-gradient(180deg,var(--sky-3),var(--sky-2) 55%,#f2f8ff);break-after:page}
.cover .tag{justify-self:start;font:400 11pt/1 var(--display);color:var(--gold);background:var(--navy);border-radius:7px;padding:8px 12px 7px;letter-spacing:.04em}
.cover h1{font-size:44pt;color:#fff;paint-order:stroke fill;-webkit-text-stroke:4px var(--ink)}
.cover p{max-width:60ch;margin:0;font-weight:800;color:var(--navy);font-size:12pt}
.mosaic{display:flex;gap:7px;flex-wrap:wrap;align-items:flex-end}.mosaic img{height:58px;width:auto}
.toc{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 18px}.toc span{font:400 13pt/1.2 var(--display);color:var(--navy)}
.sec{display:flex;align-items:end;border-bottom:3px solid var(--tab);margin-bottom:4mm}
.sec h2{font-size:20pt;color:#fff;paint-order:stroke fill;-webkit-text-stroke:5px var(--ink);padding:8px 26px 6px 14px;background:linear-gradient(180deg,var(--tab),var(--tab-2));clip-path:polygon(0 0,calc(100% - 16px) 0,100% 100%,0 100%)}
.lead{margin:0 0 4mm;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:2.2mm}
.card{border:1px solid var(--line);border-radius:5px;padding:1.5mm;display:grid;gap:1mm;break-inside:avoid;align-content:start}
.th{height:21mm;border-radius:4px;display:grid;place-items:center;background:radial-gradient(circle at 50% 60%,var(--sky-1),var(--sky-2));border:1px solid var(--sky-3);overflow:hidden}
.th img{max-width:92%;max-height:19mm;width:auto;height:auto}
.n{font:400 8pt/1.1 var(--display);color:var(--navy);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.2em;word-break:break-word}
.s{font:700 6.5pt/1.1 var(--body);color:var(--tab);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.id{font:700 7.5pt/1 "Chakra Petch","Courier New",monospace;color:var(--gold);background:var(--navy);border-radius:3px;padding:2px 4px;justify-self:start;font-variant-numeric:tabular-nums}
.chips{display:flex;gap:1mm;flex-wrap:wrap}.c{font:800 6pt/1 var(--body);color:var(--navy);background:var(--pill);border-radius:999px;padding:2px 5px}.c.g{background:var(--gold)}.c.p{background:var(--pink)}
"""
FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@700&family=Lilita+One&family=Nunito:wght@600;700;800&display=swap">'


def card(it):
    chips = f'<span class="c{" p" if it["gender"] == "Chica" else ""}">{it["gender"]}</span>'
    if it["shop"] is not None:
        chips += f'<span class="c g">{"Tienda" if it["shop"] else "Exclusivo"}</span>'
    s = f'<div class="s">{esc(it["set"])}</div>' if it["set"] else ""
    name = f'<div class="n">{esc(it["name"])}</div>' if it["name"] else ""
    return f'<div class="card"><div class="th"><img src="{it["src"]}" alt=""></div><div class="id">ID {esc(it["id"])}</div>{name}{s}<div class="chips">{chips}</div></div>'


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def page(body, title):
    return f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{title}</title>{FONTS}<style>{CSS}</style></head><body>{body}</body></html>'


def print_pdf(html, out):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, dir=HERE) as f:
        f.write(html)
        path = f.name
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=20000",
                    f"--print-to-pdf={out}", "file://" + path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    os.remove(path)


def build(kind, out_pdf):
    items, skipped = db_items() if kind == "db" else gis_items()
    title = "Catálogo de avatares"
    sub = "Colección capturada" if kind == "db" else "Colección del cliente"
    intro = ("Avatares de la colección capturada, agrupados por tipo. Cada carta muestra el primer cuadro del sprite, "
             "su ID en el juego, su nombre, el conjunto al que pertenece y si es de tienda o exclusivo.") if kind == "db" else (
             "Avatares que incluye el cliente, agrupados por tipo. Cada carta muestra el primer cuadro del sprite, su ID y su género.")
    sections = [(t, label, items[t]) for t, label in TYPES if items[t]]
    mosaic = "".join(f'<img src="{v[len(v) // 3]["src"]}" alt="">' for _, _, v in sections for _ in [0] if v)
    toc = "".join(f"<span>{label}</span>" for _, label, _ in sections)
    cover = f'<section class="cover"><span class="tag">{sub.upper()}</span><h1>{title}</h1><p>{intro}</p><div class="mosaic">{mosaic}</div><div class="toc">{toc}</div></section>'
    parts = []
    tmp = tempfile.mkdtemp(dir=HERE)
    print_pdf(page(cover, title), os.path.join(tmp, "00.pdf"))
    parts.append(os.path.join(tmp, "00.pdf"))
    for i, (t, label, its) in enumerate(sections, 1):
        lead = f'<p class="lead">{label}: avatares de este tipo, en el orden del catálogo.</p>'
        for k in range(0, len(its), 1400):  # trozos medianos para no cargar a Chrome
            head = f'<div class="sec"><h2>{label}</h2></div>{lead}' if k == 0 else ""
            html = page(head + '<div class="grid">' + "".join(card(x) for x in its[k:k + 1400]) + "</div>", title)
            p = os.path.join(tmp, f"{i:02d}-{k:06d}.pdf")
            print_pdf(html, p)
            parts.append(p)
        print(f"  {label}: {len(its)}", flush=True)
    w = PdfWriter()
    for p in parts:
        w.append(p)
    w.write(out_pdf)
    for p in parts:
        os.remove(p)
    os.rmdir(tmp)
    total = sum(len(v) for v in items.values())
    print(f"{out_pdf}: {total} avatares, {len(w.pages)} páginas; sin hoja o sin cuadro: {skipped}")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
