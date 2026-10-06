#!/usr/bin/env python3
"""Google Maps scraper API benchmark: one search per tool, everything the scraper offers.

Search: dentists in Chicago, IL (area "city", 2026-09-30) or in ZIP 60605 (area "zip60605").
Up to 100 listings or 10 pages. One run per tool.
No reviews, no chaining of other products (what each tool is sent: README.md).

Usage:  python3 run.py <tool> [--area=zip60605]   tools: lobstr_a lobstr_b apify outscraper hasdata
                                                         serpapi dataforseo scrapio scrapingdog places brightdata
        python3 run.py <tool> --dry               print the requests without sending them

Every request and response is saved under raw/<tool>/ (city) or raw/zip60605/<tool>/, API keys stripped.
meta.json holds the input, the timings, the account usage counters before and after, and the request log.
(In the published raw/ files, account details, reviewer names and email local parts are removed: README.md.)
"""
import base64, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')   # copy .env.example to .env
HERE = os.path.dirname(os.path.abspath(__file__))

KEYWORD = 'dentists'
MAX = 100
# center and zoom are for the tools that need coordinates. 60605's center and viewport (3.4 x 2.6 km)
# come from the Places API postal_code place ChIJARaEdH8rDogRqY8RW-yyHyY; zoom 14 covers it.
AREAS = {
    'city': {'query': 'dentists in Chicago, IL', 'center': (41.8781, -87.6298, 12), 'raw': 'raw',
             'lobstr_city': 'Chicago', 'apify_location': 'Chicago, IL, USA',
             'hasdata_location': 'Chicago, IL', 'hasdata_limit': MAX, 'scrapio': {'city': 'Chicago'}},
    'zip60605': {'query': 'dentists in Chicago, IL 60605', 'center': (41.8703, -87.6236, 14), 'raw': 'raw/zip60605',
                 'lobstr_city': 'Chicago 60605', 'apify_location': '60605, Chicago, IL, USA',
                 # HasData capped at 60 in the ZIP run: only that many free credits were left
                 'hasdata_location': 'Chicago, IL 60605', 'hasdata_limit': 60,
                 'scrapio': {'city': 'Chicago', 'postal_code': '60605'}},
}
AREA_NAME = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--area=')), 'city')
AREA = AREAS[AREA_NAME]
QUERY = AREA['query']
CENTER = AREA['center']
LL = f'@{CENTER[0]},{CENTER[1]},{CENTER[2]}z'


def load_env():
    env = {}
    for line in open(ENV_PATH):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()
SECRETS = [v for v in ENV.values() if len(v) > 8]


def redact(obj):
    s = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    for v in SECRETS:
        s = s.replace(v, '<key>')
    return s


def now():
    return time.time()


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


class Recorder:
    def __init__(self, tool, dry=False):
        self.tool, self.dry = tool, dry
        self.dir = os.path.join(HERE, AREA['raw'], tool)
        if not dry:   # a dry run never touches raw/
            os.makedirs(self.dir, exist_ok=True)
        self.log, self.n, self.meta = [], 0, {'tool': tool, 'area': AREA_NAME, 'query': QUERY}

    def req(self, method, url, headers=None, body=None, timeout=120):
        self.n += 1
        entry = {'n': self.n, 'method': method, 'url': redact(url), 'body': json.loads(redact(body)) if body is not None else None}
        if self.dry:
            print(f'[dry] {method} {redact(url)}  {redact(body) if body is not None else ""}')
            self.log.append(entry)
            return 0, None
        data = json.dumps(body).encode() if body is not None else None
        h = {'User-Agent': 'lobstr-benchmark/1.0', 'Accept': 'application/json', **(headers or {})}
        if data is not None:
            h.setdefault('Content-Type', 'application/json')
        t0 = now()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h, method=method), timeout=timeout) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        except Exception as e:
            status, raw = 'ERR', str(e).encode()
        t1 = now()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw.decode('utf-8', 'replace')
        entry.update({'status': status, 'started': iso(t0), 'seconds': round(t1 - t0, 3)})
        self.log.append(entry)
        with open(os.path.join(self.dir, f'{self.n:03d}.json'), 'w') as f:
            f.write(redact({'request': entry, 'response': parsed}))
        return status, parsed

    def save(self, results):
        self.meta['requests'] = self.log
        if self.dry:
            return print(json.dumps({k: v for k, v in self.meta.items() if k != 'requests'}, indent=1, default=str)[:3000])
        with open(os.path.join(self.dir, 'meta.json'), 'w') as f:
            f.write(redact(self.meta))
        if results is not None:
            with open(os.path.join(self.dir, 'results.json'), 'w') as f:
                f.write(redact(results))
        print(json.dumps({k: v for k, v in self.meta.items() if k != 'requests'}, indent=1, default=str)[:3000])


