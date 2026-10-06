#!/usr/bin/env python3
"""Data comparison for the Google Maps scraper API benchmark.

Reads the saved results (raw/<tool>/results.json for the city run, raw/zip60605/<tool>/ for the
ZIP run), maps every tool's fields onto one common set, and computes:

  1. what you get   field offered (in the tool's schema) and fill rate, on the tool's own results
  2. is it clean    duplicates, outside the area, non-dental, closed, ads, placeholder contacts,
                    numbers sent as text
  3. is it right    for every business returned by >= MIN_TOOLS tools, the majority value of
                    phone, website, rating, review count, ZIP and street number; each tool's
                    agreement with that majority

What you get is counted by semantic.py: fields matched by meaning on a record every tool returned,
never by key name. Usage: python3 compare.py            writes analysis/compare_city.json and analysis/compare_zip60605.json
"""
import json, os, re, statistics, urllib.parse
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
AREAS = {'city': {'raw': 'raw', 'zip': None,
                  'tools': ['lobstr_a', 'lobstr_b', 'apify', 'outscraper', 'hasdata_final', 'serpapi',
                            'dataforseo', 'scrapio', 'scrapingdog', 'places', 'brightdata']},
         'zip60605': {'raw': 'raw/zip60605', 'zip': '60605',
                      'tools': ['lobstr_a', 'lobstr_b', 'apify', 'outscraper', 'hasdata', 'serpapi',
                                'dataforseo', 'scrapingdog', 'places', 'brightdata']}}
MIN_TOOLS = 5
SOCIALS = ['facebook', 'instagram', 'linkedin', 'x', 'youtube', 'tiktok', 'pinterest']
PLACEHOLDER_EMAIL = re.compile(r'(somedomain|example\.(com|org)|yourdomain|domain\.com|sentry|wixpress|'
                               r'^(email|name|test|john\.?doe|john\.?smith|your\.?name)@)', re.I)
PLACEHOLDER_PHONE = {'1234567890', '0000000000', '5555555555', '1111111111'}
DENTAL = re.compile(r'dent|orthodont|oral|periodont|endodont|prosthodont|teeth|denture', re.I)


# ---------------------------------------------------------------- helpers
def val(v):
    return v not in (None, '', [], {}, 'null', 'None')


def as_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return [x.strip() for x in v.split(',') if x.strip()]
    return v if isinstance(v, list) else [v]


def num(v):
    try:
        return float(str(v).replace(',', '').rstrip('+'))
    except Exception:
        return None


def zip_from(addr):
    m = re.findall(r'\b(?:IL|Illinois) (\d{5})', addr or '')
    return m[-1] if m else None


def digits(p):
    d = re.sub(r'\D', '', str(p or ''))
    return d[-10:] if len(d) >= 10 else None


def domain(url):
    if not val(url):
        return None
    u = urllib.parse.unquote(str(url)).strip()
    if '://' not in u:
        u = 'http://' + u
    host = urllib.parse.urlparse(u).netloc.lower().split(':')[0]
    return host[4:] if host.startswith('www.') else host or None


def street_no(addr):
    m = re.match(r'\s*(\d+)', addr or '')
    return m.group(1) if m else None


def extra_numbers(main, phones):
    """Phone numbers other than the main one, deduplicated on the last 10 digits (tools repeat the main
    number, often in several formats, inside their 'other phones' list)."""
    seen, out = {digits(main)}, []
    for p in phones or []:
        d = digits(p)
        if d and d not in seen:
            seen.add(d); out.append(p)
    return out


def truthy(v):
    if isinstance(v, str):
        return v.strip().lower() in ('true', '1', 'yes')
    return bool(v)


