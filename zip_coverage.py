#!/usr/bin/env python3
"""Businesses inside ZIP 60605 found by each tool in the ZIP run, and by all of them together.

A business counts as in the ZIP when its ZIP field (or the ZIP in its address) is 60605. The union adds
raw/zip60605/lobstr_200_results_run/, an extra lobstr.io run on the same search with up to 200 results,
which found businesses none of the 100-result runs returned. Prints the counts with every category, and
with dental categories only (compare.py's dental check).
Google Places counts only when raw/zip60605/places holds full results (run.py places --area=zip60605).
Usage: python3 zip_coverage.py
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare as C

EXTRA = 'lobstr_200_results_run'


def in_zip(tool, dental):
    rows = json.load(open(os.path.join(HERE, 'raw', 'zip60605', tool, 'results.json')))
    recs = C.m_lobstr(rows) if tool.startswith('lobstr') else C.MAP[tool](rows)
    out = {}
    for r in recs:
        if r.get('zip') != '60605' or not r.get('id'):
            continue
        if dental and not C.DENTAL.search(str(r.get('category') or '') + ' ' + json.dumps(r.get('categories'))):
            continue
        out[r['id']] = r.get('name')
    return out


for dental in (False, True):
    found = {t: in_zip(t, dental) for t in C.AREAS['zip60605']['tools'] + [EXTRA]}
    bench = set().union(*[set(v) for t, v in found.items() if t != EXTRA])
    extra_only = set(found[EXTRA]) - bench
    total = len(bench | extra_only)
    print(f"\n{'dental categories only' if dental else 'every category'}: {total} businesses in ZIP 60605 "
          f"({len(bench)} from the benchmark runs + {len(extra_only)} only in the 200-result lobstr.io run)")
    for t, v in sorted(found.items(), key=lambda x: -len(x[1])):
        print(f'  {t:24} {len(v):3} of {total}')
    if extra_only:
        print('  only in the 200-result run:', ', '.join(sorted(found[EXTRA][i] for i in extra_only)))
