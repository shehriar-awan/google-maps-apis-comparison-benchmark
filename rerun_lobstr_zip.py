#!/usr/bin/env python3
"""Rerun lobstr.io (category + city input) on ZIP 60605 with listings only: no emails, details,
images or verification, to time the listing on its own. Same task and default filters as the
benchmark run. Saved to raw/zip60605/lobstr_a_rerun_listings/.
Usage: python3 rerun_lobstr_zip.py
"""
import sys
sys.argv += ['--area=zip60605']
import run

rec = run.Recorder('lobstr_a_rerun_listings')
H = {'Authorization': 'Token ' + run.ENV['LOBSTR_API_KEY']}
B = run.LOBSTR
task = {'category': 'dentist', 'country': 'United States', 'city': 'Chicago 60605'}
rec.meta['input'] = task
_, sq = rec.req('POST', f'{B}/squids', H, {'crawler': run.LOBSTR_CRAWLER, 'name': 'benchmark dentists zip60605 a rerun listings'})
sid = sq['id']; rec.meta['squid'] = sid
rec.req('POST', f'{B}/squids/{sid}', H, {
    'params': {'country': 'United States', 'language': 'English (United States)', 'max_results': run.MAX,
               'auto_verify_emails': False,
               'functions': {'extract_emails_from_website': False, 'collect_business_details': False,
                             'fetch_business_images': False}},
    'export_unique_results': True})
rec.meta['squid_after_update'] = rec.req('GET', f'{B}/squids/{sid}', H)[1]
rec.req('POST', f'{B}/tasks', H, {'squid': sid, 'tasks': [task]})
t0 = run.now(); rec.meta['submitted'] = run.iso(t0)
_, r = rec.req('POST', f'{B}/runs', H, {'squid': sid})
rid = r['id']; rec.meta['run'] = rid
last = run.poll(lambda: rec.req('GET', f'{B}/runs/{rid}', H)[1],
                lambda x: isinstance(x, dict) and x.get('status') in ('done', 'error', 'aborted'), every=5)
rec.meta['seconds_to_done'] = round(run.now() - t0, 1); rec.meta['run_final'] = last
res = rec.req('GET', f'{B}/results?run={rid}&page=1&page_size={run.MAX}', H)[1]
rec.meta['run_credits'] = rec.req('GET', f'{B}/runs/{rid}/credits', H)[1]
rec.save((res or {}).get('data'))
