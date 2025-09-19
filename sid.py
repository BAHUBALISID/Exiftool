from __future__ import annotations
import argparse
import json
import csv
from pathlib import Path
from datetime import datetime
import math
import sys

try:
    from PIL import Image
except Exception as e:
    print("Missing Pillow. Install with: pip install Pillow")
    raise

try:
    import exifread
except Exception:
    print("Missing ExifRead. Install with: pip install ExifRead")
    raise

try:
    import piexif
except Exception:
    print("Missing piexif. Install with: pip install piexif")
    raise

def safe_read_bytes(p: Path):
    try:
        return p.read_bytes()
    except Exception:
        return None

def human_size(n: int) -> str:
    for unit in ['B','KB','MB','GB','TB']:
        if n < 1024.0:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"

def ratio_to_float(r):
    # made by sid
    try:
        if hasattr(r, 'num') and hasattr(r, 'den'):
            return float(r.num) / float(r.den) if r.den != 0 else 0.0
        if isinstance(r, tuple) and len(r) == 2:
            num, den = r
            return float(num) / float(den) if den != 0 else 0.0
        return float(r)
    except Exception:
        return None

def dms_to_decimal(dms):
    
    try:
        d = ratio_to_float(dms[0])
        m = ratio_to_float(dms[1])
        s = ratio_to_float(dms[2])
        if d is None or m is None or s is None:
            return None
        return d + (m / 60.0) + (s / 3600.0)
    except Exception:
        return None

def parse_exifread_tags(tags):
    out = {}
 
    def get(k):
        return str(tags[k]) if k in tags else None

    out['make'] = get('Image Make') or get('Make')
    out['model'] = get('Image Model') or get('Model')
    out['datetime_original'] = get('EXIF DateTimeOriginal') or get('EXIF DateTimeDigitized') or get('Image DateTime')
    out['software'] = get('Image Software') or get('Software')
    out['artist'] = get('Image Artist') or get('EXIF Artist') or get('Artist')
    
    if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
        try:
            lat_vals = tags['GPS GPSLatitude'].values
            lon_vals = tags['GPS GPSLongitude'].values
            lat_ref = str(tags.get('GPS GPSLatitudeRef', '')).upper()
            lon_ref = str(tags.get('GPS GPSLongitudeRef', '')).upper()
            lat = dms_to_decimal(lat_vals)
            lon = dms_to_decimal(lon_vals)
            if lat is not None and lon is not None:
                if lat_ref and lat_ref.startswith('S'):
                    lat = -abs(lat)
                if lon_ref and lon_ref.startswith('W'):
                    lon = -abs(lon)
                out['gps'] = {'lat': round(lat, 6), 'lon': round(lon, 6),
                              'lat_ref': lat_ref, 'lon_ref': lon_ref}
        except Exception:
            pass
    return out

def parse_piexif(img_path: Path):
    """Return a cleaned piexif dict (strings decoded where possible)."""
    try:
        ex = piexif.load(str(img_path))
    except Exception:
        return {}
    def clean(ifd):
        out = {}
        for tag, val in ex.get(ifd, {}).items():
            name = piexif.TAGS.get(ifd, {}).get(tag, {}).get('name', str(tag))
            
            if isinstance(val, bytes):
                try:
                    out[name] = val.decode('utf-8', errors='replace').strip('\x00')
                except Exception:
                    out[name] = repr(val)
            else:
                out[name] = val
        return out
    return {ifd: clean(ifd) for ifd in ex.keys()}