# ---------------------------------------------------------------- per-tool mapping onto common fields
# each returns a dict; a key that is present (even None) means the tool's schema has that field
def m_lobstr(rows):
    by = {}
    for r in rows:
        by.setdefault(r['place_id'], []).append(r)
    out = []
    for pid, rs in by.items():
        r = rs[0]
        emails = []
        status = {}
        for x in rs:
            if val(x.get('email')) and x['email'] not in emails:
                emails.append(x['email']); status[x['email']] = x.get('email_status')
        imgs = [s for s in (r.get('images') or '').split(', ') if s.startswith('http')]
        out.append({
            'id': pid, 'rows': len(rs), 'name': r.get('name'), 'address': r.get('address'), 'zip': r.get('zip_code'),
            'city': r.get('city'), 'lat': r.get('lat'), 'lng': r.get('lng'), 'phone': r.get('phone'),
            'website': r.get('website'), 'rating': r.get('score'), 'reviews': r.get('ratings'),
            'category': r.get('category'), 'categories': r.get('category'), 'hours': r.get('opening_hours'),
            'description': r.get('description') or r.get('about'), 'owner': r.get('owner_name'),
            'claimed': r.get('has_owner'), 'closed': r.get('is_permanently_closed'),
            'popular_times': r.get('popular_times'),
            'review_distribution': r.get('reviews_per_score_5') if val(r.get('reviews_per_score_5')) else None,
            'booking': r.get('booking_link'), 'price': r.get('price_range') or r.get('price'),
            'attributes': r.get('accessibility') or r.get('amenities') or r.get('highlights'),
            'emails': emails, 'email_status': status,
            'facebook': r.get('facebook'), 'instagram': r.get('instagram'), 'linkedin': r.get('linkedin'),
            'x': r.get('twitter'), 'youtube': r.get('youtube'), 'tiktok': r.get('tiktok'), 'pinterest': r.get('pinterest'),
            'extra_phones': extra_numbers(r.get('phone'), [p for p in (r.get('additional_phone') or '').split(', ') if p]),
            'photos_returned': len(imgs), 'photos_total': r.get('images_count'), 'review_texts': None,
            '_typed': [r.get('score'), r.get('ratings'), r.get('lat')]})
    return out


def m_apify(rows):
    return [{
        'id': r.get('placeId'), 'rows': 1, 'name': r.get('title'), 'address': r.get('address'),
        'zip': r.get('postalCode') or zip_from(r.get('address')), 'city': r.get('city'),
        'lat': (r.get('location') or {}).get('lat'), 'lng': (r.get('location') or {}).get('lng'),
        'phone': r.get('phoneUnformatted') or r.get('phone'), 'website': r.get('website'),
        'rating': r.get('totalScore'), 'reviews': r.get('reviewsCount'), 'category': r.get('categoryName'),
        'categories': r.get('categories'), 'hours': r.get('openingHours'),
        'description': r.get('description') or r.get('ownerDescription'),   # Apify returns it as ownerDescription
        'owner': None, 'claimed': (not r.get('claimThisBusiness')) if 'claimThisBusiness' in r else None,
        'closed': r.get('permanentlyClosed'), 'popular_times': r.get('popularTimesHistogram'),
        'review_distribution': r.get('reviewsDistribution'),
        'booking': r.get('bookingLinks') or r.get('reserveTableUrl'), 'price': r.get('price'),
        'attributes': r.get('additionalInfo'), 'emails': list(dict.fromkeys(r.get('emails') or [])), 'email_status': {},
        'facebook': r.get('facebooks'), 'instagram': r.get('instagrams'), 'linkedin': r.get('linkedIns'),
        'x': r.get('twitters'), 'youtube': r.get('youtubes'), 'tiktok': r.get('tiktoks'), 'pinterest': r.get('pinterests'),
        'extra_phones': extra_numbers(r.get('phoneUnformatted') or r.get('phone'), r.get('phones')),
        'photos_returned': len(r.get('imageUrls') or []),
        'photos_total': r.get('imagesCount'), 'review_texts': len(r.get('reviews') or []) or None,
        'is_ad': r.get('isAdvertisement'), '_typed': [r.get('totalScore'), r.get('reviewsCount')]} for r in rows]


def m_outscraper(rows):
    return [{
        'id': r.get('place_id'), 'rows': 1, 'name': r.get('name'), 'address': r.get('address'),
        'zip': str(r.get('postal_code') or '') or zip_from(r.get('address')), 'city': r.get('city'),
        'lat': r.get('latitude'), 'lng': r.get('longitude'), 'phone': r.get('phone'), 'website': r.get('website'),
        'rating': r.get('rating'), 'reviews': r.get('reviews'), 'category': r.get('category') or r.get('type'),
        'categories': r.get('subtypes'), 'hours': r.get('working_hours'), 'description': r.get('description'),
        'owner': r.get('owner_title'), 'claimed': r.get('verified'),
        'closed': (r.get('business_status') == 'CLOSED_PERMANENTLY') if 'business_status' in r else None,
        'popular_times': r.get('popular_times'), 'review_distribution': r.get('reviews_per_score'),
        'booking': r.get('booking_appointment_link') or r.get('reservation_links'), 'price': r.get('range'),
        'attributes': r.get('about'), 'emails': None, 'email_status': None,
        'photos_returned': 1 if val(r.get('photo')) else 0, 'photos_total': r.get('photos_count'),
        'review_texts': None, '_typed': [r.get('rating'), r.get('reviews'), r.get('latitude')]} for r in rows]