def poll(fn, done, every=5, timeout=3600):
    """Call fn() until done(result) is true; returns the last result."""
    t0 = now()
    while True:
        r = fn()
        if done(r) or now() - t0 > timeout:
            return r
        time.sleep(every)


# ---------------------------------------------------------------- lobstr.io
LOBSTR = 'https://api.lobstr.io/v1'
LOBSTR_CRAWLER = '4734d096159ef05210e0e1677e8be823'   # Google Maps Leads Scraper


def lobstr(rec, mode):
    H = {'Authorization': 'Token ' + ENV['LOBSTR_API_KEY']}
    task = ({'category': 'dentist', 'country': 'United States', 'city': AREA['lobstr_city']} if mode == 'a'
            else {'url': f"https://www.google.com/maps/search/{QUERY.replace(' ', '+')}/{LL}"})
    rec.meta['input'] = task
    _, bal = rec.req('GET', f'{LOBSTR}/user/balance', H)
    rec.meta['balance_before'] = bal
    _, sq = rec.req('POST', f'{LOBSTR}/squids', H, {'crawler': LOBSTR_CRAWLER, 'name': f'benchmark dentists {AREA_NAME} {mode}'})
    if rec.dry:
        sid = 'SQUID'
    else:
        sid = (sq or {}).get('id')
        if not sid:
            rec.meta['error'] = 'squid not created'; return rec.save(None)
    rec.meta['squid'] = sid
    rec.req('POST', f'{LOBSTR}/squids/{sid}', H, {
        'params': {'country': 'United States', 'language': 'English (United States)', 'max_results': MAX,
                   'auto_verify_emails': True,
                   'functions': {'extract_emails_from_website': True, 'collect_business_details': True,
                                 'fetch_business_images': True}},
        'export_unique_results': True})
    st, t = rec.req('POST', f'{LOBSTR}/tasks', H, {'squid': sid, 'tasks': [task]})
    rec.meta['add_tasks_status'] = st
    if not rec.dry and st not in (200, 201):
        rec.meta['error'] = 'tasks rejected'; return rec.save(None)
    t0 = now(); rec.meta['submitted'] = iso(t0)
    _, run = rec.req('POST', f'{LOBSTR}/runs', H, {'squid': sid})
    if rec.dry:
        return rec.save(None)
    rid = (run or {}).get('id'); rec.meta['run'] = rid
    last = poll(lambda: rec.req('GET', f'{LOBSTR}/runs/{rid}', H)[1],
                lambda r: isinstance(r, dict) and r.get('status') in ('done', 'error', 'aborted'), every=10)
    t_done = now(); rec.meta['run_status_done'] = iso(t_done); rec.meta['seconds_to_run_done'] = round(t_done - t0, 1)
    rec.meta['run_final'] = last

    def fetch():
        return rec.req('GET', f'{LOBSTR}/results?run={rid}&page=1&page_size={MAX}', H)[1]

    def verified(r):
        rows = (r or {}).get('data') or []
        with_email = [x for x in rows if x.get('email')]
        return rows and all(x.get('email_status') for x in with_email)
    res = poll(fetch, verified, every=30, timeout=3600)   # verification can finish after "done"
    t_all = now(); rec.meta['all_emails_verified'] = iso(t_all); rec.meta['seconds_total'] = round(t_all - t0, 1)
    rec.meta['rows_returned_page1'] = len((res or {}).get('data') or [])
    rec.meta['results_paging'] = {k: v for k, v in (res or {}).items() if k != 'data'}
    rec.meta['run_credits'] = rec.req('GET', f'{LOBSTR}/runs/{rid}/credits', H)[1]
    rec.meta['balance_after'] = rec.req('GET', f'{LOBSTR}/user/balance', H)[1]
    rec.save((res or {}).get('data'))


