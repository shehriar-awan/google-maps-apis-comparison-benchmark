"""The data points every tool returns, mapped by MEANING, not by key name (2026-10-05).

How the map was built: the full raw record of one business every tool returned (Windy City Family Dental,
place ChIJN9ly9YgtDogRrK0Dj2T0H3M) was read key by key, nested keys and JSON inside strings included, and
each key was matched to a data point by its value. Examples the old name-matching missed or got wrong:
Apify's description is `ownerDescription`; Outscraper's `county` holds the neighborhood; SerpApi and
ScrapingDog carry claimed status as an `unclaimed_*` flag present only when true; "owner name" equals the
business name everywhere (not a data point); "other phones" lists repeat the main phone; lobstr.io fills
`last_opening_hours_updated_at` with the scrape date when Google shows no confirmation (filler).

Not data: IDs, links back to Google, query and run metadata. Photos count as present or absent only (our
own settings capped Apify at 10). Verification is its own point, never folded into "email".
Used by compare.py (fill per data point) and score.py (Data score). Rerun: python3 run_semantic.py"""
import sys, json, statistics, re
from collections import Counter, defaultdict
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare as C
V = C.val
def J(v):
    if isinstance(v, str) and v[:1] in '{[':
        try: return json.loads(v)
        except Exception: return v
    return v
def has(v):  # a value that carries data (False counts: it's a status)
    v = J(v)
    if v is False or v == 0: return True
    if isinstance(v, str) and v.strip().lower() in ('', 'none', 'null'): return False
    return V(v)
def anyv(*vs): return any(has(v) for v in vs)
def comp(p, t):
    return next((c.get('longText') for c in p.get('addressComponents') or [] if t in c.get('types', [])), None)
def extra(main, lst): return bool(C.extra_numbers(main, lst))
SOC = lambda *vs: any(has(v) for v in vs)

POINTS = ['full address', 'street', 'city', 'ZIP', 'state', 'neighborhood', 'county', 'coordinates', 'plus code', 'time zone',
          'phone', 'website', 'email', 'verified email', 'extra phone', 'social profile', 'contact page',
          'rating', 'review count', 'review distribution', 'review keywords', 'full review texts', 'review snippet',
          'main category', 'all categories', 'weekly hours', 'open now', 'hours confirmed by owner',
          'description', 'claimed', 'permanently closed', 'temporarily closed', 'booking link', 'order link',
          'attributes', 'services menu', 'owner posts', 'people also search', 'web results', 'Q&A', 'popular times',
          'photo count', 'photos', 'photo categories', 'street view', 'logo']

def lobstr(rs):
    r = rs[0]; em = [x.get('email') for x in rs if V(x.get('email'))]
    return {'full address': r.get('address'), 'street': r.get('street_address'), 'city': r.get('city'), 'ZIP': r.get('zip_code'),
     'state': r.get('region'), 'neighborhood': r.get('neighborhood'), 'county': r.get('county'), 'coordinates': r.get('lat'),
     'plus code': r.get('plus_code'), 'time zone': r.get('timezone'), 'phone': r.get('phone'), 'website': r.get('website'),
     'email': em, 'verified email': [x.get('email') for x in rs if x.get('email_status') == 'valid'] or None,
     'extra phone': extra(r.get('phone'), (r.get('additional_phone') or '').split(', ')) or None,
     'social profile': SOC(*[r.get(k) for k in ('facebook','instagram','linkedin','twitter','youtube','tiktok','pinterest','whatsapp')]) or None,
     'rating': r.get('score'), 'review count': r.get('ratings'), 'review distribution': r.get('reviews_per_score_5'),
     'review keywords': r.get('reviews_tags'), 'main category': r.get('category'),
     'all categories': r.get('category') if ',' in (r.get('category') or '') else None,
     'weekly hours': r.get('opening_hours'), # lobstr.io fills this with the scrape date when Google shows no confirmation: only the text counts
     'hours confirmed by owner': r.get('last_opening_hours_updated_at') if 'business' in str(r.get('last_opening_hours_updated_at')) else None,
     'description': r.get('description') or r.get('about'), 'claimed': r.get('has_owner'),
     'permanently closed': r.get('is_permanently_closed'), 'temporarily closed': r.get('is_temporarily_closed'),
     'booking link': r.get('booking_link') or (r.get('actions') if 'Book' in str(r.get('actions')) else None),
     'order link': r.get('order_providers'),
     'attributes': anyv(r.get('accessibility'), r.get('payment_methods'), r.get('service_options'), r.get('amenities'), r.get('highlights')) or None,
     'services menu': r.get('menu_items') or r.get('menu'), 'owner posts': r.get('owner_posts'),
     'people also search': r.get('people_also_search'), 'popular times': r.get('popular_times') or r.get('popular_times_live'),
     'photo count': r.get('images_count'), 'photos': r.get('images') or r.get('main_image_url'),
     'photo categories': r.get('image_categories'), 'street view': r.get('streetview_url'), 'scrape timestamp': r.get('scraping_time')}

