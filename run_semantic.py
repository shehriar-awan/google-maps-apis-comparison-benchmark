#!/usr/bin/env python3
"""Data points per listing on the dentists every tool returned (ZIP 60605 run), and accuracy on them.

Prints: the number of listings shared by every tool, each tool's data points offered and filled per shared
listing, the fill of every data point, the values that differ from the majority, and scrape timestamps.
Usage: python3 run_semantic.py
"""
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from semantic import *
T = ['lobstr_a','lobstr_b','apify','outscraper','brightdata','dataforseo','places','hasdata','serpapi','scrapingdog']
D = {t: load('zip60605', t) for t in T}
shared = sorted(set.intersection(*[set(D[t]) for t in T]))
print('shared listings:', len(shared), '(Scrap.io left out: it serves a database, not a live scrape)')
# offered: point filled on at least one of the tool's own results in either run
def offered(t):
    allrecs = list(load('zip60605', t).values()) + (list(load('city', t if t!='hasdata' else 'hasdata_final').values()) if t!='scrapio' else [])
    return {p for p in POINTS if any(r[p] for r in allrecs)}
off = {t: offered(t) for t in T}
print(f'\n{"tool":12} offered(of {len(POINTS)})  filled per shared listing')
rows = []
for t in T:
    n = [sum(D[t][i][p] for p in POINTS) for i in shared]
    rows.append((t, len(off[t]), statistics.mean(n), min(n), max(n)))
for t, o, m, lo, hi in sorted(rows, key=lambda x: -x[2]):
    print(f'{t:12} {o:4}            {m:5.1f}  (range {lo}-{hi})')
print('\nper point, listings filled out of', len(shared))
cols = T
print(f'{"":24}' + ''.join(c[:8].ljust(9) for c in cols))
for p in POINTS:
    vals = [sum(D[t][i][p] for i in shared) for t in T]
    print(f'{p:24}' + ''.join(str(v).ljust(9) for v in vals))

# ---------- accuracy and freshness on the shared listings
import re
def norm(t, p, raw):
    v = J(raw.get(p))
    if v is None or v == '' : return None
    if p == 'phone': return C.digits(v)
    if p == 'website': return C.domain(v if isinstance(v, str) else str(v))
    if p in ('rating',): 
        try: return round(float(v), 1)
        except: return None
    if p in ('review count', 'photo count'):
        try: return int(str(v).rstrip('+'))
        except: return None
    if p == 'review distribution':
        if isinstance(v, dict):
            for k in ('fiveStar', '5', '5_star_reviews'):
                if k in v: return int(v[k])
        try: return int(v)
        except: return None
    if p == 'claimed': return str(v).lower() in ('true', '1')
    return v
AC = ['phone', 'website', 'rating', 'review count', 'review distribution', 'photo count', 'claimed']
allD = dict(D)
print('\naccuracy on the shared listings: values that differ from the majority')
for p in AC:
    bad = Counter(); comp_n = Counter()
    for i in shared:
        vals = {t: norm(t, p, allD[t][i]['_raw']) for t in allD if i in allD[t]}
        have = {t: v for t, v in vals.items() if v is not None}
        if len(have) < 3: continue
        top = Counter(have.values()).most_common(1)[0][0]
        for t, v in have.items():
            comp_n[t] += 1
            if v != top: bad[t] += 1; print(f'   {p:20} {t:12} {v!r} vs majority {top!r}  ({allD["apify"][i]["_raw"].get("full address","")[:30]})')
    print(f'{p:20} compared on {max(comp_n.values()) if comp_n else 0} listings; mismatches: {dict(bad) or "none"}')
print('\nscrape timestamps on Windy City Family Dental:')
w = 'ChIJN9ly9YgtDogRrK0Dj2T0H3M'
for t in ['lobstr_a','apify','brightdata']: print('  ', t, allD[t][w]['_raw'].get('scrape timestamp'))
