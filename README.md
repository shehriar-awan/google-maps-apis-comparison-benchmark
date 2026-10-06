# Google Maps scraper API benchmark

The scripts and raw data behind [Google Maps Scraper API: 8 Benchmarked on Data, Cost & Speed](https://www.lobstr.io/blog/google-maps-scraper-api) on the lobstr.io blog.

Eight third-party Google Maps scraper APIs and Google's own Places API ran the same two searches. Every request and response is in this repo, with the timings, the usage counters before and after each run, and the code behind the scores.

**Disclosure:** lobstr.io is one of the tested tools, and lobstr.io ran this benchmark. This repo exists so you can check every number yourself.

## What was tested

- **8 ranked APIs:** lobstr.io (Google Maps Leads Scraper), Apify (`compass/crawler-google-places`), HasData, Outscraper, DataForSEO, Bright Data, SerpApi and ScrapingDog.
- **Google Places API (New)** as a baseline, scored but not ranked.
- **Scrap.io**, tested but not ranked: it serves results from its own database instead of scraping Google Maps live. It's scored on the city run only, because its trial stopped at 100 exports before the ZIP run.
- lobstr.io ran twice per search, with two input types: **category + city** (`lobstr_a` in the scripts) and **a Google Maps search URL** (`lobstr_b`). The article reports the category + city run.

## The test

- **Two searches of about 100 dentists each:**
  - **City run:** `dentists in Chicago, IL`, on 2026-09-30. Every tool started within 6 minutes of the others, except Bright Data, which ran 16 hours later (2026-10-01).
  - **ZIP run:** `dentists in Chicago, IL 60605`, on 2026-10-01. Every tool started within 9 seconds of the others. The ZIP run was added because the city outputs didn't share a single dentist; in ZIP 60605, 12 dentists showed up in every output.
- **Up to 100 places per tool.** Google Places stops at 60. HasData was capped at 60 in the ZIP run, because only that many free credits were left.
- **One run per tool, everything on:** every option the same scraper offers for this job was switched on.
- **No reviews** for any tool (they have their own benchmark), and **no separate products:** a scraper's own add-ons count, services a vendor sells as a product of their own don't.
- **Filters:** each tool's defaults.

What each tool was sent (the city run; the ZIP run swaps in the ZIP, or its center for the tools that take coordinates). `run.py` has the exact requests.

| Tool | Input | Switched on |
|---|---|---|
| lobstr.io, category + city input | `category: dentist`, `country: United States`, `city: Chicago` (ZIP run: `Chicago 60605`), `max_results: 100` | `extract_emails_from_website`, `auto_verify_emails`, `collect_business_details`, `fetch_business_images` |
| lobstr.io, Maps URL input | `url: https://www.google.com/maps/search/dentists+in+Chicago,+IL/@41.8781,-87.6298,12z` | same as above |
| Apify (`compass/crawler-google-places`) | `searchStringsArray: ["dentists"]`, `locationQuery: "Chicago, IL, USA"`, `maxCrawledPlacesPerSearch: 100`, `language: en` | `scrapeContacts`, `scrapePlaceDetailPage`, `maxImages: 10`, `includeWebResults`; `maxReviews: 0`, social profile enrichment and leads enrichment off (separate products) |
| HasData | `categories: ["dentist"]`, `locations: ["Chicago, IL"]`, `limit: 100` | `extractEmails` |
| Outscraper (`google-maps-search`) | `query: ["dentists in Chicago, IL"]`, `organizationsPerQueryLimit: 100`, `language: en`, `region: US`, `async: true` | listings only: its emails and email verification are separate products |
| DataForSEO (Google Maps SERP, Live mode) | `keyword: "dentists in Chicago, IL"`, `location_name: "Chicago,Illinois,United States"`, `language_code: en`, `depth: 100` | nothing to switch on |
| Bright Data (dataset `gd_m8ebnr0q2qlklc02fz`, "Google Maps full information") | discover by location: `country: US`, `lat: 41.8781`, `long: -87.6298`, `zoom_level: 12`, `keyword: dentists`, `limit_per_input: 100` (there's no city or ZIP field) | nothing to switch on |
| SerpApi (`engine: google_maps`) | `q: "dentists in Chicago, IL"`, `type: search`, `hl: en`, `gl: us`, `start` 0 to 80 | nothing to switch on |
| ScrapingDog (`google_maps`) | `query: "dentists"`, `ll: @41.8781,-87.6298,12z`, `page` 0 to 80 | nothing to switch on |
| Scrap.io (`gmap/search`) | `country_code: US`, `admin1_code: IL`, `city: Chicago`, `type: dentist`, `per_page: 50`, two pages | nothing to switch on (records already carry emails and socials) |
| Google Places API (New) | see below | |

ZIP run centers: `41.8703, -87.6236`, zoom 14 (from the Places API's `postal_code` place for 60605).

## Google Places method

Google's Maps Platform Terms (3.2.4) ask a published benchmark to include everything needed to replicate it. Here it is:

- **Endpoint:** `POST https://places.googleapis.com/v1/places:searchText`
- **Body:** `{"textQuery": "dentists in Chicago, IL", "pageSize": 20}` (ZIP run: `dentists in Chicago, IL 60605`). Then the same body with the returned `pageToken`, for up to 3 pages: Google returns at most 60 results per search.
- **Field mask** (`X-Goog-FieldMask`): `places.<field>` for each of these 61 fields, plus `nextPageToken`. That's every Pro, Enterprise and Atmosphere field except `reviews`, so it bills as Text Search Enterprise + Atmosphere (a `*` mask bills the same SKU).

  ```
  id, displayName, formattedAddress, shortFormattedAddress, addressComponents, adrFormatAddress, location, viewport, plusCode, types, primaryType, primaryTypeDisplayName, googleMapsUri, googleMapsLinks, businessStatus, utcOffsetMinutes, photos, pureServiceAreaBusiness, postalAddress, timeZone, containingPlaces, attributions, nationalPhoneNumber, internationalPhoneNumber, websiteUri, rating, userRatingCount, priceLevel, priceRange, regularOpeningHours, currentOpeningHours, regularSecondaryOpeningHours, currentSecondaryOpeningHours, editorialSummary, accessibilityOptions, paymentOptions, parkingOptions, goodForChildren, goodForGroups, allowsDogs, restroom, reservable, takeout, delivery, dineIn, curbsidePickup, outdoorSeating, liveMusic, menuForChildren, servesBreakfast, servesLunch, servesDinner, servesBeer, servesWine, servesBrunch, servesVegetarianFood, servesCocktails, servesCoffee, servesDessert, goodForWatchingSports, generativeSummary
  ```
- **Between pages,** the script waits 2 seconds before using a page token. Whether the wait is needed wasn't tested.
- **Result:** 60 places in 3 requests per search, 8.0 s end to end (city) and 9.9 s (ZIP).
- **Cost:** $40 per 1K requests on that SKU, with 1,000 free requests a month. That's 50 requests per 1K places, so **$2.00 per 1K places**.
- **What this repo keeps:** the request records (body, status, timing) and the place IDs. Google's terms don't allow storing the rest of the Places content (3.2.3(b)), so it's removed. To get it, run `python3 run.py places` and `python3 run.py places --area=zip60605` with your own key; the scripts then score Places too.

## How it's scored

The full rules are in `score.py`, with the data map in `semantic.py` and the cleanliness and accuracy checks in `compare.py`. Scores come from the ZIP run (Scrap.io: the city run).

**Step 1: the data level sets the score range.** These APIs don't do the same job, so each one lands in one of three levels by how deep its data goes, and less data never outranks more data:

| Level | What it means | Range | Tools |
|---|---|---|---|
| Lead data | the full profile plus each business's website: emails, email verification, socials, extra phones | 7 to 10 | lobstr.io, Apify, HasData (Scrap.io, unranked) |
| Full profile | each place's own page: claimed and closed status, review breakdown, booking links | 4 to 7 | Outscraper, DataForSEO, Bright Data (Google Places, baseline) |
| Listing | the search results page: rating, review count, position | 1 to 4 | SerpApi, ScrapingDog |

**Step 2: inside its range, Data carries 90% of the score.**

```
Overall = level floor (7 / 4 / 1) + 0.27 × Data + 0.03 × mean(Cost, Speed, Usability)
```

Every sub-score is out of 10.

- **Data:** 46 data points (address parts, contacts, ratings, categories, hours, status, links, photos and so on), matched by what each field holds rather than by its key name (`semantic.py`). Each point weighs 1, except **email 4, verified email 4 and social profile 2**. A point counts when it's filled on at least 10% of the tool's own results. The sum, out of the maximum, is then multiplied by:
  - **cleanliness:** 1 minus the share of off-target (non-dental), duplicate, permanently closed and placeholder-contact results
  - **accuracy:** agreement with the majority value of phone, website, rating, review count, ZIP and street number, on businesses returned by at least 5 tools
  - **freshness:** ×0.5 for a database snapshot instead of a live scrape (Scrap.io)
- **Cost:** the price per 1K places on each tool's scale plan, divided by the data it delivers per place (the same weights, by fill, times cleanliness, accuracy and freshness). One scale across every API: the cheapest per data point scores 10, and every 10× dearer loses 2.5. lobstr.io and HasData charge extra per place with an email, so both are priced at a **33% email rate** (lobstr.io's average across millions of rows), not at this run's rate: lobstr.io 3 credits + 33% × 3 = 3.99 credits per place, $1.995 per 1K places on Team; HasData 3 credits + 33% × 7 = 5.31 credits, $0.368 per 1K places on Growth. Apify bills its contact lookup per place with a website, not per email: $4.64 to $5.18 per 1K places on Business, $4.91 midpoint.
- **Speed:** data delivered per second, with everything on, on the mean time per 100 places of both runs. Same scale: the fastest scores 10, every 10× slower loses 2.5.
- **Usability:** up to 10 yes/no checks, scored passed / applicable × 10:
  1. Official SDK
  2. Integrations (Make, Zapier, n8n or webhooks)
  3. MCP server
  4. Flexible input: at least 2 of free text, structured location parameters and a Google Maps URL
  5. One typed record per business
  6. Run cost visible through the API
  7. No blocker in our runs
  8. Error handling: a failure comes back with a clear status or error code, and you either don't pay for it or can resume it
  9. No data lost when a run fails (only for APIs that queue a job)
  10. Results kept in the cloud for at least 7 days (only for APIs that queue a job)

  SerpApi, ScrapingDog and DataForSEO (tested in Live mode) answer in the same call, so checks 9 and 10 don't apply to them.

Google Places is scored the same way but kept out of the ranking, and out of the "best of all tools" reference for Cost and Speed.

## Results

From `analysis/scorecard.json`. The article rounds to one decimal.

| # | API | Level | Overall | Data | Cost | Speed | Usability | Per 1K places at scale |
|---|---|---|---|---|---|---|---|---|
| 1 | lobstr.io (category + city input) | Lead data | 9.35 | 7.95 | 5.64 | 5.54 | 9 | $2.00 |
| 2 | Apify | Lead data | 8.96 | 6.49 | 4.31 | 6.77 | 10 | $4.64 to $5.18 |
| 3 | HasData | Lead data | 8.10 | 3.40 | 6.53 | 5.73 | 6 | $0.37 |
| 4 | Outscraper | Full profile | 5.52 | 4.86 | 5.99 | 9.19 | 6 | $1.00 |
| 5 | DataForSEO | Full profile | 5.41 | 4.11 | 10 | 10 | 10 | $0.02 |
| 6 | Bright Data | Full profile | 5.16 | 3.58 | 5.34 | 6.54 | 7 | $1.30 |
| 7 | SerpApi | Listing | 2.00 | 2.72 | 6.41 | 9.98 | 10 | $0.36 |
| 8 | ScrapingDog | Listing | 1.86 | 2.13 | 9.20 | 9.77 | 10 | $0.02 |
| – | Google Places API (baseline) | Full profile | 5.35 | 4.15 | 5.11 | 10 | 7.5 | $2.00 |
| – | Scrap.io (unranked, database snapshot) | Lead data | 8.01 | 3.10 | 3.61 | 8.41 | 5 | $4.90 to $4.99 |

lobstr.io's Maps URL input scored 9.31 overall (Data 7.79, Cost 5.65, Speed 5.60, Usability 9).

Field counts per tool ("Volume" in the article: lobstr.io 136, Apify 138, Bright Data 77, Outscraper 65, DataForSEO 51, HasData 42, SerpApi 41, ScrapingDog 38) come from `schema_keys.py`: every field path across both runs, nested keys included, with keys that are data (days, hours, numbers) counted once.

## Reproduce

Standard-library Python 3 only, nothing to install.

**Rerun the analysis on the files in this repo:**

```bash
python3 compare.py        # writes analysis/compare_city.json and analysis/compare_zip60605.json
python3 run_semantic.py   # prints the data points per shared listing and the accuracy check
python3 score.py          # writes analysis/scorecard.json
python3 schema_keys.py    # prints the field counts, writes analysis/field_paths/
python3 zip_coverage.py   # prints the businesses inside ZIP 60605 found by each tool
```

This gives the same numbers as the article for every third-party API. Google Places is skipped, because this repo keeps only its place IDs: `analysis/` as committed was produced with the full Places responses, so a rerun on this repo drops the Places line from `scorecard.json` (and its field paths) and changes nothing else.

**Run the APIs yourself:**

```bash
cp .env.example .env      # then put your own keys in .env
python3 run.py <tool> [--area=zip60605]
```

Tools: `lobstr_a` (lobstr.io, category + city input), `lobstr_b` (lobstr.io, Maps URL input), `apify`, `outscraper`, `hasdata`, `serpapi`, `dataforseo`, `scrapio`, `scrapingdog`, `places`, `brightdata`. Add `--dry` to print the requests without sending them. Then run `compare.py`, `run_semantic.py` and `score.py` as above.

Notes:

- Google's results change every day, so a fresh run returns a different set of businesses. The files here are what each API returned on the run dates.
- `run.py hasdata` writes to `raw/hasdata/`, while `compare.py` reads the city run's HasData results from `raw/hasdata_final/` (see below). Rename the folder after a city run.
- The run times in `score.py` are taken from the `meta.json` files: `seconds_total` for most tools, `seconds_to_finished` for HasData's city run, and the job's own start and end times for HasData's ZIP run (53 s for 60 places, scaled to 100).
- `rerun_lobstr_zip.py` reruns lobstr.io's category + city input on ZIP 60605 with nothing switched on, for the listing-only time the article quotes (24 s for 100 places).

## How many dentists are in ZIP 60605?

The article says the best tool found "23 of 29 in-ZIP dentists". The 29 is every business whose ZIP is 60605 in any output of the ZIP run: **26 found by the benchmark tools, plus 3 that only the 200-result lobstr.io run returned** (`raw/zip60605/lobstr_200_results_run/`) (Dr. Christopher Isabelle, Dr. Jamal Flowers, Justin A. Welke D.D.S.). Outscraper found 23 of them, the most of the benchmark tools; the 200-result lobstr.io run also found 23. `python3 zip_coverage.py` prints the count per tool. Google Places adds no in-ZIP business the others missed (it shows 0 on this repo, which keeps only its place IDs).

One of the 29 is not a dentist: Outscraper's DentroLux, a marketing agency (the off-target result the article mentions). Counting dental categories only, it's **28 in-ZIP dentists, and Outscraper found 22 of them** (the 200-result lobstr.io run: 23). The script prints both counts.

## What's in here

```
run.py               one runner per API; saves every request and response
compare.py           maps each tool's fields onto common fields; fill, cleanliness and accuracy
semantic.py          the 46 data points, matched by meaning, per tool
run_semantic.py      data points on the dentists every tool returned, and the accuracy check
score.py             the scorecard
schema_keys.py       field counts per tool
zip_coverage.py      businesses inside ZIP 60605 found by each tool, and by all of them together
rerun_lobstr_zip.py  lobstr.io listing-only rerun on ZIP 60605
analysis/            compare_city.json, compare_zip60605.json, scorecard.json, field_paths/
raw/<tool>/          city run
raw/zip60605/<tool>/ ZIP run
```

Each `raw/` folder holds:

- `NNN.json`: one request and its response, in order
- `meta.json`: the input, the timings, the usage counters before and after, and the request log
- `results.json`: every row returned

Folders worth a note:

- `raw/hasdata_final/`: the city run's HasData job. The job ended with a status its docs don't list (`finished_with_error`, stop reason `data_limit_exceeded`), so the script kept polling after it had finished; the final job status and the 100 rows were then fetched again into this folder. `poll_log.json` is the original polling session's request log (times, job status and row count per request, response bodies left out), which dates the finish at 16 min 28 s.
- `raw/zip60605/lobstr_a_rerun_listings/`: the listing-only rerun.
- `raw/zip60605/lobstr_200_results_run/`: an extra lobstr.io run on the same ZIP search (category `dentist`, city `Chicago 60605`), listings only, with up to 200 results instead of 100, started from the lobstr.io dashboard and fetched through the API (`meta.json` holds the run, the Squid settings, the task and the credits). It isn't scored; it's only used for the ZIP coverage count (see "How many dentists are in ZIP 60605?").
- Bright Data's city run: the script's own snapshot download hung for about 5 minutes after the snapshot was ready, so the same snapshot was downloaded separately (noted in its `meta.json`).

## What was removed before publishing

- **API keys** are replaced with `<key>`.
- **Account details:** emails, usernames, account, user and customer IDs, logins, balances, plan renewal dates and other account settings are removed from the account responses (lobstr.io `/user/balance` and Squid settings, Apify `/users/me/limits` and run records, Outscraper `/profile/balance`, DataForSEO `user_data`, SerpApi `account.json`, ScrapingDog `/account`, Scrap.io `/subscription`, HasData job records). The usage counters the article relies on stay: lobstr.io's `available`/`consumed` credits and per-run credit breakdown, Apify's `usageTotalUsd` and `chargedEventCounts` (and monthly usage in USD), Outscraper's "Google Maps Data" usage line, DataForSEO's per-call `cost`, SerpApi's search counters, ScrapingDog's `requestUsed`, Scrap.io's export credits and HasData's `creditsSpent`.
- **Scraped emails:** the part before the @ is replaced with `masked-` plus the first 10 hex characters of the SHA-256 of the full address, as returned; the domain is kept (`info@example-dental.com` → `masked-1a2b3c4d5e@example-dental.com`). This applies to every email in every file, in any field or inside text. The same email always gets the same mask, so the scripts count, dedupe and match emails and their verification status exactly as on the originals. The placeholder address `john.smith@somedomain.com` is left as returned, because `compare.py` flags it. Scrap.io's name fields next to its emails (`firstname`, `lastname`, `gender`) are replaced with `[removed]`.
- **Reviewers and other private individuals:** in review snippets and customer posts, the person's name, profile link, photo URL and profile stats are replaced with `[removed]`; the rating, date and text stay. Fields: Bright Data `top_reviews[]` and `reviews_snippets[]` (`reviewer_name`, `reviewer_image_url`, `reviewer_photos_number`, `reviewer_reviews_number`), Scrap.io `reviews_highlighted[]` (`author.name`, `author.profile_link`, the review `link`, and reviewer photos emptied), Apify `updatesFromCustomers` (`postedBy.*`, `media[].link`). The keys stay, so the field counts don't change.
- **Google Places content** is reduced to place IDs (see the Places method above).
- **Script changes for publishing:** `run.py` reads keys from a `.env` next to it, comments were tidied, and `score.py` skips a tool with no data in `raw/` (Places in this repo). The scoring code is otherwise the code that produced the article's numbers.