def apify(r):
    return {'full address': r.get('address'), 'street': r.get('street'), 'city': r.get('city'), 'ZIP': r.get('postalCode'),
     'state': r.get('state'), 'neighborhood': r.get('neighborhood'), 'coordinates': r.get('location'), 'plus code': r.get('plusCode'),
     'phone': r.get('phone'), 'website': r.get('website'), 'email': r.get('emails'),
     'extra phone': extra(r.get('phoneUnformatted') or r.get('phone'), r.get('phones')) or None,
     'social profile': SOC(*[r.get(k) for k in ('facebooks','instagrams','linkedIns','twitters','youtubes','tiktoks','pinterests','discords')]) or None,
     'rating': r.get('totalScore'), 'review count': r.get('reviewsCount'), 'review distribution': r.get('reviewsDistribution'),
     'review keywords': r.get('reviewsTags'), 'full review texts': r.get('reviews'), 'main category': r.get('categoryName'),
     'all categories': r.get('categories') if len(r.get('categories') or []) > 1 else None,
     'weekly hours': r.get('openingHours'), 'open now': r.get('wasOpenAtScrapeTime'),
     'hours confirmed by owner': r.get('openingHoursBusinessConfirmationText'),
     'description': r.get('description') or r.get('ownerDescription'),
     'claimed': (not r['claimThisBusiness']) if 'claimThisBusiness' in r else None,
     'permanently closed': r.get('permanentlyClosed'), 'temporarily closed': r.get('temporarilyClosed'),
     'booking link': r.get('bookingLinks') or r.get('reserveTableUrl') or r.get('tableReservationLinks'),
     'attributes': r.get('additionalInfo'), 'services menu': r.get('menu'), 'owner posts': r.get('ownerUpdates'),
     'people also search': r.get('peopleAlsoSearch'), 'web results': r.get('webResults'), 'Q&A': r.get('questionsAndAnswers'),
     'popular times': r.get('popularTimesHistogram'), 'photo count': r.get('imagesCount'), 'photos': r.get('imageUrls') or r.get('imageUrl'),
     'photo categories': r.get('imageCategories'), 'scrape timestamp': r.get('scrapedAt')}

def outscraper(r):
    return {'full address': r.get('address'), 'street': r.get('street'), 'city': r.get('city'), 'ZIP': r.get('postal_code'),
     'state': r.get('state'), 'neighborhood': r.get('county'),  # Outscraper's "county" holds the neighborhood
     'coordinates': r.get('latitude'), 'plus code': r.get('plus_code'), 'time zone': r.get('time_zone'),
     'phone': r.get('phone'), 'website': r.get('website'),
     'rating': r.get('rating'), 'review count': r.get('reviews'), 'review distribution': r.get('reviews_per_score'),
     'review keywords': r.get('reviews_tags'), 'main category': r.get('category') or r.get('type'),
     'all categories': r.get('subtypes') if ',' in str(r.get('subtypes')) else None, 'weekly hours': r.get('working_hours'),
     'description': r.get('description'), 'claimed': r.get('verified'),
     'permanently closed': r.get('business_status'), 'temporarily closed': r.get('business_status'),
     'booking link': r.get('booking_appointment_link') or r.get('reservation_links'), 'order link': r.get('order_links'),
     'attributes': r.get('about'), 'owner posts': r.get('posts'), 'popular times': r.get('popular_times'),
     'photo count': r.get('photos_count'), 'photos': r.get('photo'), 'street view': r.get('street_view'), 'logo': r.get('logo')}