def extract_one(path: Path):
    result = {
        'file': path.name,
        'path': str(path.resolve()),
        'size_bytes': None,
        'size_human': None,
        'width': None,
        'height': None,
        'format': None,
        'pil_error': None,
        'exifread': {},
        'piexif': {},
        'highlights': {}
    }
    try:
        stat = path.stat()
        result['size_bytes'] = stat.st_size
        result['size_human'] = human_size(stat.st_size)
    except Exception:
        pass

    # PIL info
    try:
        with Image.open(path) as im:
            result['format'] = im.format
            result['width'], result['height'] = im.size
    except Exception as e:
        result['pil_error'] = str(e)

    # exifread (flat)
    try:
        with open(path, 'rb') as f:
            tags = exifread.process_file(f, details=False, strict=True)
        # store raw small set and parsed highlights
        result['exifread_raw'] = {k: str(tags[k]) for k in tags.keys()}
        parsed = parse_exifread_tags(tags)
        result['exifread'] = parsed
    except Exception as e:
        result['exifread_error'] = str(e)
        parsed = {}

    # piexif (structured)
    try:
        result['piexif'] = parse_piexif(path)
    except Exception as e:
        result['piexif_error'] = str(e)

    # Build highlights in human-friendly order
    highlights = {}
    # Device
    make = parsed.get('make') or result['piexif'].get('0th', {}).get('Make')
    model = parsed.get('model') or result['piexif'].get('0th', {}).get('Model')
    if make or model:
        highlights['device'] = ' '.join([x for x in [make, model] if x])
    # Author/Artist
    artist = parsed.get('artist') or result['piexif'].get('0th', {}).get('Artist')
    if artist:
        highlights['author'] = artist
    # Software/editor
    software = parsed.get('software') or result['piexif'].get('0th', {}).get('Software')
    if software:
        highlights['software'] = software
    # Date/time
    dt = parsed.get('datetime_original')
    if not dt:
        # piexif 0th or Exif may have DateTime
        dt = result['piexif'].get('0th', {}).get('DateTime') or result['piexif'].get('Exif', {}).get('DateTimeOriginal')
        # piexif returns bytes sometimes; ensure str
        if isinstance(dt, bytes):
            try:
                dt = dt.decode('utf-8', errors='replace')
            except Exception:
                dt = str(dt)
    if dt:
        highlights['datetime_original'] = dt
    # GPS
    gps = parsed.get('gps') or None
    if gps:
        highlights['gps_decimal'] = f"{gps['lat']}, {gps['lon']}"
        highlights['gps'] = gps
    # Dimensions & size
    if result['width'] and result['height']:
        highlights['dimensions'] = f"{result['width']}x{result['height']}"
    if result['size_human']:
        highlights['file_size'] = result['size_human']

    # Confidence notes
    notes = []
    if not highlights.get('gps'):
        notes.append("No GPS data found (or stripped by app).")
    if not highlights.get('author'):
        notes.append("No author/artist metadata found.")
    if not highlights.get('device'):
        notes.append("No device/make/model info found.")
    if not highlights.get('datetime_original'):
        notes.append("No DateTimeOriginal found.")
    highlights['notes'] = notes

    result['highlights'] = highlights
    return result

def print_summary(item):
    h = item['highlights']
    print("="*60)
    print(f"File: {item['file']}")
    if item.get('format'):
        print(f" Format: {item['format']}")
    if h.get('dimensions'):
        print(f" Dimensions: {h['dimensions']}")
    if h.get('file_size'):
        print(f" Size: {h['file_size']}")
    if h.get('device'):
        print(f" Device: {h['device']}")
    if h.get('author'):
        print(f" Author: {h['author']}")
    if h.get('software'):
        print(f" Software: {h['software']}")
    if h.get('datetime_original'):
        print(f" Taken: {h['datetime_original']}")
    if h.get('gps'):
        print(f" GPS (decimal): {h['gps_decimal']}")
    # notes
    if h.get('notes'):
        print(" Notes:")
        for n in h['notes']:
            print("  -", n)
    print("="*60)
    print()

def main():
    parser = argparse.ArgumentParser(description="Extract human-friendly image metadata highlights.")
    parser.add_argument("cmd", choices=['extract'], help="command")
    parser.add_argument("images", nargs='+', help="image files to process")
    parser.add_argument("--json", action="store_true", help="write per-image JSON sidecar (image.meta.json)")
    parser.add_argument("--csv", type=str, default=None, help="write summary CSV file")
    args = parser.parse_args()

    results = []
    for img in args.images:
        p = Path(img)
        if not p.exists():
            print(f"Not found: {img}", file=sys.stderr)
            continue
        res = extract_one(p)
        results.append(res)
        print_summary(res)
        if args.json:
            outp = p.with_name(p.name + ".meta.json")
            try:
                with open(outp, 'w', encoding='utf-8') as f:
                    json.dump(res, f, indent=2, ensure_ascii=False)
                print(f"Wrote JSON sidecar: {outp}")
            except Exception as e:
                print(f"Failed to write JSON for {p.name}: {e}", file=sys.stderr)

    if args.csv and results:
        csv_path = Path(args.csv)
        fieldnames = ['file','path','format','width','height','file_size','device','author','software','datetime_original','gps_decimal']
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as cf:
                w = csv.DictWriter(cf, fieldnames=fieldnames)
                w.writeheader()
                for r in results:
                    h = r['highlights']
                    row = {
                        'file': r.get('file'),
                        'path': r.get('path'),
                        'format': r.get('format'),
                        'width': r.get('width'),
                        'height': r.get('height'),
                        'file_size': h.get('file_size'),
                        'device': h.get('device'),
                        'author': h.get('author'),
                        'software': h.get('software'),
                        'datetime_original': h.get('datetime_original'),
                        'gps_decimal': h.get('gps_decimal'),
                    }
                    w.writerow(row)
            print(f"Wrote CSV summary: {csv_path}")
        except Exception as e:
            print(f"Failed to write CSV: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
