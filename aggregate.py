#!/usr/bin/env python3
"""
Aggregate releases_yt.jsonl (from parse_releases.py) into page stats and write a SQL file for D1 seo_stats.

Usage (on the Pi):
  python3 -I aggregate.py releases_yt.jsonl seo_stats_discogs.sql 20261101

Kinds written (slug = same rules as statSlug() in src/lib/seoStats.ts):
  d_style, d_country, d_year, d_style_decade ("soul-jazz--1960s"), d_label, d_site
Only groups with enough releases are written (MIN_* below). Stdlib only, two passes over the file is avoided:
counters are kept per group in memory (a few hundred MB for ~4M releases).
"""
import json
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict

MIN = {'d_style': 100, 'd_country': 100, 'd_year': 500, 'd_style_decade': 300, 'd_label': 200}
SAMPLE = 16


def slug(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower().replace('&', ' and ')
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def clean_label(l):
    if not l:
        return None
    l = re.sub(r'\s*\(\d+\)$', '', l).strip()
    return None if l in ('Not On Label', '') or l.startswith('Not On Label') else l


class G:
    __slots__ = ('n', 'decades', 'years', 'labels', 'countries', 'styles', 'genres', 'formats', 'desc', 'artists', 'main', 'reissue', 'comp', 'sample', 'seen')

    def __init__(self):
        self.n = 0
        self.decades = Counter(); self.years = Counter(); self.labels = Counter(); self.countries = Counter()
        self.styles = Counter(); self.genres = Counter(); self.formats = Counter(); self.desc = Counter(); self.artists = Counter()
        self.main = 0; self.reissue = 0; self.comp = 0
        self.sample = []; self.seen = 0

    def add(self, r, skip_style=None):
        self.n += 1
        y = r.get('year')
        if y and 1900 < y < 2030:
            self.years[y] += 1
            self.decades[f'{y // 10 * 10}s'] += 1
        lab = clean_label(r.get('label'))
        if lab:
            self.labels[lab] += 1
        if r.get('country') and r['country'] != 'Unknown':
            self.countries[r['country']] += 1
        for s in r.get('styles') or []:
            if s != skip_style:
                self.styles[s] += 1
        for g in r.get('genres') or []:
            self.genres[g] += 1
        if r.get('format'):
            self.formats[r['format']] += 1
        d = set(r.get('format_desc') or [])
        for k in ('LP', '7"', '12"', 'EP', 'Single', 'Album', 'Compilation', 'Reissue', 'Remastered', 'Promo', 'Limited Edition', 'Mono', 'Stereo'):
            if k in d:
                self.desc[k] += 1
        if 'Reissue' in d or 'Repress' in d:
            self.reissue += 1
        if 'Compilation' in d:
            self.comp += 1
        if r.get('main'):
            self.main += 1
        for a in (r.get('artists') or [])[:1]:
            a = re.sub(r'\s*\(\d+\)$', '', a)
            if a and a != 'Various':
                self.artists[a] += 1
        # Reservoir sample of playable records (prefer main releases with an artist and a year).
        if r.get('artists') and r.get('year') and r.get('main') and r.get('videos'):
            self.seen += 1
            item = (r['id'], re.sub(r'\s*\(\d+\)$', '', r['artists'][0]), r.get('title'), r.get('year'), r.get('country'), lab, r['videos'][0]['id'])
            if len(self.sample) < SAMPLE:
                self.sample.append(item)
            else:
                j = random.randrange(self.seen)
                if j < SAMPLE:
                    self.sample[j] = item

    def out(self, kind):
        top = lambda c, k: [{'name': a, 'n': b} for a, b in c.most_common(k)]
        yrs = sorted(self.years.elements()) if self.n < 400_000 else None
        median = yrs[len(yrs) // 2] if yrs else (self.years.most_common(1)[0][0] if self.years else None)
        return {
            'source': 'discogs',
            'genres': top(self.genres, 8),
            'decades': [{'name': k, 'n': v} for k, v in sorted(self.decades.items())],
            'labels': top(self.labels, 15),
            'countries': top(self.countries, 12),
            'styles': top(self.styles, 15),
            'artists': top(self.artists, 12),
            'formats': top(self.formats, 6),
            'desc': dict(self.desc),
            'peakYear': self.years.most_common(1)[0][0] if self.years else None,
            'yearMin': min(self.years) if self.years else None,
            'yearMax': max(self.years) if self.years else None,
            'medianYear': median,
            'mainShare': round(self.main / self.n, 3) if self.n else 0,
            'reissueShare': round(self.reissue / self.n, 3) if self.n else 0,
            'compShare': round(self.comp / self.n, 3) if self.n else 0,
            'records': [{'discogs': i, 'artist': a, 'title': t, 'year': y, 'country': c, 'label': l, 'yt': v} for (i, a, t, y, c, l, v) in self.sample],
        }


def main(src, dst, dump):
    random.seed(42)
    groups = defaultdict(G)
    names = {}
    total = 0
    with open(src, encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            total += 1
            y = r.get('year')
            dec = f'{y // 10 * 10}s' if y and 1900 < y < 2030 else None
            for s in set(r.get('styles') or []):
                k = ('d_style', slug(s)); names[k] = s; groups[k].add(r, skip_style=s)
                if dec:
                    k2 = ('d_style_decade', f'{slug(s)}--{dec}'); names[k2] = f'{s}|{dec}'; groups[k2].add(r, skip_style=s)
            c = r.get('country')
            if c and c != 'Unknown':
                k = ('d_country', slug(c)); names[k] = c; groups[k].add(r)
            if y and 1900 < y < 2030:
                k = ('d_year', str(y)); names[k] = str(y); groups[k].add(r)
            lab = clean_label(r.get('label'))
            if lab:
                k = ('d_label', slug(lab)); names.setdefault(k, lab); groups[k].add(r)
            if total % 500_000 == 0:
                print(f'{total:,} read, {len(groups):,} groups', file=sys.stderr, flush=True)

    rows = 0
    q = lambda s: "'" + s.replace("'", "''") + "'"
    with open(dst, 'w', encoding='utf-8') as out:
        for (kind, sl), g in groups.items():
            if not sl or g.n < MIN[kind]:
                continue
            data = json.dumps(g.out(kind), ensure_ascii=False, separators=(',', ':'))
            out.write(f"INSERT INTO seo_stats (kind, slug, name, n, data, updated_at) VALUES ({q(kind)}, {q(sl)}, {q(names[(kind, sl)])}, {g.n}, {q(data)}, datetime('now')) "
                      f"ON CONFLICT(kind, slug) DO UPDATE SET name=excluded.name, n=excluded.n, data=excluded.data, updated_at=excluded.updated_at;\n")
            rows += 1
        site = json.dumps({'releases': total, 'dump': dump, 'styles': sum(1 for (k, s), g in groups.items() if k == 'd_style' and g.n >= MIN['d_style'])})
        out.write(f"INSERT INTO seo_stats (kind, slug, name, n, data, updated_at) VALUES ('d_site', 'all', 'all', {total}, {q(site)}, datetime('now')) "
                  f"ON CONFLICT(kind, slug) DO UPDATE SET n=excluded.n, data=excluded.data, updated_at=excluded.updated_at;\n")
    print(f'done: {total:,} releases, {rows:,} rows written', file=sys.stderr)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
