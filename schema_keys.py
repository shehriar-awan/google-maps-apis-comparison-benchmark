#!/usr/bin/env python3
"""Count the fields in each tool's output (the "Volume" field counts in the article).

Walks every row of both runs, nested keys and JSON inside strings included, and normalises the paths:
a dict whose keys are data rather than field names (days, hours, numbers, keys with spaces, or more than
12 distinct keys) counts as one field. Prints the counts and writes each tool's field list to
analysis/field_paths/paths_<tool>.json.
Usage: python3 schema_keys.py
"""
import os, sys, json, re
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare as C
DAY=re.compile(r'^(mon|tue|wed|thu|fri|sat|sun)[a-z]*$|^\d{1,2}(:\d\d)?\s?(AM|PM|am|pm)?$|^\d+$', re.I)
def walk(v, pre, out, kids):
    if isinstance(v, str) and v[:1] in '{[':
        try: v=json.loads(v)
        except Exception: pass
    if isinstance(v, dict):
        for k,x in v.items():
            kids[pre].add(k); walk(x, f'{pre}.{k}' if pre else k, out, kids)
        if not v: out.add(pre)
    elif isinstance(v, list):
        if not any(isinstance(x,(dict,list)) for x in v): out.add(pre+'[]')
        for x in v:
            if isinstance(x,(dict,list,str)): walk(x, pre+'[]', out, kids) if isinstance(x,(dict,list)) else None
    else: out.add(pre)
def norm(paths, kids):
    # a dict is a "map" (its keys are data, not fields) if it has >12 distinct keys, keys with spaces, or day/hour/number keys
    maps={p for p,ks in kids.items() if p and (len(ks)>12 or any(' ' in k or DAY.match(k) for k in ks))}
    out=set()
    for p in paths:
        parts=p.split('.'); orig=''; q=[]
        for part in parts:
            q.append('*' if orig in maps else part)
            orig=f'{orig}.{part}' if orig else part
        out.add('.'.join(q))
    out={re.sub(r'reviews_per_score_\d','reviews_per_score_*',x) for x in out}
    return out
for t in ['lobstr_a','apify','outscraper','hasdata','scrapio','serpapi','dataforseo','scrapingdog','places','brightdata']:
    paths=set(); kids=defaultdict(set); top=set()
    for area in ['zip60605','city']:
        if t not in C.AREAS[area]['tools']: continue
        for r in C.load(area,t)[0]:
            top|=set(r); walk(r,'',paths,kids)
    n=norm(paths,kids)
    print(f'{t:12} top-level {len(top):3}  raw incl. nested {len(paths):4}  normalised {len(n):4}')
    os.makedirs(os.path.join(HERE,'analysis','field_paths'),exist_ok=True)
    json.dump(sorted(n),open(os.path.join(HERE,'analysis','field_paths',f'paths_{t}.json'),'w'),indent=0)
