#!/usr/bin/env python3
"""Scorecard for the Google Maps scraper API benchmark .

Four sub-scores out of 10, then an overall that keeps "data first":
  Data       weighted data points delivered, from semantic.py's meaning-based map (lead points weigh most:
             the article's lead-gen use case),
             x cleanliness (non-dental, duplicates, closed, placeholder contacts), x accuracy,
             x freshness (a database snapshot instead of a live scrape counts half)
  Cost       price per data point delivered (scale-plan price per place / fill-weighted data points per
             place), on one scale across every tool: the cheapest = 10, every 10x dearer = -2.5
  Speed      data points delivered per second (100 places with everything on, mean of runs), same scale:
             the fastest = 10, every 10x slower = -2.5
  Usability  a 10-point checklist (below)
  Overall    level floor (lead data 7, full profile 4, listing 1) + 0.27 x Data + 0.03 x mean(Cost, Speed,
             Usability). Within a level, Data carries 90% of the 3-point band, so less data only
             outranks more data when the data scores are close.
Reads analysis/compare_zip60605.json (Scrap.io from compare_city.json: no rows in the ZIP run).
Usage: python3 score.py   -> analysis/scorecard.json
Google Places is skipped when raw/ holds only its place IDs (as published): run `python3 run.py places
--area=zip60605` with your own key to score it.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
ZIP = json.load(open(os.path.join(HERE, 'analysis', 'compare_zip60605.json')))
CITY = json.load(open(os.path.join(HERE, 'analysis', 'compare_city.json')))

# data points: semantic.py's meaning-based map.
# Every point weighs 1, except the lead-gen points the article is built around:
# email 4, verified email 4, social profile 2. "Delivered" = filled on >= 10% of the tool's own results.
import semantic as S
LEAD_WEIGHTS = {'email': 4, 'verified email': 4, 'social profile': 2}
POINTS = [(p, LEAD_WEIGHTS.get(p, 1)) for p in S.POINTS]
MAX_POINTS = sum(w for _, w in POINTS)

TOOLS = {   # level, scale-plan price per 1K places in USD (midpoint where it's a range), seconds per 100 places per run
    # (city run, ZIP run). HasData's ZIP run returned 60 places in 53 s, scaled to 100.
    'lobstr_a':    {'name': 'lobstr.io (category + city input)', 'level': 1, 'price': 1.995, 'secs': (1854.1, 1233.2)},
    'lobstr_b':    {'name': 'lobstr.io (Maps URL input)', 'level': 1, 'price': 1.995, 'secs': (1684.2, 1249.0)},
    'apify':       {'name': 'Apify', 'level': 1, 'price': 4.91, 'secs': (292.8, 424.5)},
    'hasdata':     {'name': 'HasData', 'level': 1, 'price': 0.368, 'secs': (997.5, 53 * 100 / 60)},
    'scrapio':     {'name': 'Scrap.io', 'level': 1, 'price': 4.99, 'secs': (42.3,), 'area': 'city', 'snapshot': True},
    'outscraper':  {'name': 'Outscraper', 'level': 2, 'price': 1.00, 'secs': (42.9, 30.7)},
    'brightdata':  {'name': 'Bright Data', 'level': 2, 'price': 1.30, 'secs': (335.9, 273.7)},
    'dataforseo':  {'name': 'DataForSEO', 'level': 2, 'price': 0.02, 'secs': (14.3, 13.9)},
    'serpapi':     {'name': 'SerpApi', 'level': 3, 'price': 0.36, 'secs': (9.0, 9.9)},
    'scrapingdog': {'name': 'ScrapingDog', 'level': 3, 'price': 0.0225, 'secs': (7.9, 10.9)},
    'places':      {'name': 'Google Places (baseline)', 'level': 2, 'price': 2.00, 'secs': (8.0, 9.9), 'baseline': True},
}
# price notes: the email APIs are priced at a 33% email rate, lobstr.io's average across
# millions of rows, so no run's luck with emails moves the price. lobstr.io: 3 credits + 33% x (1 email + 2 verify)
# = 3.99 credits per place, Team $0.50/1K credits = $1.995. HasData: 3 credits + 33% x 7 = 5.31 credits, Growth
# $208/3M = $0.368. Apify bills its contact lookup per place with a website, not per email: measured $4.64-5.18.

USABILITY_ITEMS = ['official SDK', 'integrations (Make, Zapier, n8n or webhooks)', 'MCP server',
                   'flexible input (2 of: free text, structured location, Google Maps URL)', 'one typed record per business',
                   'run cost visible through the API', 'no blocker in our runs',
                   'error handling (failure reported by status or code, and failed work free or resumable)',
                   'no data lost when a run fails (queued jobs only)', 'results kept in the cloud 7 days or more (queued jobs only)']
# 1 = yes, 0 = no or not documented, None = doesn't apply (APIs that answer in the same call, and DataForSEO,
# tested in Live mode). Score = passed / applicable x 10. Sources: each vendor's docs and our own runs.
USABILITY = {
    'lobstr_a': ([1, 1, 1, 1, 0, 1, 1, 1, 1, 1], 'one row per email and numbers as text'),
    'apify': ([1, 1, 1, 1, 1, 1, 1, 1, 1, 1], 'a failed run can be resurrected with its data'),
    'hasdata': ([0, 1, 1, 0, 1, 1, 1, 0, 1, 0], 'CLI, no SDK; fixed category list (422 on free text); undocumented finished_with_error status, no retry; no stated retention'),
    'scrapio': ([0, 1, 1, 0, 1, 1, 0, 0, None, None], 'unranked (serves its own database); location codes and a category ID; "incomplete" with credits left; error handling not documented'),
    'outscraper': ([1, 1, 1, 1, 1, 0, 1, 0, 0, 0], 'run cost visible a day later; no documented retry or resume; a failed request has no results; 4 h retention'),
    'brightdata': ([1, 1, 1, 1, 1, 0, 0, 1, 0, 1], 'key cannot read the balance; a blocked domain and a stalled download; docs silent on partial data after a failure'),
    'dataforseo': ([1, 1, 1, 1, 1, 1, 1, 1, None, None], 'Live mode: queued-job checks n/a'),
    'serpapi': ([1, 1, 1, 1, 1, 1, 1, 1, None, None], 'synchronous'),
    'scrapingdog': ([1, 1, 1, 1, 1, 1, 1, 1, None, None], 'synchronous'),
    'places': ([1, 1, 1, 1, 1, 0, 0, 1, None, None], 'no run cost via the API; 60-result cap; integration via Make\'s own Google Maps app'),
}
USABILITY['lobstr_b'] = USABILITY['lobstr_a']


def log_score(x, unit):
    return max(0.0, min(10.0, 10 - 2.5 * math.log10(max(x, 1e-9) / unit)))


def data_score(key, cfg):
    rep = (CITY if cfg.get('area') == 'city' else ZIP)
    t = rep['tools'][key]
    w, clean = t['what_you_get'], t['is_it_clean']
    pct = {k: v['pct'] for k, v in w.items() if not k.startswith('_')}
    got = [(f, wt) for f, wt in POINTS if pct.get(f, 0) >= 10]
    points = sum(wt for _, wt in got)
    n = clean['records']
    dirty = (n - clean['dental']) + clean['duplicate_ids'] + clean['permanently_closed'] + clean['placeholder_phones'] \
        + len(clean['placeholder_emails'])
    clean_f = max(0.0, 1 - dirty / n)
    acc = (rep['is_it_right']['tools'][key]['agree_pct'] or 100) / 100
    fresh = 0.5 if cfg.get('snapshot') else 1.0
    score = 10 * points / MAX_POINTS * clean_f * acc * fresh
    return round(score, 2), {'points': points, 'of': MAX_POINTS, 'missing': [f for f, _ in POINTS if (f, _) not in got],
                              'clean_factor': round(clean_f, 3), 'accuracy': acc, 'freshness': fresh}


def value_per_place(key, cfg, detail):
    """Fill-weighted data points per place (same weights as Data), x cleanliness, accuracy, freshness."""
    sem = list(S.load('city' if cfg.get('area') == 'city' else 'zip60605', key).values())
    raw = sum(sum(w for p, w in POINTS if r[p]) for r in sem) / len(sem)
    return raw * detail['clean_factor'] * detail['accuracy'] * detail['freshness']


def peer_score(x, best, higher_is_better):
    ratio = (best / x) if higher_is_better else (x / best)
    return round(max(0.0, min(10.0, 10 - 2.5 * math.log10(max(ratio, 1.0)))), 2)


def main():
    out = []
    base = {}
    for key, cfg in TOOLS.items():
        d, detail = data_score(key, cfg)
        v = value_per_place(key, cfg, detail)
        if not v:   # the published raw/places keeps only place IDs (Google's terms): run run.py places first
            print(f"{cfg['name']}: no data to score in raw/, skipped")
            continue
        secs = sum(cfg['secs']) / len(cfg['secs'])
        base[key] = {'data': d, 'detail': detail, 'value': v,
                     'usd_per_1k_points': cfg['price'] / 1000 / v * 1000, 'points_per_sec': v * 100 / secs, 'secs': secs}
    # one scale across every tool, so scores compare across levels in one table.
    # Per data point, so more data isn't punished; the best of all tools (baseline excluded) = 10.
    peers = [k for k, c in TOOLS.items() if not c.get('baseline') and k in base]
    for k in base:
        base[k]['cost'] = peer_score(base[k]['usd_per_1k_points'], min(base[p]['usd_per_1k_points'] for p in peers), False)
        base[k]['speed'] = peer_score(base[k]['points_per_sec'], max(base[p]['points_per_sec'] for p in peers), True)
    for key, cfg in TOOLS.items():
        if key not in base:
            continue
        b = base[key]
        d, detail, cost, speed, secs = b['data'], b['detail'], b['cost'], b['speed'], b['secs']
        items, note = USABILITY[key]
        applicable = [i for i in items if i is not None]
        usab = round(10 * sum(applicable) / len(applicable), 2)
        floor = {1: 7.0, 2: 4.0, 3: 1.0}[cfg['level']]
        overall = round(floor + 0.27 * d + 0.03 * (cost + speed + usab) / 3, 2)
        out.append({'key': key, 'tool': cfg['name'], 'level': cfg['level'], 'baseline': cfg.get('baseline', False),
                    'data': d, 'cost': cost, 'speed': speed, 'usability': usab, 'overall': overall,
                    'inputs': {'price_per_1k_places': cfg['price'], 'seconds_per_100': round(secs, 1),
                               'data_points_per_place': round(b['value'], 1),
                               'usd_per_1k_data_points': round(b['usd_per_1k_points'], 4),
                               'data_points_per_second': round(b['points_per_sec'], 2)},
                    'data_detail': detail, 'usability_items': dict(zip(USABILITY_ITEMS, items)), 'usability_note': note})
    out.sort(key=lambda r: (r['baseline'], -r['overall']))
    with open(os.path.join(HERE, 'analysis', 'scorecard.json'), 'w') as f:
        json.dump(out, f, indent=1)
    for r in out:
        i = r['inputs']
        print(f"{r['tool']:26} L{r['level']}  data {r['data']:5.2f}  cost {r['cost']:5.2f}  speed {r['speed']:5.2f}  "
              f"usability {r['usability']:4.1f}  overall {r['overall']:5.2f}  | pts/place {i['data_points_per_place']:4.1f}  "
              f"$/1K pts {i['usd_per_1k_data_points']:.4f}  pts/s {i['data_points_per_second']:.2f}")


if __name__ == '__main__':
    main()
