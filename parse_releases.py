#!/usr/bin/env python3
"""
Stream-parse a Discogs CC0 monthly releases dump into compact JSONL, keeping only
releases that carry at least one YouTube video (the only ones CrateDrop can play).

Usage (on the Pi, dump on the SSD):
  python3 -I parse_releases.py /mnt/ssd/discogs/discogs_20261101_releases.xml.gz /mnt/ssd/discogs/releases_yt.jsonl

Stdlib only, constant memory (elements are cleared as they stream past).
Source data: https://data.discogs.com/ (CC0 1.0, no rights reserved).
"""
import gzip
import json
import re
import sys
import xml.etree.ElementTree as ET

YT = re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})')


def text(el, path):
    x = el.find(path)
    return (x.text or '').strip() if x is not None and x.text else None


def main(src, dst):
    kept = seen = 0
    with gzip.open(src, 'rb') as fh, open(dst, 'w', encoding='utf-8') as out:
        root = None
        for ev, el in ET.iterparse(fh, events=('start', 'end')):
            if ev == 'start':
                if root is None:
                    root = el  # <releases>: cleared releases stay attached to it unless the root is cleared too
                continue
            if el.tag != 'release':
                continue
            seen += 1
            vids = []
            for v in el.findall('videos/video'):
                m = YT.search(v.get('src') or '')
                if m:
                    vids.append({'id': m.group(1), 'title': text(v, 'title'), 'sec': int(v.get('duration') or 0)})
            if vids and el.get('status', 'Accepted') == 'Accepted':
                released = text(el, 'released') or ''
                year = int(released[:4]) if released[:4].isdigit() else None
                labels = el.findall('labels/label')
                fmts = el.findall('formats/format')
                master = el.find('master_id')
                out.write(json.dumps({
                    'id': int(el.get('id')),
                    'title': text(el, 'title'),
                    'artists': [a.text for a in el.findall('artists/artist/name') if a.text],
                    'year': year,
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
                }, ensure_ascii=False) + '\n')
                kept += 1
            el.clear()
            root.clear()  # drop the finished release from the tree: constant memory (26 Nov: the leak took down the Pi)
            if seen % 500_000 == 0:
                print(f'{seen:,} releases read, {kept:,} kept', file=sys.stderr, flush=True)
    print(f'done: {seen:,} releases read, {kept:,} with YouTube videos', file=sys.stderr)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