def hasdata(r):
    return {'full address': r.get('address'), 'coordinates': r.get('gpsCoordinates'),
     'time zone': (r.get('workingHours') or {}).get('timezone'), 'phone': r.get('phone'), 'website': r.get('website'),
     'email': r.get('emails'), 'rating': r.get('rating'), 'review count': r.get('reviews'), 'main category': r.get('type'),
     'all categories': r.get('types') if len(r.get('types') or []) > 1 else None,
     'weekly hours': (r.get('workingHours') or {}).get('days'), 'open now': r.get('openState'),
     'attributes': r.get('extensions'), 'services menu': r.get('menu'), 'photos': r.get('thumbnail')}

def serp(r):
    return {'full address': r.get('address'), 'coordinates': r.get('gps_coordinates'), 'phone': r.get('phone'), 'website': r.get('website'),
     'rating': r.get('rating'), 'review count': r.get('reviews'), 'review snippet': r.get('user_review'),
     'main category': r.get('type'), 'all categories': r.get('types') if len(r.get('types') or []) > 1 else None,
     'weekly hours': r.get('operating_hours'), 'open now': r.get('open_state'),
     'description': r.get('description'),
     'claimed': not (r.get('unclaimed_listing') or r.get('unclaimed_business')),
     'booking link': r.get('book_online'), 'attributes': r.get('extensions'), 'services menu': r.get('menu'),
     'photos': r.get('thumbnail') or r.get('image')}

def dataforseo(r):
    a = r.get('address_info') or {}; ri = r.get('rating') or {}
    return {'full address': r.get('address'), 'street': a.get('address'), 'city': a.get('city'), 'ZIP': a.get('zip'),
     'state': a.get('region'), 'neighborhood': a.get('borough'), 'coordinates': r.get('latitude'),
     'phone': r.get('phone'), 'website': r.get('url') or r.get('domain'), 'contact page': r.get('contact_url'),
     'rating': ri.get('value'), 'review count': ri.get('votes_count'), 'review distribution': r.get('rating_distribution'),
     'review snippet': r.get('local_justifications'), 'main category': r.get('category'),
     'all categories': r.get('additional_categories'), 'weekly hours': (r.get('work_hours') or {}).get('timetable'),
     'open now': (r.get('work_hours') or {}).get('current_status'), 'claimed': r.get('is_claimed'),
     'booking link': r.get('book_online_url'), 'photo count': r.get('total_photos'), 'photos': r.get('main_image')}

def places(r):
    return {'full address': r.get('formattedAddress'),
     'street': comp(r, 'route'), 'city': comp(r, 'locality'), 'ZIP': comp(r, 'postal_code'), 'state': comp(r, 'administrative_area_level_1'),
     'neighborhood': comp(r, 'neighborhood'), 'county': comp(r, 'administrative_area_level_2'), 'coordinates': r.get('location'),
     'plus code': r.get('plusCode'), 'time zone': r.get('timeZone'), 'phone': r.get('nationalPhoneNumber'), 'website': r.get('websiteUri'),
     'rating': r.get('rating'), 'review count': r.get('userRatingCount'), 'main category': r.get('primaryTypeDisplayName'),
     'all categories': r.get('types'), 'weekly hours': r.get('regularOpeningHours'),
     'open now': (r.get('currentOpeningHours') or {}).get('openNow'),
     'description': (r.get('editorialSummary') or {}).get('text') or (r.get('generativeSummary') or {}).get('overview'),
     'permanently closed': r.get('businessStatus'), 'temporarily closed': r.get('businessStatus'),
     'attributes': anyv(r.get('paymentOptions'), r.get('accessibilityOptions'), r.get('parkingOptions')) or None,
     'photos': r.get('photos')}

