#!/usr/bin/env python3
"""Birden çok Mihon/Tachiyomi index.pb deposunu tek bir index.pb içinde birleştirir.

- Her depodaki eklenti kayıtları (paket adı bazında) alınır; aynı paket birden çok depoda varsa
  versionCode'u yüksek olan kazanır, eşitlikte sources.json'daki ilk depo kazanır.
- Kayıtlardaki göreli adresler (apk / jar / ikon / site) kaynak deponun adresine göre mutlak
  hale getirilir; böylece JAR'lar özgün depodan inmeye devam eder.
- Çıktı, Anime İzle'nin okuduğu biçimdedir: gzip'li protobuf, alan 1 = ad, alan 2 = rozet,
  alan 101 = eklenti listesi (alan 1 tekrarlı kayıtlar).
Yalnızca Python standart kütüphanesi kullanır.
"""
import argparse, gzip, json, sys, time, urllib.request
from urllib.parse import urljoin, urlparse


# ---------------------------------------------------------------- protobuf (genel, sıra korumalı)
def read_varint(buf, i):
    shift = result = 0
    while True:
        if i >= len(buf):
            raise ValueError("kesik varint")
        b = buf[i]; i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7
        if shift > 70:
            raise ValueError("çok uzun varint")


def write_varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b); return bytes(out)


def parse(buf):
    fields, i = [], 0
    while i < len(buf):
        key, i = read_varint(buf, i)
        field, wt = key >> 3, key & 7
        if field == 0:
            raise ValueError("geçersiz alan numarası")
        if wt == 0:
            v, i = read_varint(buf, i)
        elif wt == 1:
            v, i = buf[i:i + 8], i + 8
        elif wt == 2:
            n, i = read_varint(buf, i)
            if i + n > len(buf):
                raise ValueError("kesik alan")
            v, i = buf[i:i + n], i + n
        elif wt == 5:
            v, i = buf[i:i + 4], i + 4
        else:
            raise ValueError(f"desteklenmeyen wire type {wt}")
        fields.append((field, wt, v))
    return fields


def encode(fields):
    out = bytearray()
    for field, wt, v in fields:
        out += write_varint((field << 3) | wt)
        if wt == 0:
            out += write_varint(v)
        elif wt == 2:
            out += write_varint(len(v)) + v
        else:
            out += v
    return bytes(out)


def get(fields, number, wt=None):
    for f, w, v in fields:
        if f == number and (wt is None or w == wt):
            return v
    return None


# ---------------------------------------------------------------- depo işlemleri
def normalize(url):
    """github.com/<k>/<r>/raw|blob/<dal>/<yol> -> raw.githubusercontent.com/<k>/<r>/<dal>/<yol>"""
    p = urlparse(url.strip())
    if p.netloc.lower() == "github.com":
        parts = [x for x in p.path.split("/") if x]
        if len(parts) >= 5 and parts[2] in ("raw", "blob"):
            return "https://raw.githubusercontent.com/" + "/".join(parts[:2] + parts[3:])
    return url.strip()


def fetch(url, tries=3):
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "anime-izle-repo-merge/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e; time.sleep(2 * (n + 1))
    raise RuntimeError(f"{url} indirilemedi: {last}")


def unwrap(raw):
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw


def extension_records(payload):
    """Uygulamadaki ExtensionIndexDecoder ile aynı mantık."""
    top = parse(payload)
    list_bytes = get(top, 101, 2) or get(top, 5, 2) or payload
    items = parse(list_bytes)
    records = [v for f, w, v in items if f == 1 and w == 2]
    if not records:
        records = [v for f, w, v in items if f == 2 and w == 2]
    return records


def absolutize(value, base):
    text = value.decode("utf-8", "replace")
    if not text or urlparse(text).scheme:
        return value
    return urljoin(base, text).encode()


def rewrite_record(record, base):
    fields = parse(record)
    out = []
    for f, w, v in fields:
        if f == 3 and w == 2:            # kaynaklar: apk(1), ikon(2), jar(501)
            res = [(rf, rw, absolutize(rv, base) if rf in (1, 2, 501) and rw == 2 else rv)
                   for rf, rw, rv in parse(v)]
            v = encode(res)
        elif f == 8 and w == 2:          # kaynak listesi: site adresi alt alan 4
            src = [(sf, sw, absolutize(sv, base) if sf == 4 and sw == 2 else sv)
                   for sf, sw, sv in parse(v)]
            v = encode(src)
        out.append((f, w, v))
    return encode(out)


def package_and_version(record):
    fields = parse(record)
    pkg = (get(fields, 2, 2) or b"").decode("utf-8", "replace")
    ver = get(fields, 5, 0) or 0
    return pkg, ver


def has_jar(record):
    for f, w, val in parse(record):
        if f == 3 and w == 2:
            for rf, rw, rv in parse(val):
                if rf == 501 and rw == 2 and rv:
                    return True
    return False


def merge(payloads_with_base):
    best = {}
    order = []
    for payload, base in payloads_with_base:
        for record in extension_records(payload):
            try:
                pkg, ver = package_and_version(record)
                if not pkg:
                    continue
                fixed = rewrite_record(record, base)
            except ValueError:
                continue
            rank = (has_jar(fixed), ver)
            if pkg not in best:
                order.append(pkg); best[pkg] = (rank, fixed)
            elif rank > best[pkg][0]:
                best[pkg] = (rank, fixed)
    return [best[p][1] for p in order]


def build_index(name, badge, records):
    listing = encode([(1, 2, r) for r in records])
    top = [(1, 2, name.encode()), (2, 2, badge.encode()), (101, 2, listing)]
    return gzip.compress(encode(top), mtime=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="sources.json")
    ap.add_argument("--out", default="dist/index.pb")
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    loaded = []
    for url in cfg["sources"]:
        norm = normalize(url)
        print("indiriliyor:", norm)
        loaded.append((unwrap(fetch(norm)), norm))
    records = merge(loaded)
    if not records:
        sys.exit("Hiç eklenti bulunamadı; çıktı yazılmadı.")
    import os
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "wb") as f:
        f.write(build_index(cfg.get("name", "Birleşik depo"), cfg.get("badge", ""), records))
    print(f"{len(records)} eklenti -> {a.out}")


if __name__ == "__main__":
    main()
