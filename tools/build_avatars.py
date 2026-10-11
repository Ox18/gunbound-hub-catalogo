"""Miniaturas y datos de los dos catálogos de avatares de la web (primer cuadro de cada sprite).

    ~/gunbound/.venv/bin/python tools/build_avatars.py [gb|db|all]

La lógica de recorte es la de avatares_pdf.py (el agente de GunBound, data/src/), pero en vez de
incrustar base64 en un PDF escribe un .webp por avatar en avatars/<gb|db>/ y un data/avatars-<gb|db>.js
(`window.AVATARS_GB = [...]`), que la web carga con <script> para funcionar abriendo el archivo sin servidor.
"""
import json, os, re, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "src")
DB_JSON = os.path.join(SRC, "db_avatars.json")
DL_AVA = os.path.join(SRC, "ava_dl") + "/"
LOCAL_AVA = "/Users/x/gunbound/dragonbound/src/web/public_html/data/images/ava/"
HUB_AVA = "/Users/x/Documents/www-dragonbound-hack/se-business-dragonbound-hub/app/storage/avatars/"
GIS_PNG = "/Users/x/gunbound/gis/png/"
FRAMES_JSON = "/Users/x/gunbound/data/avatars.json"
THUMB = 96


def save_thumb(im, path):
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    s = min(THUMB / im.width, THUMB / im.height, 2.0)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    im.save(path, "WEBP", quality=75, method=4)


def first_block(img):
    """Ancho del primer cuadro de una tira sin datos de cuadros: hasta la primera columna transparente."""
    alpha = img.getchannel("A")
    w, h = img.size
    cols = [alpha.crop((x, 0, x + 1, h)).getbbox() is not None for x in range(min(w, h * 4))]
    start = next((x for x, c in enumerate(cols) if c), 0)
    end = next((x for x in range(start, len(cols)) if not cols[x]), None)
    if end is None or end - start > h * 2:
        end = min(w, start + h)
    return max(1, end)


def wide_frame(img):
    """Fondos y primeros planos: cuadros de 2 a 3,5 veces su altura que dividen la tira exacta."""
    w, h = img.size
    for n in range(1, 200):
        if w % n == 0 and 2.0 <= (w // n) / h <= 3.5:
            return w // n
    return min(w, round(h * 2.45))


def build_db():
    out_dir = os.path.join(ROOT, "avatars", "db")
    rows = json.load(open(DB_JSON))
    frames = {a["file"]: a["g"][0] for a in json.load(open(FRAMES_JSON))["avatars"] if a.get("g") and isinstance(a["g"][0], list)}
    hub = {f.split("-", 1)[1][:-4]: f for f in os.listdir(HUB_AVA) if "-" in f}
    items, skipped = [], 0
    for r in rows:
        fn = r["filename"]
        path = next((p for p in (LOCAL_AVA + fn + ".png", DL_AVA + fn + ".png") if os.path.exists(p)), None)
        if not path and fn in hub:
            path = HUB_AVA + hub[fn]
        f0 = r["f0"] if isinstance(r["f0"], list) else frames.get(fn)
        if not path:
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
            save_thumb(img.crop((0, 0, w, h)), os.path.join(out_dir, fn + ".webp"))
        except Exception:
            skipped += 1
            continue
        g = r["gender"] if r["gender"] in "mf" else (fn[0] if fn[:1] in "mf" and r["type"] in "hbgf" else "a")
        items.append([str(r["game_id"]), r["type"], g, (r["name"] or "").strip(), (r["set_name"] or "").strip(),
                      1 if r["in_shop"] else 0, fn])
    return items, skipped


GIS_PREFIX = {"mh": ("h", "m"), "fh": ("h", "f"), "mb": ("b", "m"), "fb": ("b", "f"), "mg": ("g", "m"), "fg": ("g", "f"),
              "mf": ("f", "m"), "ff": ("f", "f"), "b": ("1", "a"), "f": ("2", "a")}


def gis_first(name):
    img = Image.open(GIS_PNG + name + ".png").convert("RGBA")
    meta = json.load(open(GIS_PNG + name + ".json"))
    anims = meta.get("animations") or {}
    i = anims["normal"]["steps"][0][0] if anims.get("normal", {}).get("steps") else 0
    x, y, w, h = meta["frames"][i][:4]
    part = img.crop((x, y, x + w, y + h))
    if len(meta["frames"][i]) > 6 and meta["frames"][i][6] == 3:
        r, g, b, a = part.split()
        part = Image.merge("RGBA", (g, b, a, r))
    return part


def build_gb():
    out_dir = os.path.join(ROOT, "avatars", "gb")

    def order(n):
        m = re.fullmatch(r"([a-zA-Z]+)(\d+)(.*)", n)
        return (m.group(1), int(m.group(2)), m.group(3)) if m else (n, 0, "")

    names = sorted((n[:-4] for n in os.listdir(GIS_PNG) if n.endswith(".png")), key=order)
    items, skipped = [], 0
    for n in names:
        m = re.fullmatch(r"(mh|fh|mb|fb|mg|fg|mf|ff|b|f)(\d{5,6})", n)
        if not m or not os.path.exists(GIS_PNG + n + ".json"):
            continue
        t, g = GIS_PREFIX[m.group(1)]
        try:
            save_thumb(gis_first(n), os.path.join(out_dir, n + ".webp"))
        except Exception:
            skipped += 1
            continue
        items.append([m.group(2), t, g, "", "", None, n])
    return items, skipped


def write_js(kind, items):
    var = "AVATARS_" + kind.upper()
    with open(os.path.join(ROOT, "data", f"avatars-{kind}.js"), "w") as f:
        f.write(f"// Generado por tools/build_avatars.py: [id, tipo, género, nombre, conjunto, tienda, archivo]\n")
        f.write(f"window.{var} = {json.dumps(items, ensure_ascii=False, separators=(',', ':'))};\n")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for kind, fn in (("gb", build_gb), ("db", build_db)):
        if which in (kind, "all"):
            items, skipped = fn()
            write_js(kind, items)
            print(kind, len(items), "avatares;", skipped, "sin imagen")