def m_hasdata(rows):
    return [{
        'id': r.get('placeId'), 'rows': 1, 'name': r.get('title'), 'address': r.get('address'),
        'zip': zip_from(r.get('address')), 'city': None,
        'lat': (r.get('gpsCoordinates') or {}).get('latitude'), 'lng': (r.get('gpsCoordinates') or {}).get('longitude'),
        'phone': r.get('phone'), 'website': r.get('website'), 'rating': r.get('rating'), 'reviews': r.get('reviews'),
        'category': r.get('type'), 'categories': r.get('types'), 'hours': r.get('workingHours'),
        'attributes': r.get('extensions'), 'emails': list(dict.fromkeys(r.get('emails') or [])), 'email_status': {},
        'photos_returned': 1 if val(r.get('thumbnail')) else 0, 'review_texts': None,
        '_typed': [r.get('rating'), r.get('reviews')]} for r in rows]


def m_serp(rows):   # SerpApi and ScrapingDog share the same Google Maps result shape
    return [{
        'id': r.get('place_id'), 'rows': 1, 'name': r.get('title'), 'address': r.get('address'),
        'zip': zip_from(r.get('address')), 'city': None,
        'lat': (r.get('gps_coordinates') or {}).get('latitude'), 'lng': (r.get('gps_coordinates') or {}).get('longitude'),
        'phone': r.get('phone'), 'website': r.get('website'), 'rating': r.get('rating'), 'reviews': r.get('reviews'),
        'category': r.get('type'), 'categories': r.get('types'), 'hours': r.get('operating_hours'),
        'description': r.get('description'), 'price': r.get('price'), 'attributes': r.get('extensions'),
        'booking': r.get('book_online'),   # SerpApi only
        # both flag only unclaimed listings (unclaimed_listing / unclaimed_business); the flag matched
        # lobstr.io's has_owner on every shared place in the ZIP run, so its absence means claimed
        'claimed': not (r.get('unclaimed_listing') or r.get('unclaimed_business')),
        'photos_returned': 1 if val(r.get('thumbnail') or r.get('image')) else 0, 'review_texts': None,
        '_typed': [r.get('rating'), r.get('reviews')]} for r in rows]


def m_dataforseo(rows):
    out = []
    for r in rows:
        ri = r.get('rating') or {}
        out.append({
            'id': r.get('place_id'), 'rows': 1, 'name': r.get('title'), 'address': r.get('address'),
            'zip': (r.get('address_info') or {}).get('zip') or zip_from(r.get('address')),
            'city': (r.get('address_info') or {}).get('city'), 'lat': r.get('latitude'), 'lng': r.get('longitude'),
            'phone': r.get('phone'), 'website': r.get('url') or r.get('domain'), 'rating': ri.get('value'),
            'reviews': ri.get('votes_count'), 'category': r.get('category'),
            'categories': ([r.get('category')] if r.get('category') else []) + (r.get('additional_categories') or []),
            'hours': r.get('work_hours'), 'claimed': r.get('is_claimed'),
            'review_distribution': r.get('rating_distribution'), 'booking': r.get('book_online_url'),
            'price': r.get('price_level'), 'photos_returned': 1 if val(r.get('main_image')) else 0,
            'photos_total': r.get('total_photos'), 'review_texts': None, 'is_ad': r.get('type') == 'maps_paid_item',
            '_typed': [ri.get('value'), ri.get('votes_count'), r.get('latitude')]})
    return out