# ---------------------------------------------------------------- Apify compass
def apify(rec):
    H = {'Authorization': 'Bearer ' + ENV['APIFY_API_KEY']}
    inp = {'searchStringsArray': [KEYWORD], 'locationQuery': AREA['apify_location'], 'maxCrawledPlacesPerSearch': MAX,
           'language': 'en', 'scrapeContacts': True, 'scrapePlaceDetailPage': True, 'maxImages': 10,
           'includeWebResults': True, 'maxReviews': 0, 'maximumLeadsEnrichmentRecords': 0,
           'scrapeSocialMediaProfiles': {'facebooks': False, 'instagrams': False, 'youtubes': False,
                                         'tiktoks': False, 'twitters': False}}
    rec.meta['input'] = inp
    rec.meta['limits_before'] = rec.req('GET', 'https://api.apify.com/v2/users/me/limits', H)[1]
    t0 = now(); rec.meta['submitted'] = iso(t0)
    _, run = rec.req('POST', 'https://api.apify.com/v2/acts/compass~crawler-google-places/runs', H, inp)
    if rec.dry:
        return rec.save(None)
    rid = run['data']['id']; ds = run['data']['defaultDatasetId']; rec.meta['run'] = rid
    last = poll(lambda: rec.req('GET', f'https://api.apify.com/v2/actor-runs/{rid}', H)[1],
                lambda r: r['data']['status'] in ('SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'), every=10)
    items = rec.req('GET', f'https://api.apify.com/v2/datasets/{ds}/items?clean=true&format=json', H)[1]
    t1 = now(); rec.meta['seconds_total'] = round(t1 - t0, 1)
    d = last['data']
    rec.meta['run_final'] = {k: d.get(k) for k in ('status', 'startedAt', 'finishedAt', 'usageTotalUsd',
                                                   'chargedEventCounts', 'stats', 'pricingInfo')}
    rec.meta['rows'] = len(items) if isinstance(items, list) else None
    rec.meta['limits_after'] = rec.req('GET', 'https://api.apify.com/v2/users/me/limits', H)[1]
    rec.save(items)


# ---------------------------------------------------------------- Outscraper (listings only)
def outscraper(rec):
    H = {'X-API-KEY': ENV['OUTSCRAPER_API_KEY']}
    base = 'https://api.app.outscraper.com'
    body = {'query': [QUERY], 'language': 'en', 'region': 'US', 'organizationsPerQueryLimit': MAX,
            'skipPlaces': 0, 'dropDuplicates': False, 'async': True}
    rec.meta['input'] = body
    rec.meta['balance_before'] = rec.req('GET', f'{base}/profile/balance', H)[1]
    t0 = now(); rec.meta['submitted'] = iso(t0)
    _, sub = rec.req('POST', f'{base}/google-maps-search', H, body)
    if rec.dry:
        return rec.save(None)
    rid = sub.get('id'); rec.meta['request_id'] = rid
    res = poll(lambda: rec.req('GET', f'{base}/requests/{rid}', H)[1],
               lambda r: isinstance(r, dict) and r.get('status') != 'Pending', every=5)
    t1 = now(); rec.meta['seconds_total'] = round(t1 - t0, 1)
    data = res.get('data') or []
    rows = data[0] if data and isinstance(data[0], list) else data
    rec.meta['status_final'] = res.get('status'); rec.meta['rows'] = len(rows)
    rec.meta['balance_after'] = rec.req('GET', f'{base}/profile/balance', H)[1]
    rec.save(rows)