def brightdata(r):
    return {'full address': r.get('address'), 'coordinates': r.get('lat'), 'phone': r.get('phone_number'), 'website': r.get('open_website'),
     'rating': r.get('rating'), 'review count': r.get('reviews_count'), 'review distribution': r.get('review_distribution'),
     'full review texts': r.get('top_reviews'), 'review snippet': r.get('reviews_snippets'), 'main category': r.get('category'),
     'all categories': r.get('all_categories') if len(r.get('all_categories') or []) > 1 else None, 'weekly hours': r.get('open_hours'),
     'claimed': r.get('is_claimed'), 'permanently closed': r.get('permanently_closed'), 'temporarily closed': r.get('temporarily_closed'),
     'booking link': r.get('reservation_link'), 'attributes': r.get('services_provided'),
     'people also search': r.get('people_also_search'), 'web results': r.get('web_results'), 'Q&A': r.get('questions_answers'),
     'popular times': r.get('popular_times'), 'photos': r.get('photos_and_videos') or r.get('main_image'), 'scrape timestamp': r.get('timestamp')}

def scrapio(r):
    w = r.get('website_data') or {}
    em = [e.get('email') if isinstance(e, dict) else e for e in C.as_list(w.get('emails'))]
    ph = [p.get('phone') if isinstance(p, dict) else p for p in C.as_list(w.get('phones'))]
    return {'full address': r.get('location_full_address'), 'street': r.get('location_street_1'), 'city': r.get('location_city'),
     'ZIP': r.get('location_postal_code'), 'state': r.get('location_state'), 'neighborhood': r.get('location_borough'),
     'county': r.get('location_admin2_code'), 'coordinates': r.get('location_latitude'), 'time zone': r.get('timezone'),
     'phone': r.get('phone'), 'website': r.get('website'), 'email': [e for e in em if e], 'extra phone': extra(r.get('phone'), ph) or None,
     'social profile': SOC(*[w.get(k) for k in ('facebook','instagram','linkedin','twitter','youtube','tiktok')]) or None,
     'contact page': w.get('contact_pages'),
     'rating': r.get('reviews_rating'), 'review count': r.get('reviews_count'), 'review distribution': r.get('reviews_per_score'),
     'review keywords': r.get('reviews_tags'), 'full review texts': r.get('reviews_highlighted'),
     'main category': next((t.get('type') for t in r.get('types') or [] if t.get('is_main')), None),
     'all categories': r.get('types') if len(r.get('types') or []) > 1 else None, 'weekly hours': r.get('working_hours'),
     'description': r.get('descriptions'), 'claimed': r.get('is_claimed'), 'permanently closed': r.get('is_closed'),
     'temporarily closed': r.get('is_temporarily_closed'), 'booking link': r.get('booking_links'), 'order link': r.get('order_links'),
     'attributes': r.get('characteristics'),
     'popular times': r.get('occupancy') if any(V(v) for v in (r.get('occupancy') or {}).values()) else None,
     'photo count': r.get('photos_count'), 'photos': r.get('photos'), 'street view': r.get('photos_360'),
     'scrape timestamp': r.get('scraped_at')}

MAPS = {'hasdata_final': hasdata, 'lobstr_a': lobstr, 'lobstr_b': lobstr, 'apify': apify, 'outscraper': outscraper, 'hasdata': hasdata, 'serpapi': serp,
        'scrapingdog': serp, 'dataforseo': dataforseo, 'places': places, 'brightdata': brightdata, 'scrapio': scrapio}
IDK = {'hasdata_final': 'placeId', 'lobstr_a': 'place_id', 'lobstr_b': 'place_id', 'apify': 'placeId', 'outscraper': 'place_id', 'hasdata': 'placeId',
       'serpapi': 'place_id', 'scrapingdog': 'place_id', 'dataforseo': 'place_id', 'places': 'id', 'brightdata': 'place_id', 'scrapio': 'place_id'}

def load(area, t):
    rows = C.load(area, t)[0]
    by = defaultdict(list)
    for r in rows:
        if t == 'dataforseo' and r.get('type') == 'maps_paid_item': continue
        by[r.get(IDK[t])].append(r)
    out = {}
    for pid, rs in by.items():
        m = MAPS[t](rs) if t.startswith('lobstr') else MAPS[t](rs[0])
        out[pid] = {p: has(m.get(p)) for p in POINTS}
        out[pid]['_raw'] = m
    return out