def m_scrapio(rows):
    out = []
    for r in rows:
        w = r.get('website_data') or {}
        emails = [e.get('email') if isinstance(e, dict) else e for e in as_list(w.get('emails'))]
        out.append({
            'id': r.get('place_id'), 'rows': 1, 'name': r.get('name'), 'address': r.get('location_full_address'),
            'zip': r.get('location_postal_code'), 'city': r.get('location_city'),
            'lat': r.get('location_latitude'), 'lng': r.get('location_longitude'), 'phone': r.get('phone'),
            'website': r.get('website'), 'rating': r.get('reviews_rating'), 'reviews': r.get('reviews_count'),
            'category': next((t.get('type') for t in r.get('types') or [] if t.get('is_main')), None),
            'categories': [t.get('type') for t in r.get('types') or []], 'hours': r.get('working_hours'),
            'description': r.get('descriptions'), 'owner': r.get('owner_name'), 'claimed': r.get('is_claimed'),
            'closed': r.get('is_closed'),
            'popular_times': r.get('occupancy') if any(val(v) for v in (r.get('occupancy') or {}).values()) else None,
            'review_distribution': r.get('reviews_per_score'), 'booking': r.get('booking_links'),
            'price': r.get('price_range'), 'attributes': r.get('characteristics'),
            'emails': [e for e in dict.fromkeys(emails) if e], 'email_status': {},
            'facebook': as_list(w.get('facebook')), 'instagram': as_list(w.get('instagram')),
            'linkedin': as_list(w.get('linkedin')), 'x': as_list(w.get('twitter')), 'youtube': as_list(w.get('youtube')),
            'tiktok': as_list(w.get('tiktok')), 'pinterest': None,
            'extra_phones': extra_numbers(r.get('phone'), [p.get('phone') if isinstance(p, dict) else p for p in as_list(w.get('phones'))]),
            'photos_returned': len(r.get('photos') or []), 'photos_total': r.get('photos_count'),
            'review_texts': len(r.get('reviews_highlighted') or []) or None,
            '_typed': [r.get('reviews_rating'), r.get('reviews_count'), r.get('location_latitude')]})
    return out


def m_places(rows):
    out = []
    for r in rows:
        z = next((c.get('shortText') for c in r.get('addressComponents') or [] if 'postal_code' in c.get('types', [])), None)
        city = next((c.get('longText') for c in r.get('addressComponents') or [] if 'locality' in c.get('types', [])), None)
        attrs = {k: r.get(k) for k in ('paymentOptions', 'accessibilityOptions', 'parkingOptions') if r.get(k)}
        out.append({
            'id': r.get('id'), 'rows': 1, 'name': (r.get('displayName') or {}).get('text'),
            'address': r.get('formattedAddress'), 'zip': z, 'city': city,
            'lat': (r.get('location') or {}).get('latitude'), 'lng': (r.get('location') or {}).get('longitude'),
            'phone': r.get('nationalPhoneNumber'), 'website': r.get('websiteUri'), 'rating': r.get('rating'),
            'reviews': r.get('userRatingCount'), 'category': (r.get('primaryTypeDisplayName') or {}).get('text'),
            'categories': r.get('types'), 'hours': r.get('regularOpeningHours'),
            'description': (r.get('editorialSummary') or {}).get('text'),
            'closed': (r.get('businessStatus') == 'CLOSED_PERMANENTLY'), 'price': r.get('priceRange'),
            'attributes': attrs or None, 'photos_returned': len(r.get('photos') or []), 'review_texts': None,
            '_typed': [r.get('rating'), r.get('userRatingCount')]})
    return out


def m_brightdata(rows):
    return [{
        'id': r.get('place_id'), 'rows': 1, 'name': r.get('name'), 'address': r.get('address'),
        'zip': zip_from(r.get('address')), 'city': None, 'lat': r.get('lat'), 'lng': r.get('lon'),
        'phone': r.get('phone_number'), 'website': r.get('open_website'), 'rating': r.get('rating'),
        'reviews': r.get('reviews_count'), 'category': r.get('category'), 'categories': r.get('all_categories'),
        'hours': r.get('open_hours'), 'claimed': r.get('is_claimed'), 'closed': r.get('permanently_closed'),
        'popular_times': r.get('popular_times'), 'review_distribution': r.get('review_distribution'),
        'booking': r.get('reservation_link'), 'attributes': r.get('services_provided'),
        'photos_returned': len(r.get('photos_and_videos') or []) or (1 if val(r.get('main_image')) else 0),
        'review_texts': len(r.get('top_reviews') or []) or None,
        '_typed': [r.get('rating'), r.get('reviews_count'), r.get('lat')]} for r in rows]