# ---------------------------------------------------------------- HasData (extractEmails only)
def hasdata(rec):
    H = {'x-api-key': ENV['HASDATA_API_KEY']}
    base = 'https://api.hasdata.com'
    # categories is a fixed enum (a 422 lists the choices): 'dentist' is valid, free text like 'dentists' is not
    body = {'limit': AREA['hasdata_limit'], 'categories': ['dentist'], 'locations': [AREA['hasdata_location']],
            'extractEmails': True}
    rec.meta['input'] = body
    t0 = now(); rec.meta['submitted'] = iso(t0)
    st, job = rec.req('POST', f'{base}/scrapers/google-maps/jobs', H, body)
    if rec.dry:
        return rec.save(None)
    if st not in (200, 201) or not isinstance(job, dict) or not job.get('id'):
        rec.meta['error'] = 'job not created'; return rec.save(None)
    jid = job['id']; rec.meta['job'] = jid
    state = {'prev': None}

    def check():
        j = rec.req('GET', f'{base}/scrapers/jobs/{jid}', H)[1]
        r = rec.req('GET', f'{base}/scrapers/jobs/{jid}/results?page=1&limit={MAX}', H)[1]
        return {'job': j, 'results': r}

    def done(x):
        j, r = x['job'] or {}, x['results'] or {}
        # a job that reaches its limit ends as finished_with_error (stopReason data_limit_exceeded)
        if j.get('status') in ('finished', 'finished_with_error', 'completed', 'failed', 'error'):
            return True
        total = ((r.get('meta') or {}).get('total'))
        rows = int(j.get('dataRowsCount') or 0)   # dataRowsCount comes back as a string
        stable = total is not None and total == rows and total == state['prev'] and total > 0
        state['prev'] = total
        return stable
    last = poll(check, done, every=10)
    t1 = now(); rec.meta['seconds_total'] = round(t1 - t0, 1)
    rec.meta['job_final'] = last['job']
    rows = [x.get('data', x) for x in ((last['results'] or {}).get('data') or [])]
    rec.meta['rows'] = len(rows)
    rec.save(rows)


# ---------------------------------------------------------------- SerpApi
def serpapi(rec):
    key = ENV['SERPAPI_API_KEY']
    rec.meta['input'] = {'engine': 'google_maps', 'q': QUERY, 'type': 'search', 'hl': 'en', 'gl': 'us', 'start': '0..80'}
    rec.meta['account_before'] = rec.req('GET', f'https://serpapi.com/account.json?api_key={key}')[1]
    t0 = now(); rec.meta['submitted'] = iso(t0); rows = []
    for start in range(0, MAX, 20):
        q = urllib.parse.urlencode({'engine': 'google_maps', 'q': QUERY, 'type': 'search', 'hl': 'en', 'gl': 'us',
                                    'start': start, 'api_key': key})
        _, r = rec.req('GET', f'https://serpapi.com/search.json?{q}')
        if rec.dry:
            continue
        page = (r or {}).get('local_results') or []
        rows += page
        if len(page) < 20:
            break
    rec.meta['seconds_total'] = round(now() - t0, 1); rec.meta['rows'] = len(rows)
    rec.meta['account_after'] = rec.req('GET', f'https://serpapi.com/account.json?api_key={key}')[1]
    rec.save(rows if not rec.dry else None)


# ---------------------------------------------------------------- DataForSEO (live endpoint)
def dataforseo(rec):
    a = base64.b64encode(f"{ENV['DATAFORSEO_API_LOGIN']}:{ENV['DATAFORSEO_API_PASSWORD']}".encode()).decode()
    H = {'Authorization': 'Basic ' + a}
    body = [{'keyword': QUERY, 'location_name': 'Chicago,Illinois,United States', 'language_code': 'en', 'depth': MAX}]
    rec.meta['input'] = body
    rec.meta['user_before'] = rec.req('GET', 'https://api.dataforseo.com/v3/appendix/user_data', H)[1]
    t0 = now(); rec.meta['submitted'] = iso(t0)
    _, r = rec.req('POST', 'https://api.dataforseo.com/v3/serp/google/maps/live/advanced', H, body, timeout=300)
    rec.meta['seconds_total'] = round(now() - t0, 1)
    if rec.dry:
        return rec.save(None)
    task = (r.get('tasks') or [{}])[0]
    rows = ((task.get('result') or [{}])[0] or {}).get('items') or []
    rec.meta['cost'] = r.get('cost'); rec.meta['status_message'] = task.get('status_message'); rec.meta['rows'] = len(rows)
    rec.meta['user_after'] = rec.req('GET', 'https://api.dataforseo.com/v3/appendix/user_data', H)[1]
    rec.save(rows)


