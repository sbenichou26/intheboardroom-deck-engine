"""Real-image resolver for deck slots. Keyless, best-effort.

Sources:
  - Openverse (CC / public-domain image search across the open web: Flickr,
    museums, Wikimedia...) for photos. Filtered to licences usable in a
    COMMERCIAL advisory deck WITH attribution and after recompression, i.e.
    CC0 / Public Domain Mark / CC BY only. NC (non-commercial), ND (no
    derivatives - recompression is a derivative) and SA (copyleft - would
    force the whole deck under share-alike) are excluded.
  - Wikipedia REST summary for a club crest / lead image (trademark used
    nominatively for identification; flagged as such).

Every image is downloaded, compressed (Pillow) and base64-embedded so the deck
stays a standalone, offline-safe file (needed for the PDF export). Any network
or decode failure returns None and the caller simply drops that slot.
"""
import base64
import json
import ssl
import urllib.parse
import urllib.request
from io import BytesIO

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover - fall back to system certs
    _CTX = ssl.create_default_context()

_UA = "intheboardroom-deck/1.0 (research; contact via app)"

# Licences safe for a commercial deck once the image is recompressed:
# public domain and attribution-only. Nothing copyleft / non-commercial / no-deriv.
_COMMERCIAL_LICENSES = "cc0,pdm,by"


def _open(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    return urllib.request.urlopen(req, timeout=timeout, context=_CTX)


def _get_json(url, timeout=12):
    with _open(url, timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def search_openverse(query: str, page_size: int = 8) -> list:
    """Return a list of candidate images (url + licence metadata) for a query,
    already filtered to commercially-usable licences. Empty list on any failure."""
    q = urllib.parse.quote(query)
    url = (f"https://api.openverse.org/v1/images/?q={q}"
           f"&page_size={page_size}&license={_COMMERCIAL_LICENSES}&mature=false")
    try:
        data = _get_json(url)
    except Exception:
        return []
    out = []
    for r in (data.get("results") or []):
        u = r.get("url")
        if not u:
            continue
        out.append({
            "url": u,
            "license": (r.get("license") or "").upper(),
            "license_version": r.get("license_version") or "",
            "creator": (r.get("creator") or "").strip(),
            "source": r.get("source") or "",
            "title": (r.get("title") or "").strip(),
        })
    return out


def _attribution(cand: dict) -> str:
    who = cand.get("creator") or cand.get("source") or "Unknown"
    src = cand.get("source") or ""
    lic = cand.get("license") or ""
    ver = cand.get("license_version") or ""
    tail = f" via {src}" if src else ""
    lic_str = f"CC {lic} {ver}".strip() if lic not in ("CC0", "PDM") else lic
    return f"Photo: {who}{tail} ({lic_str})"


def fetch_and_encode(url: str, max_w: int = 1100, quality: int = 68):
    """Download, downscale and JPEG-compress an image, return a base64 data URI,
    or None on any failure."""
    try:
        from PIL import Image
        with _open(url, timeout=15) as r:
            raw = r.read()
        if not raw or len(raw) > 15_000_000:
            return None
        im = Image.open(BytesIO(raw)).convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)))
        out = BytesIO()
        im.save(out, format="JPEG", quality=quality, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:
        return None


def resolve_photo(query: str, max_w: int = 1100, quality: int = 68):
    """First Openverse result that downloads and encodes.
    Returns {'data_uri', 'attribution'} or None."""
    for cand in search_openverse(query):
        data = fetch_and_encode(cand["url"], max_w, quality)
        if data:
            return {"data_uri": data, "attribution": _attribution(cand)}
    return None


def resolve_crest(title: str, max_w: int = 600, quality: int = 82):
    """Club crest / lead image from the entity's Wikipedia page. The crest is a
    trademark used nominatively for identification. Returns {'data_uri',
    'attribution'} or None."""
    t = urllib.parse.quote(title.replace(" ", "_"))
    for lang in ("en", "fr"):
        try:
            d = _get_json(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{t}")
        except Exception:
            continue
        img = (d.get("originalimage") or d.get("thumbnail") or {}).get("source")
        if not img:
            continue
        data = fetch_and_encode(img, max_w, quality)
        if data:
            return {"data_uri": data,
                    "attribution": f"Logo/crest via Wikipedia ({d.get('title', title)})"}
    return None