MAP = {'lobstr_a': m_lobstr, 'lobstr_b': m_lobstr, 'apify': m_apify, 'outscraper': m_outscraper,
       'hasdata': m_hasdata, 'hasdata_final': m_hasdata, 'serpapi': m_serp, 'scrapingdog': m_serp,
       'dataforseo': m_dataforseo, 'scrapio': m_scrapio, 'places': m_places, 'brightdata': m_brightdata}

# FIELDS: the key-name map's common fields. It still feeds cleanliness and accuracy (is_it_clean, is_it_right).
# What each tool RETURNS is counted by semantic.py's meaning-based map, never by this one.
FIELDS = {  # group -> common fields, in report order
    'basic': ['name', 'address', 'phone', 'website', 'rating', 'reviews', 'category', 'hours', 'lat'],
    'profile': ['categories', 'description', 'owner', 'claimed', 'closed', 'popular_times', 'review_distribution',
                'booking', 'price', 'attributes'],
    'lead': ['emails', 'verified_email'] + SOCIALS + ['extra_phones'],
    'media': ['photos_returned', 'photos_total', 'review_texts'],
}


def load(area, tool):
    rows = json.load(open(os.path.join(HERE, AREAS[area]['raw'], tool, 'results.json')))
    recs = MAP[tool](rows)
    for r in recs:   # Google's "owner" is the profile's display name: when it repeats the business name
        if val(r.get('owner')) and str(r['owner']).strip().lower() == str(r.get('name') or '').strip().lower():
            r['owner'] = None   # it adds nothing (100% of lobstr.io, Outscraper and Scrap.io rows)
    return rows, recs


def filled(rec, f):
    if f == 'verified_email':
        return any(s in ('valid',) for s in (rec.get('email_status') or {}).values())
    v = rec.get(f)
    if f in ('photos_returned', 'review_texts'):
        return bool(v)
    if f in ('claimed', 'closed'):
        return v is not None and v != ''
    return val(v)


def offered(recs, f):
    if f == 'verified_email':
        return any(r.get('email_status') for r in recs) or any('email_status' in r and r['email_status'] is not None
                                                               and r.get('emails') is not None for r in recs[:0])
    return any(f in r and r[f] is not None for r in recs) or any(filled(r, f) for r in recs)


# ---------------------------------------------------------------- the three passes
def what_you_get(area, tool, recs):
    """Fill per data point on the tool's own results, from semantic.py's meaning-based map
    (the old key-name FIELDS map missed data and counted duplicates: see semantic.py)."""
    import semantic as S
    sem = [r for r in S.load(area, tool).values()]
    n = len(sem)
    out = {}
    for p in S.POINTS:
        k = sum(1 for r in sem if r[p])
        out[p] = {'filled': k, 'of': n, 'pct': round(100 * k / n) if n else 0}
    photos = [r.get('photos_returned') or 0 for r in recs]
    out['_photos_per_place'] = {'median': statistics.median(photos) if photos else 0, 'max': max(photos or [0]),
                                'total': sum(photos)}
    em = [len(r.get('emails') or []) for r in recs]
    out['_emails'] = {'businesses_with_email': sum(1 for e in em if e), 'unique_emails':
                      len({e for r in recs for e in (r.get('emails') or [])}), 'of': n}
    st = Counter(s for r in recs for s in (r.get('email_status') or {}).values())
    out['_email_status'] = dict(st)
    return out


def is_it_clean(rows, recs, area_zip, tool):
    n = len(recs)
    ids = [r['id'] for r in recs if r.get('id')]
    emails = [e for r in recs for e in (r.get('emails') or [])]
    owners = defaultdict(set)
    for r in recs:
        for e in r.get('emails') or []:
            owners[e].add(r['id'])
    phones_fake = sum(1 for r in recs for p in (r.get('extra_phones') or []) + [r.get('phone')]
                      if digits(p) in PLACEHOLDER_PHONE)
    typed = [v for r in recs for v in r.get('_typed', []) if v is not None]
    cities = [r.get('city') or ('Chicago' if 'Chicago' in (r.get('address') or '') else None) for r in recs]
    return {
        'records': n, 'raw_rows': len(rows), 'duplicate_ids': len(ids) - len(set(ids)),
        'missing_id': n - len(ids),
        'ads': sum(1 for r in recs if r.get('is_ad')),
        'in_chicago': sum(1 for c in cities if c == 'Chicago'),
        'dental': sum(1 for r in recs if DENTAL.search(str(r.get('category') or '') + ' ' + json.dumps(r.get('categories')))),
        'in_area_zip': sum(1 for r in recs if area_zip and r.get('zip') == area_zip) if area_zip else None,
        'permanently_closed': sum(1 for r in recs if truthy(r.get('closed'))),
        'placeholder_emails': sorted({e for e in emails if PLACEHOLDER_EMAIL.search(e)}),
        'emails_on_several_businesses': sum(1 for e, s in owners.items() if len(s) > 1),
        'placeholder_phones': phones_fake,
        'numbers_as_text_pct': round(100 * sum(1 for v in typed if isinstance(v, str)) / len(typed)) if typed else None,
    }