# ---------------------------------------------------------------- Scrap.io
def scrapio(rec):
    H = {'Authorization': 'Bearer ' + ENV['SCRAPIO_API_KEY']}
    params = {'country_code': 'US', 'admin1_code': 'IL', **AREA['scrapio'], 'type': 'dentist', 'per_page': 50}
    rec.meta['input'] = params
    rec.meta['subscription_before'] = rec.req('GET', 'https://scrap.io/api/v1/subscription', H)[1]
    t0 = now(); rec.meta['submitted'] = iso(t0); rows = []; cursor = None
    while len(rows) < MAX:
        p = dict(params, **({'cursor': cursor} if cursor else {}))
        _, r = rec.req('GET', 'https://scrap.io/api/v1/gmap/search?' + urllib.parse.urlencode(p), H)
        if rec.dry:
            break
        page = (r or {}).get('data') or []
        rows += page
        cursor = ((r or {}).get('meta') or {}).get('next_cursor') or (r or {}).get('next_cursor')
        if not page or not cursor:
            break
    rec.meta['seconds_total'] = round(now() - t0, 1); rec.meta['rows'] = len(rows)
    rec.meta['subscription_after'] = rec.req('GET', 'https://scrap.io/api/v1/subscription', H)[1]
    rec.save(rows[:MAX] if not rec.dry else None)


# ---------------------------------------------------------------- ScrapingDog
def scrapingdog(rec):
    key = ENV['SCRAPINGDOG_API_KEY']
    rec.meta['input'] = {'query': KEYWORD, 'll': LL, 'page': '0..80'}
    rec.meta['account_before'] = rec.req('GET', f'https://api.scrapingdog.com/account?api_key={key}')[1]
    t0 = now(); rec.meta['submitted'] = iso(t0); rows = []
    for page in range(0, MAX, 20):
        q = urllib.parse.urlencode({'api_key': key, 'query': KEYWORD, 'll': LL, 'page': page})
        _, r = rec.req('GET', f'https://api.scrapingdog.com/google_maps?{q}')
        if rec.dry:
            continue
        pg = (r or {}).get('search_results') or [] if isinstance(r, dict) else []
        rows += pg
        if len(pg) < 20:
            break
    rec.meta['seconds_total'] = round(now() - t0, 1); rec.meta['rows'] = len(rows)
    rec.meta['account_after'] = rec.req('GET', f'https://api.scrapingdog.com/account?api_key={key}')[1]
    rec.save(rows if not rec.dry else None)


# ---------------------------------------------------------------- Google Places API (New)
PLACES_FIELDS = [
    # Essentials / Pro
    'id', 'displayName', 'formattedAddress', 'shortFormattedAddress', 'addressComponents', 'adrFormatAddress',
    'location', 'viewport', 'plusCode', 'types', 'primaryType', 'primaryTypeDisplayName', 'googleMapsUri',
    'googleMapsLinks', 'businessStatus', 'utcOffsetMinutes', 'photos', 'pureServiceAreaBusiness',
    'postalAddress', 'timeZone', 'containingPlaces', 'attributions',
    # Enterprise
    'nationalPhoneNumber', 'internationalPhoneNumber', 'websiteUri', 'rating', 'userRatingCount',
    'priceLevel', 'priceRange', 'regularOpeningHours', 'currentOpeningHours',
    'regularSecondaryOpeningHours', 'currentSecondaryOpeningHours',
    # Enterprise + Atmosphere (everything except reviews)
    'editorialSummary', 'accessibilityOptions', 'paymentOptions', 'parkingOptions', 'goodForChildren',
    'goodForGroups', 'allowsDogs', 'restroom', 'reservable', 'takeout', 'delivery', 'dineIn', 'curbsidePickup',
    'outdoorSeating', 'liveMusic', 'menuForChildren', 'servesBreakfast', 'servesLunch', 'servesDinner',
    'servesBeer', 'servesWine', 'servesBrunch', 'servesVegetarianFood', 'servesCocktails', 'servesCoffee',
    'servesDessert', 'goodForWatchingSports', 'generativeSummary',
]


