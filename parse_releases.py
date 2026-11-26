#!/usr/bin/env python3
"""
Stream-parse a Discogs CC0 monthly releases dump into compact JSONL, keeping only
releases that carry at least one YouTube video (the only ones CrateDrop can play).

Usage:
  python3 -I parse_releases.py discogs_YYYYMM01_releases.xml.gz releases_yt.jsonl
  pigz -dc discogs_YYYYMM01_releases.xml.gz | python3 -I parse_releases.py - releases_yt.jsonl   # faster: decompress on another core

Constant memory: every finished release is removed from the tree (26 Nov 2026: without that the tree grew until the
Pi ran out of RAM). Uses lxml when installed (several times faster), else the standard library.
Source data: https://data.discogs.com/ (CC0 1.0, no rights reserved).
"""
import gzip
import json
import re
import sys

try:
    from lxml import etree as ET
    LXML = True
except ImportError:  # pragma: no cover
    import xml.etree.ElementTree as ET
    LXML = False

YT = re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})')


def text(el, path):
    x = el.find(path)
    return (x.text or '').strip() if x is not None and x.text else None


def record(el):
    vids = []
    for v in el.findall('videos/video'):
        m = YT.search(v.get('src') or '')
        if m:
            vids.append({'id': m.group(1), 'title': text(v, 'title'), 'sec': int(v.get('duration') or 0)})
    if not vids or el.get('status', 'Accepted') != 'Accepted':
        return None
    released = text(el, 'released') or ''
    labels = el.findall('labels/label')
    fmts = el.findall('formats/format')
    master = el.find('master_id')
    return {
        'id': int(el.get('id')),
        'title': text(el, 'title'),
        'artists': [a.text for a in el.findall('artists/artist/name') if a.text],
        'year': int(released[:4]) if released[:4].isdigit() else None,
        'country': text(el, 'country'),
        'genres': [g.text for g in el.findall('genres/genre') if g.text],
        'styles': [s.text for s in el.findall('styles/style') if s.text],
        'label': labels[0].get('name') if labels else None,
        'catno': labels[0].get('catno') if labels else None,
        'format': fmts[0].get('name') if fmts else None,
        'format_desc': [d.text for f in fmts for d in f.findall('descriptions/description') if d.text],
        'master': int(master.text) if master is not None and master.text else None,
        'main': master is not None and master.get('is_main_release') == 'true',
        'videos': vids,
    }


def main(src, dst):
    kept = seen = 0
    fh = sys.stdin.buffer if src == '-' else gzip.open(src, 'rb')
    with fh, open(dst, 'w', encoding='utf-8') as out:
        if LXML:
            events = ET.iterparse(fh, events=('end',), tag='release', huge_tree=True)
        else:
            events = ET.iterparse(fh, events=('start', 'end'))
        root = None
        for ev, el in events:
            if not LXML:
                if ev == 'start':
                    if root is None:
                        root = el
                    continue
                if el.tag != 'release':
                    continue
            seen += 1
            r = record(el)
            if r:
                out.write(json.dumps(r, ensure_ascii=False) + '\n')
                kept += 1
            el.clear()
            if LXML:
                while el.getprevious() is not None:  # drop finished siblings held by the parent
                    del el.getparent()[0]
            else:
                root.clear()
            if seen % 500_000 == 0:
                print(f'{seen:,} releases read, {kept:,} kept', file=sys.stderr, flush=True)
    print(f'done: {seen:,} releases read, {kept:,} with YouTube videos', file=sys.stderr)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