def norm_field(f, v):
    if not val(v):
        return None
    if f == 'phone':
        return digits(v)
    if f == 'website':
        return domain(v)
    if f == 'rating':
        x = num(v); return round(x, 1) if x is not None else None
    if f == 'reviews':
        x = num(v); return int(x) if x is not None else None
    if f == 'zip':
        return str(v)
    if f == 'street_no':
        return street_no(v)
    return v


def is_it_right(by_tool):
    """Majority value per business and field, across tools; each tool's agreement with it."""
    fields = ['phone', 'website', 'rating', 'reviews', 'zip', 'street_no']
    index = defaultdict(dict)   # id -> tool -> rec
    for t, recs in by_tool.items():
        for r in recs:
            if r.get('id'):
                index[r['id']][t] = r
    shared = {i: m for i, m in index.items() if len(m) >= MIN_TOOLS}
    score = {t: {f: {'agree': 0, 'disagree': 0, 'missing': 0} for f in fields} for t in by_tool}
    examples = defaultdict(list)
    for i, m in shared.items():
        for f in fields:
            vals = {t: norm_field(f, r.get('address') if f == 'street_no' else r.get(f)) for t, r in m.items()}
            have = {t: v for t, v in vals.items() if v is not None}
            if len(have) < 3:
                continue
            c = Counter(have.values())
            top, k = c.most_common(1)[0]
            if f == 'reviews':   # counts move by a review or two within the hour: allow +-2 or 1%
                close = lambda a, b: abs(a - b) <= max(2, 0.01 * b)
                k = sum(1 for v in have.values() if close(v, top))
            if k < len(have) / 2:
                continue        # no majority: not scored
            for t, v in vals.items():
                if v is None:
                    score[t][f]['missing'] += 1
                    continue
                ok = (abs(v - top) <= max(2, 0.01 * top)) if f == 'reviews' else v == top
                score[t][f]['agree' if ok else 'disagree'] += 1
                if not ok and len(examples[(t, f)]) < 5:
                    examples[(t, f)].append({'id': i, 'name': next(iter(m.values())).get('name'), 'tool': v, 'majority': top})
    summary = {}
    for t, fs in score.items():
        a = sum(x['agree'] for x in fs.values()); d = sum(x['disagree'] for x in fs.values())
        summary[t] = {'agree_pct': round(100 * a / (a + d), 1) if a + d else None, 'compared': a + d, 'by_field': fs}
    return {'min_tools': MIN_TOOLS, 'shared_businesses': len(shared), 'tools': summary,
            'disagreements': {f'{t}:{f}': v for (t, f), v in examples.items()}}


def main():
    os.makedirs(os.path.join(HERE, 'analysis'), exist_ok=True)
    for area, cfg in AREAS.items():
        by_tool, report = {}, {'area': area, 'tools': {}}
        for t in cfg['tools']:
            rows, recs = load(area, t)
            recs = [r for r in recs if not r.get('is_ad')] if t == 'dataforseo' else recs
            by_tool[t] = recs
            report['tools'][t] = {'what_you_get': what_you_get(area, t, recs), 'is_it_clean': is_it_clean(rows, recs, cfg['zip'], t)}
        report['is_it_right'] = is_it_right(by_tool)
        with open(os.path.join(HERE, 'analysis', f'compare_{area}.json'), 'w') as f:
            json.dump(report, f, indent=1, default=str)
        print(f'wrote analysis/compare_{area}.json')


if __name__ == '__main__':
    main()