def places(rec, fields=None):
    fields = fields or PLACES_FIELDS
    H = {'X-Goog-Api-Key': ENV['GOOGLE_PLACES_API'],
         'X-Goog-FieldMask': ','.join(['places.' + f for f in fields] + ['nextPageToken'])}
    rec.meta['input'] = {'textQuery': QUERY, 'pageSize': 20, 'fields': fields}
    t0 = now(); rec.meta['submitted'] = iso(t0); rows = []; token = None
    for _ in range(3):   # Google's cap: 60 results across 3 pages
        body = {'textQuery': QUERY, 'pageSize': 20, **({'pageToken': token} if token else {})}
        st, r = rec.req('POST', 'https://places.googleapis.com/v1/places:searchText', H, body)
        if rec.dry:
            break
        if st != 200:
            rec.meta['error'] = r; break
        rows += r.get('places') or []
        token = r.get('nextPageToken')
        if not token:
            break
        time.sleep(2)   # a page token needs a moment before it's valid
    rec.meta['seconds_total'] = round(now() - t0, 1); rec.meta['rows'] = len(rows)
    rec.save(rows if not rec.dry else None)


# ---------------------------------------------------------------- Bright Data (Google Maps full information)
BRIGHTDATA_DATASET = 'gd_m8ebnr0q2qlklc02fz'


def brightdata(rec):
    H = {'Authorization': 'Bearer ' + ENV['BRIGHTDATA_API_KEY']}
    base = 'https://api.brightdata.com'
    # discover by location has no city or ZIP field: the area's center and zoom stand in for it
    # docs: limit_per_input goes in the body next to input (a bare array can't carry it)
    body = {'input': [{'country': 'US', 'lat': CENTER[0], 'long': CENTER[1], 'zoom_level': CENTER[2],
                       'keyword': KEYWORD}], 'limit_per_input': MAX}
    q = urllib.parse.urlencode({'dataset_id': BRIGHTDATA_DATASET, 'type': 'discover_new', 'discover_by': 'location',
                                'notify': 'false', 'include_errors': 'true'})
    rec.meta['input'] = body
    rec.meta['balance_before'] = rec.req('GET', f'{base}/customer/balance', H)[1]
    t0 = now(); rec.meta['submitted'] = iso(t0)
    st, sub = rec.req('POST', f'{base}/datasets/v3/trigger?{q}', H, body)
    if rec.dry:
        return rec.save(None)
    sid = sub.get('snapshot_id') if isinstance(sub, dict) else None
    if not sid:
        rec.meta['error'] = 'no snapshot created'; return rec.save(None)
    rec.meta['snapshot'] = sid
    rec.meta['progress_final'] = poll(lambda: rec.req('GET', f'{base}/datasets/v3/progress/{sid}', H)[1],
                                      lambda p: isinstance(p, dict) and p.get('status') in ('ready', 'failed'),
                                      every=10)
    _, rows = rec.req('GET', f'{base}/datasets/v3/snapshot/{sid}?format=json', H)
    rec.meta['seconds_total'] = round(now() - t0, 1)
    rows = rows if isinstance(rows, list) else []
    rec.meta['rows'] = len(rows)
    rec.meta['balance_after'] = rec.req('GET', f'{base}/customer/balance', H)[1]
    rec.save(rows)


TOOLS = {'lobstr_a': lambda r: lobstr(r, 'a'), 'lobstr_b': lambda r: lobstr(r, 'b'), 'apify': apify,
         'outscraper': outscraper, 'hasdata': hasdata, 'serpapi': serpapi, 'dataforseo': dataforseo,
         'scrapio': scrapio, 'scrapingdog': scrapingdog, 'places': places, 'brightdata': brightdata}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in TOOLS:
        sys.exit(__doc__)
    tool = sys.argv[1]
    TOOLS[tool](Recorder(tool, dry='--dry' in sys.argv))
