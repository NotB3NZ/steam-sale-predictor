"""Phase 5B.2: deterministic offline source-feasibility artifacts, never labels.

External research is recorded separately in a reviewed JSON evidence ledger.
This script only reads local inputs; it does not collect prices or access sites.
"""
import argparse
from collections import Counter
import importlib.util
import io
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('coverage_investigation', ROOT / 'src/05_investigate_sale_coverage.py')
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)
audit = coverage.audit
PILOT = 'data/intermediate/autumn_sale_verification_pilot.csv'
EVIDENCE = 'data/intermediate/autumn_sale_verification_evidence.csv'
REPORT = 'reports/autumn_sale_ground_truth_feasibility.md'
VALIDATION = 'reports/autumn_sale_ground_truth_validation.json'
INVENTORY = 'reports/sources/historical_price_source_inventory.json'
LEDGER = 'reports/sources/historical_price_verification_ledger.json'
OUTPUTS = (PILOT, EVIDENCE, REPORT, VALIDATION)
MANIFEST = 'reports/sources/phase_5b2_input_manifest.json'


def protected_hashes(root):
    """Use the inventory captured before this task, including uncommitted 5B.1 work."""
    expected = json.loads((root / MANIFEST).read_text())['protected_sha256']
    actual = {p: audit.digest(root / p) for p in sorted(expected)}
    coverage.require(actual == expected, 'A protected input differs from the pre-work manifest')
    return actual


def source_hashes(root):
    paths = [INVENTORY, LEDGER, MANIFEST, 'src/06_verify_historical_ground_truth.py',
             'tests/test_historical_ground_truth.py']
    return {p: audit.digest(root / p) for p in paths}


def select_pilot(rows):
    """18 diagnostic pairs; ordered strata, numeric AppID tie-breaking, no random state.

    All B; one recent full-price D per year + one additional closest D; three
    old D across years/distinct games; three recent discounted D; two A controls;
    two additional conflict-bearing A; one empty history. Strata add unique pairs.
    Recency of 30 days is a sampling stratum, not a coverage/label rule.
    """
    selected = {}
    key = lambda r: (r['appid'], int(r['sale_year']))
    stable = lambda r: (int(r['appid']), int(r['sale_year']))
    def add(row, reason):
        if key(row) in selected:
            selected[key(row)]['selection_rationale'] += '; ' + reason
        else:
            fields = ['appid', 'name', 'sale_year', 'evidence_category', 'sale_start_utc', 'sale_end_utc',
                      'release_date', 'eligibility_reason', 'pre_observed_state', 'post_observed_state',
                      'pre_gap_days', 'post_gap_days', 'pre_timestamp_utc', 'post_timestamp_utc',
                      'pre_price', 'pre_regular_price', 'pre_cut', 'post_price', 'post_regular_price', 'post_cut',
                      'in_window_record_count', 'in_window_discount_count', 'in_window_full_price_count',
                      'history_conflicting_timestamp_groups', 'empty_raw_history']
            selected[key(row)] = {f: row[f] for f in fields}
            selected[key(row)]['selection_rationale'] = reason
    for row in sorted([r for r in rows if r['evidence_category'] == 'B'], key=stable):
        add(row, 'all_Category_B; includes unresolved same-day eligibility where applicable')
    recent_full = sorted([r for r in rows if r['evidence_category'] == 'D' and
                          r['pre_observed_state'] == 'full_price' and r['pre_gap_days'] != '' and
                          float(r['pre_gap_days']) <= 30], key=lambda r: (float(r['pre_gap_days']), *stable(r)))
    for year in (2023, 2024, 2025):
        add(next(r for r in recent_full if int(r['sale_year']) == year), f'recent_full_price_D; closest in {year}; sampling-only 30-day stratum')
    add(next(r for r in recent_full if key(r) not in selected), 'recent_full_price_D; additional smallest pre-gap')
    used_old_games = set()
    for year in (2023, 2024, 2025):
        old = sorted([r for r in rows if r['evidence_category'] == 'D' and int(r['sale_year']) == year
                      and r['pre_gap_days'] != '' and r['appid'] not in used_old_games and key(r) not in selected],
                     key=lambda r: (-float(r['pre_gap_days']), *stable(r)))
        add(old[0], f'very_old_D; longest pre-gap in {year}; distinct games across old stratum')
        used_old_games.add(old[0]['appid'])
    recent_discount = sorted([r for r in rows if r['evidence_category'] == 'D' and
                              r['pre_observed_state'] == 'discount' and r['pre_gap_days'] != '' and
                              float(r['pre_gap_days']) <= 30], key=lambda r: (float(r['pre_gap_days']), *stable(r)))
    for row in [r for r in recent_discount if key(r) not in selected][:3]:
        add(row, 'recent_discount_D; three smallest pre-gaps; no persistence inference')
    for year in (2023, 2025):
        controls = sorted([r for r in rows if r['evidence_category'] == 'A' and int(r['sale_year']) == year
                           and int(r['history_conflicting_timestamp_groups']) == 0 and key(r) not in selected], key=stable)
        add(controls[0], f'positive_control_A; smallest eligible AppID without history conflicts in {year}')
    seen_conflicts = set()
    conflicted = sorted([r for r in rows if int(r['history_conflicting_timestamp_groups']) > 0 and key(r) not in selected],
                        key=lambda r: (-int(r['history_conflicting_timestamp_groups']), *stable(r)))
    for row in conflicted:
        if row['appid'] not in seen_conflicts:
            add(row, 'historical_timestamp_conflict; highest group count then AppID/year; distinct games')
            seen_conflicts.add(row['appid'])
            if len(seen_conflicts) == 2:
                break
    empty = sorted([r for r in rows if r['evidence_category'] == 'D' and r['empty_raw_history'] == 'True'
                    and key(r) not in selected], key=stable)
    add(empty[0], 'empty_ITAD_history; smallest AppID/year; absence is not a negative')
    result = sorted(selected.values(), key=lambda r: (int(r['sale_year']), int(r['appid'])))
    audit.require(len(result) == 18)
    audit.require({int(r['sale_year']) for r in result} == {2023, 2024, 2025})
    return [dict(selection_order=i + 1, **r) for i, r in enumerate(result)]


def validate_evidence(records, pilot, inventory, windows):
    """Validate manually reviewed source assertions; never infer unobserved states."""
    pairs = {(r['appid'], int(r['sale_year'])): r for r in pilot}
    sources = {s['source_id'] for s in inventory['sources']}
    coverage.require(len(sources) == len(inventory['sources']), 'Duplicate source IDs')
    coverage.require(len({r['attempt_id'] for r in records}) == len(records), 'Duplicate attempt IDs')
    fields = ('observation_timestamp_utc', 'observed_price', 'regular_price', 'discount_percent',
              'currency', 'region', 'steam_store_explicit', 'purchase_scope')
    result = []
    for raw in records:
        r = dict(raw)
        key = (r['appid'], int(r['sale_year']))
        coverage.require(key in pairs and key[1] in (2023, 2024, 2025), 'Evidence outside selected scope')
        coverage.require(r['source_id'] in sources, 'Unknown source')
        coverage.require(r['source_url'].startswith('https://') and r['access_date'] and
                         r['observed_fact'] and r['diagnostic_interpretation'] and r['limitations'],
                         'Missing source provenance or fact/interpretation separation')
        coverage.require(r['contradicts_itad'] in ('YES', 'NO', 'NOT_ASSESSABLE'), 'Conflict must be explicit')
        for flag in ('source_page_accessible', 'historical_price_observation_available',
                     'independently_verifiable_observation', 'supports_discount_occurrence', 'supports_full_sale_absence'):
            coverage.require(isinstance(r[flag], bool), 'Evidence flags must be explicit booleans')
        start, end = windows[key[1]][2:]
        inside = ''
        if r['observation_timestamp_utc']:
            timestamp = audit.utc_stamp(r['observation_timestamp_utc'])
            coverage.require(timestamp < coverage.CUTOFF, '2026 observations forbidden')
            coverage.require(audit.fmt(timestamp) == r['observation_timestamp_utc'], 'Timestamp must be canonical UTC')
            inside = start <= timestamp < end
        if not r['historical_price_observation_available']:
            coverage.require(all(r[f] == '' for f in fields), 'No fabricated fields for unretrieved observations')
            coverage.require(not r['supports_discount_occurrence'] and not r['supports_full_sale_absence'] and
                             not r['independently_verifiable_observation'] and r['contradicts_itad'] == 'NOT_ASSESSABLE',
                             'Missing evidence cannot support outcomes or source contradictions')
        else:
            coverage.require(r['source_page_accessible'], 'An inaccessible page is not an observation')
            coverage.require(r['observation_timestamp_utc'] or
                             (r['coverage_start_utc'] and r['coverage_end_utc']), 'Historical time required')
        if r['supports_discount_occurrence']:
            coverage.require(inside is True and r['steam_store_explicit'] is True and
                             r['independently_verifiable_observation'] and r['currency'] and r['region'] and
                             r['purchase_scope'], 'Positive assertion lacks event/store/scope provenance')
            price, regular, cut = (float(r[f]) for f in ('observed_price', 'regular_price', 'discount_percent'))
            coverage.require(all(math.isfinite(v) for v in (price, regular, cut)) and
                             0 <= price < regular and 0 < cut <= 100, 'Contradictory discount fields')
        if r['supports_full_sale_absence']:
            coverage.require(r['coverage_kind'] == 'continuous_documented_complete' and
                             r.get('completeness_documentation_url', '').startswith('https://') and
                             r.get('coverage_proof', '') and r['steam_store_explicit'] is True and
                             r['independently_verifiable_observation'] and r['currency'] and r['region'] and
                             r['purchase_scope'], 'A point observation cannot prove a full-sale absence')
            coverage.require(audit.utc_stamp(r['coverage_start_utc']) <= start and
                             end <= audit.utc_stamp(r['coverage_end_utc']) <= coverage.CUTOFF,
                             'Continuous evidence does not cover the whole permitted event')
        if r['reuse_of_attempt_id']:
            prior = next((x for x in records if x['attempt_id'] == r['reuse_of_attempt_id']), None)
            coverage.require(prior is not None and prior['source_url'] == r['source_url'], 'Invalid reused access reference')
        result.append(dict(r, name=pairs[key]['name'], evidence_category=pairs[key]['evidence_category'],
                           evidence_inside_sale=inside,
                           verification_result='HISTORICAL_EVIDENCE_RETRIEVED' if r['historical_price_observation_available'] else 'NOT_VERIFIABLE'))
    coverage.require(set(pairs) == {(r['appid'], int(r['sale_year'])) for r in records}, 'A selected pair has no recorded attempt')
    return result


def summarize(pilot, evidence):
    """Pair counts describe retrieved evidence, not target values; conflicts may overlap."""
    counts = Counter()
    for p in pilot:
        records = [r for r in evidence if r['appid'] == p['appid'] and int(r['sale_year']) == int(p['sale_year'])]
        positive = any(r['supports_discount_occurrence'] for r in records)
        absence = any(r['supports_full_sale_absence'] for r in records)
        observed = any(r['historical_price_observation_available'] for r in records)
        counts['discoverable_source_page_pairs'] += any(r['source_page_accessible'] for r in records)
        counts['historical_price_observation_pairs'] += observed
        counts['independent_positive_evidence_pairs'] += positive
        counts['full_sale_absence_evidence_pairs'] += absence
        counts['partial_only_pricing_evidence_pairs'] += observed and not positive and not absence
        counts['conflicting_source_pairs'] += any(r['contradicts_itad'] == 'YES' for r in records)
        counts['not_verifiable_pairs'] += not observed
        counts['unknown_release_hour_pairs'] += p['appid'] == '2650840' and int(p['sale_year']) == 2023
    return dict(counts)


def build_report(root, pilot, evidence, inventory, receipt):
    calendar = audit.calendar_data(root)
    prior = {(r['appid'], int(r['sale_year'])): r for r in audit.read_csv(root / coverage.DIAGNOSTICS)}
    gap = lambda value: f'{float(value):.6f}' if value != '' else 'missing'
    lines = ['# Phase 5B.2 — Historical Ground-Truth Verification and Label Feasibility', '',
             'Research/access date: **2026-10-11**. Investigation complete; external verification limited by access and evidence availability. **Final labels have not been generated. Stop for human review before Phase 5B.3.**', '',
             '## Research objective and required evidence standard', '',
             '> Given information available about a Steam game before a specific Steam Autumn Sale begins, what is the probability that the game will be discounted at any point during that sale?', '',
             'The event is a valid Steam-store discount at **any instant** inside `[start_utc, end_utc)`. Start is included; end is excluded. A positive occurrence is existential; an absence claim is universal across the entire event. Formal Valve event enrollment is a different question.', '',
             'These are minimum requirements for evaluating candidate evidence, **not an approved evidence-to-label policy**:', '',
             audit.md_table(['Evidence type', 'Minimum requirement / unresolved decision'], [
                 ['Positive discount evidence', 'Identifiable AppID/purchase option, explicit Steam storefront, historical event timestamp, currency/region and an authentic discounted offer. One valid point can demonstrate occurrence; source authenticity, eligibility and conflicts still need review.'],
                 ['Negative full-sale coverage evidence', 'A reproducible record covering every instant of the event, with documented capture completeness or an authoritative complete offer schedule, matching storefront/region/purchase scope. No unobserved gap or competing qualifying discount may remain. No investigated source established this.'],
                 ['Partial-sale evidence', 'One or several authentic historical observations with known times. Full price at those points establishes only those points; finite samples cannot rule out a temporary discount between them.'],
                 ['Missing evidence', 'No retrieved relevant observation, empty history, inaccessible page or missing archive entry. Preserve missing fields; none implies absence of a discount.'],
                 ['Conflicting evidence', 'Retain incompatible observations with both provenance chains. First resolve timestamps, regions, editions and purchase options; an apparent mismatch is not automatically a source error.'],
                 ['Unknown eligibility', 'A release date without sufficient event-time precision, delisting or purchase availability ambiguity requires separate review. nekowater 2023 remains unresolved.']]), '',
             'The frozen ITAD collection uses US / USD / Steam shop 61. Whether the eventual outcome is US-specific or across regions, which purchase options qualify, and how free promotions, bundles and rounding are treated remain human decisions. A publisher promotion announcement can corroborate a store offer only when its game, storefront and time scope are explicit; a publication date alone is not a price timestamp. No state is carried forward here.', '',
             '## Inputs, provenance and unchanged scope', '',
             'The existing 100-game pilot and 300 game-sale diagnostics are unchanged. Original A/B/C/D totals remain **175/3/0/122**; the 178 directly timestamped in-sale records remain prior-phase evidence, not independent verification. Frozen histories contain 5,568 records; the existing 5B.1 pre-2026 scope contains 4,716. This phase reads the saved diagnostics; it does not recollect prices or rewrite them.', '',
             'Exact events reuse the verified centralized calendar and its original Valve references:', '',
             audit.md_table(['Year', 'UTC start (inclusive)', 'UTC end (exclusive)', 'Pacific', 'Existing source'], [
                 [e['sale_year'], e['sale_start_utc'], e['sale_end_utc'], '10 AM PST' if e['sale_year'] < 2025 else '10 AM PDT', f"[Valve]({e['source_url']})"] for e in calendar['events']]), '',
             'All 300 pairs are eligible under the original release-date rule, but nekowater’s unknown release hour is not resolved. Only 2023–2025 events are investigated. Current-year outcomes seen incidentally in live pages/search results are excluded, along with current prices and wrong-year promotions.', '',
             'Inputs and pre-work hashes: [Phase 5B.2 input manifest](sources/phase_5b2_input_manifest.json). Existing reports: [coverage investigation](autumn_sale_coverage_investigation.md), [exact-window audit](autumn_sale_evidence_audit.md), and [boundary comparison](autumn_sale_boundary_comparison.md).', '',
             '## Sources investigated and access constraints', '',
             'The [source inventory](sources/historical_price_source_inventory.json) records eleven candidates across all five requested families, field-level availability, access dates, verified facts and unresolved questions. “Not established” means a guarantee or capability was not verified; it does not mean the source has no data. Documentation can describe a source without establishing any selected game’s outcome.', '',
             audit.md_table(['Candidate / family', 'Observed access or suitability', 'Primary reference'], [
                 [s['name'] + ' / ' + s['family'], s['investigation_status'], f"[Reference]({s['documentation_urls'][0]})"] for s in inventory['sources']]), '',
             'SteamDB automation was stopped because permission is required; no app price pages were scraped. Its event calendar alone supplies no full-sale absence proof. See the [FAQ](https://steamdb.info/faq/).', '',
             'Steam’s [news method](https://partner.steamgames.com/doc/webapi/ISteamNews) can locate publisher posts; posts are not complete price monitoring. [Publisher financial access](https://partner.steamgames.com/doc/webapi/IPartnerFinancialsService) requires authorized credentials. No credentials were supplied or bypassed. Transactions also do not describe offers when nobody purchased.', '',
             'Wayback’s [documented lookup](https://archive.org/help/wayback_api.php) and [CDX documentation](https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server) identify captures. The Droid Assault lookup failed through the research tool; no index result or snapshot was obtained. Its HTTP cause is unknown. Archive verification stopped at that limitation; other pilot pairs were not individually queried. A failed request is not an empty archive. [Replay limitations](https://help.archive.org/help/using-the-wayback-machine/) also require checking missing assets and live substitutions before trusting a captured price.', '',
             'Common Crawl provides a documented archive route, but no selected AppID capture or WARC was retrieved in this phase. Future lookup must follow its [rate guidance](https://blog.commoncrawl.org/faq) and [terms](https://commoncrawl.org/terms-of-use); underlying content rights still apply. Crawl samples cannot by themselves establish uninterrupted offer coverage.', '',
             'One [Steambase tracker](https://steambase.io/games/have-a-nice-death/price) was inspected for source discovery. The rendered monthly table did not expose the selected 2023 event. No chart export or price data was collected. [Reuse terms](https://steambase.io/legal/terms/) and its [completeness disclaimer](https://steambase.io/legal/fair-use/) prevent assuming an unrestricted complete source. Bulk collection/republication was not undertaken.', '',
             'CheapShark documentation could not be read sufficiently to verify a suitable endpoint; GG.deals documentation retrieval failed. No undocumented endpoints were guessed. The reviewed public metadata dataset is a snapshot rather than an event-resolution price log. These candidates remain unsuitable or unresolved for the present verification, not proven globally unavailable.', '',
             '## Diagnostic verification pilot', '',
             '**Selection is diagnostic, not representative:** 18 pairs / 17 distinct games; A=4, B=3, C=0, D=11. Years contain 9 / 3 / 6 pairs. All three B pairs are mandatory. Remaining strata deliberately cover recent full-price D, very old D, recent discounted D, positive controls, historical timestamp conflicts and an empty history.', '',
             'Selection has no randomness: numeric AppID/year tie-breaking; recent full-price D chooses the closest per year plus another closest; old D chooses the longest per year with distinct games; recent discounted D chooses the three smallest pre-gaps; A controls use the smallest eligible AppID without conflicts in 2023/2025; two additional conflict-bearing games are ranked by conflict count; an empty history uses the smallest AppID/year. The 30-day stratum is only for sampling. No threshold is approved as a coverage rule.', '',
             '[Pilot CSV](../data/intermediate/autumn_sale_verification_pilot.csv) preserves original categories and a rationale for every pair. [Evidence CSV](../data/intermediate/autumn_sale_verification_evidence.csv) preserves exact source URLs, access status and separate observed-fact/interpretation fields. Empty historical time/price/currency fields mean no observation was retrieved; they are never zeros.', '',
             audit.md_table(['AppID', 'Game', 'Year', 'Category', 'Pre / post observed state', 'Pre / post gap (days)', 'Independent result'], [
                 [r['appid'], r['name'], r['sale_year'], r['evidence_category'], f"{r['pre_observed_state']} / {r['post_observed_state']}", f"{gap(r['pre_gap_days'])} / {gap(r['post_gap_days'])}", 'NOT_VERIFIABLE'] for r in pilot]), '',
             '## Verification findings: discoverability is not ground truth', '',
             audit.md_table(['Level / result (pair-level)', 'Count'], list(receipt['verification_counts'].items())), '',
             '**Observed facts:** Seven of 17 distinct Steam app-news feeds were accessible in the returned extracts, covering eight selected pairs because Men of War appears twice. Ten pairs’ feed requests failed. The additional Steambase page concerns a pair already discoverable. None yielded a relevant historical price observation, continuous price interval or source contradiction. A 2023 Steam Awards post for Have a Nice Death is non-pricing evidence and is not counted as partial price coverage.', '',
             '**Verification outcome:** independently positive **0**, full-sale absence **0**, partial-only historical pricing **0**, conflicting independent observations **0**, unverifiable **18**. Conflict counts may overlap other evidence counts when observations exist; unknown release-hour count is a separate eligibility flag. Zero independent conflicts does not clear the known ITAD conflicts: no independent observation was available to compare.', '',
             'A positive control is an ITAD-positive pair selected to test an independent source, not an independently verified positive. FATE posts for a later sale year and unrelated-year Have a Nice Death promotions were excluded from the selected pairs. Finding a discount for a different year would not verify these pairs; the selection was not changed to favor accessible promotions.', '',
             'The reviewed ledger contains 21 pair-source attempt rows: 18 app-feed rows (17 distinct URLs, one reused), one public news API probe, one archive-index probe and one Steambase inspection. Searches and documentation access are additional. Underlying web-tool HTTP totals are unavailable. Generic access errors are not described as CAPTCHAs, bans, empty histories or paywalls without supporting evidence. No bypasses or alternative restricted routes were used.', '',
             '## Special cases and existing conflicting evidence', '',
             'The following tables reproduce **existing ITAD observations only**, with raw-array provenance. They are not independent confirmations or reconstructed prices. All original B cases and both ordinary A controls are shown:', '']
    for p in pilot:
        if p['evidence_category'] == 'B' or 'positive_control_A' in p['selection_rationale']:
            row = prior[(p['appid'], int(p['sale_year']))]
            lines += [f"### {p['name']} ({p['appid']}), {p['sale_year']} — {p['evidence_category']}", '']
            observations = []
            for relation, field in [('pre', 'pre_nearest_records_json'), ('in', 'in_window_records_json'), ('post', 'post_nearest_records_json')]:
                observations += [[relation, r['source_record_index'], r['timestamp_utc'], r['price'], r['regular_price'], r['cut'], r['price_currency']]
                                 for r in json.loads(row[field])]
            lines += [audit.md_table(['Relation', 'Raw index', 'UTC timestamp', 'Price', 'Regular', 'Cut', 'Currency'], observations), '',
                      'Independent historical price verification: NOT_VERIFIABLE. The observed sequence does not establish persistence or full-sale absence.', '']
    lines += ['nekowater (2650840), 2023, was released on the event start date. The observed full-price record at 22:39:17 UTC does not determine its release hour or whether it was purchasable throughout the event. HOPE LEFT ME has no post-sale record within the permitted observation scope; this does not establish a permanently unchanged offer.', '',
              'Men of War (7830), 2024 D, has a pre-sale discount at `2024-11-26T18:18:34Z` (USD 0.74 / 4.99, cut 85; raw index 25), and a post-sale full price at `2024-12-04T18:17:52Z` (USD 4.99 / 4.99, cut 0; index 24). The latter is only 17 minutes 52 seconds after event end. This resembles a discount-end pattern but neither observation proves the price inside the event. The public feed supplied no corroborating historical offer.', '',
              'Railway Islands 2 (2621900), 2023, and The Great Ace Attorney Chronicles (1158850), 2025, likewise have recent pre-sale discounts and no in-window records. Droid Assault (219200), 2025, has recent pre-sale full price but a 73-day post gap; its failed Wayback lookup does not resolve that interval. QUICKERFLAK (1836120), 2025, and the two other recent-full-price D cases remain unverified.', '',
              'The old-observation stratum includes Civilization V (8930), 2023; Scoregasm (202410), 2024; and CubeZ (314300), 2025, with pre-gaps shown above reaching 1,732.708333 days. Monster (1894600), 2023, has an empty ITAD history and no pre/post state. None has independent retrieved target-price evidence.', '',
              'Prototype 2 (115320) has three conflicting historical timestamp groups and Rush Bros. (234490) has one. These are pre-event ITAD conflicts, not new source disagreements. Their exact raw-index sequences remain in the unchanged [coverage diagnostics](../data/intermediate/autumn_sale_coverage_diagnostics.csv) and [prior report](autumn_sale_coverage_investigation.md). Neither public feed resolved them; no record was deleted or overwritten.', '',
              '## Strategy comparison and label feasibility', '',
              '**Diagnostic interpretation:** the current retrieved evidence does not support a defensible binary outcome dataset. No independent full-sale negative was established. This does not prove that reliable negatives cannot ever be obtained; permissioned complete histories or authoritative publisher schedules remain untested possibilities.', '',
              audit.md_table(['Strategy', 'Validity / coverage / false-negative risk', 'Bias, reproducibility, access and scale'], [
                  ['A — retain direct ITAD discounts as positive evidence; others unresolved', '175 positive-evidence candidates across 300 pairs; 125 others remain unresolved. Requires eligibility/conflict review. No inferred negatives. Cannot support ordinary binary logistic-regression training/evaluation by itself.', 'Offline and reproducible; access already available. Observation availability can bias which positives are visible. Retain evidence without creating labels.'],
                  ['B — ITAD positives plus independently verified full-sale negatives', 'Conceptually defensible if entire-event absence is genuinely established. Present independent negative coverage is zero; combining single full-price snapshots is insufficient.', 'Permission/access and completeness proof unresolved. Easily verified or well-known games may be overselected; scale cannot be estimated from this blocked pilot.'],
                  ['C — reconstruct from a demonstrably complete change log', 'Could cover intervening instants only with justified completeness, initial-state validity, purchase scope and timestamp accuracy. No investigated source meets this standard yet.', 'Requires documented guarantees, permissioned export and source/version capture. Monitoring outages and corrections can create false negatives; no reconstruction implemented.'],
                  ['D — independent archived Steam snapshots', 'Authentic in-event discounted points can support occurrence. Full-price points give partial coverage; a finite set cannot rule out an unobserved temporary discount.', 'Documented archive access exists, but the probe failed. Sampled capture availability, geolocation, age gates, JavaScript and replay assets introduce bias. No interval completeness established.'],
                  ['E — permissioned publisher historical offer/discount schedules', 'A complete authoritative offer schedule could resolve a limited cooperating cohort; transaction reports alone are insufficient. No schedules obtained or guarantees verified.', 'Requires publisher/source cooperation and lawful reproducible access. Cohort would likely be selected; any reduced population/research question needs explicit approval.']]), '',
              '**Most defensible next step:** use Strategy A as an evidence-retention approach while leaving unresolved pairs unresolved, not as a finalized label-generation decision. Seek authorized source exports or publisher schedules with explicit completeness before considering Strategy B/C/E. A binary label dataset and logistic regression remain blocked by negative ground truth; label count or class balance is not a reason to weaken the evidence standard.', '',
              'For the 300 pairs, practical verification requires game/purchase-option/region identity, timestamp alignment, preservation of source payloads, and coverage review over each full event—not merely 300 successful page loads. The 18-pair pilot did not measure a successful verification rate or review throughput. Approximately 99,194 master games imply at most **297,582 game-year reviews** before eligibility filtering. No time/cost estimate or automated scaling claim is supported. Permissioned batch exports would need separate feasibility testing; sampled archives might add positive points without resolving the negative bottleneck.', '',
              'Source discoverability and source coverage can favor popular titles, long-lived store pages, active publishers and regions frequently crawled. The deliberately difficult pilot cannot estimate population source availability. Source availability may correlate with the intended outcome and predictors, so complete-case training could be biased. Independent vendor branding also does not establish independent collection; shared upstream Steam or ITAD data must be checked.', '',
              '## Unresolved human decisions', '',
              '- Define geographic and purchase-option scope, qualifying discounts/free promotions and release eligibility at event-hour precision.',
              '- Decide what authenticated completeness evidence would justify absence or interval reconstruction, and how outages, conflicts and rounding are adjudicated.',
              '- Decide whether to obtain authorized exports/publisher cooperation, attempt permitted archive retrieval in an environment where it works, or revise the study cohort/question.',
              '- Determine how unresolved outcomes and source-selection bias will be handled; no 1/0/UNKNOWN mapping is approved or implemented.',
              '- Keep 2026 outcomes reserved for the planned retrospective verification; no current-year outcomes inform these decisions.', '',
              '## Validation and reproducibility', '',
              'Run only the new offline investigation to preserve prior analytical artifacts:', '',
              '```bash', 'python3 -B src/06_verify_historical_ground_truth.py --verify', '```', '',
              'The script consumes the reviewed local source inventory/ledger and pre-work manifest, reuses the exact calendar and existing CSV parser, and never collects external observations. A normal run checks the previous execution fingerprint; `--verify` runs the complete offline suite and two repeated executions, then repeats with the verified receipt. It protects all preceding files listed in the manifest, including uncommitted Phase 5B.1 work. Documentation changes are intentionally recorded separately from frozen inputs.', '',
              audit.md_table(['Check', 'Result'], [
                  ['Full offline test suite', f"{receipt['execution_checks']['full_offline_test_suite']}; {receipt['execution_checks'].get('tests_run', 'not run')} tests"],
                  ['Deterministic full outputs', receipt['execution_checks']['deterministic_full_runs']],
                  ['Protected pre-work files / frozen Phase 4 inputs', f"{len(receipt['protected_before_sha256'])} / {len(receipt['frozen_phase4_before_sha256'])}; before/after SHA-256 unchanged"],
                  ['Previous 300 pair keys and evidence categories', 'Unchanged; exact event timestamps reconciled'],
                  ['Research provenance / missing fields', 'All 21 attempts have source URL/access date; no invented historical observations'],
                  ['Diagnostic network attempts / ITAD pricing requests / new histories', '0 / 0 / 0'],
                  ['2026 outcome records / final target columns / models', 'None']]), '',
              'Detailed hashes and execution results: [validation receipt](autumn_sale_ground_truth_validation.json). The [research ledger](sources/historical_price_verification_ledger.json) preserves concise manually reviewed access notes; raw HTML responses were not archived, so live-source replay may change. Offline determinism is not a claim that external sites are immutable. No prior analytical report, raw cache, test or source implementation was modified. README/context/status updates only record this phase.', '',
              '**Stop gate:** Phase 5B.2 source-feasibility investigation is complete with external verification limitations explicitly recorded. No final labels, features, models or Phase 5B.3 work were created. Human review is required.', '']
    return '\n'.join(lines)


def run(root=ROOT, execution_checks=None):
    root = Path(root)
    with coverage.offline_guard() as attempts:
        before = protected_hashes(root)
        frozen = audit.frozen_hashes(root)
        audit.verify_baseline(root)
        windows = audit.canonical_windows(root)
        diagnostics = audit.read_csv(root / coverage.DIAGNOSTICS)
        old = audit.read_csv(root / 'data/intermediate/autumn_sale_evidence_audit.csv')
        key = lambda r: (r.get('appid', r.get('AppID')), int(r['sale_year']))
        coverage.require(len(diagnostics) == len({key(r) for r in diagnostics}) == 300, 'Expected 300 unique pairs')
        coverage.require({key(r): r['evidence_category'] for r in diagnostics} ==
                         {key(r): r['evidence_category'] for r in old}, 'Previous evidence categories changed')
        coverage.require({int(r['sale_year']) for r in diagnostics} == set(windows) == {2023, 2024, 2025}, 'Unexpected years')
        for r in diagnostics:
            coverage.require((r['sale_start_utc'], r['sale_end_utc']) == tuple(audit.fmt(d) for d in windows[int(r['sale_year'])][2:]),
                             'Prior diagnostics differ from event calendar')
        pilot = select_pilot(diagnostics)
        inventory = json.loads((root / INVENTORY).read_text())
        ledger = json.loads((root / LEDGER).read_text())
        coverage.require(inventory['scope_years'] == ledger['scope_years'] == [2023, 2024, 2025], 'Research scope changed')
        evidence = validate_evidence(ledger['records'], pilot, inventory, windows)
        sources = source_hashes(root)
        if execution_checks is None:
            previous = json.loads((root / VALIDATION).read_text()) if (root / VALIDATION).exists() else {}
            execution_checks = previous.get('execution_checks', {})
            if execution_checks.get('source_sha256') != sources or execution_checks.get('protected_sha256') != before:
                execution_checks = dict(full_offline_test_suite='NOT RUN: use --verify',
                                        deterministic_full_runs='NOT RUN: use --verify', source_sha256=sources, protected_sha256=before)
        coverage.require(execution_checks['source_sha256'] == sources and execution_checks['protected_sha256'] == before,
                         'Verification fingerprint changed')
        for path, rows in ((PILOT, pilot), (EVIDENCE, evidence)):
            fields = list(rows[0])
            coverage.require(not {'label', 'target', 'discounted', 'final_label', 'training_label'} & set(fields), 'Final label columns forbidden')
            coverage.require(all(set(r) == set(fields) for r in rows), 'Inconsistent record fields')
            audit.write_csv(root / path, rows, fields)
            coverage.require(audit.read_csv(root / path) == [{k: str(v) for k, v in r.items()} for r in rows], 'CSV round-trip differs')
        receipt = dict(phase='5B.2', status='source_feasibility_complete_external_verification_limited_pending_review',
                       all_existing_pairs=300, selected_pairs=len(pilot), selected_games=len({r['appid'] for r in pilot}),
                       selected_categories=dict(Counter(r['evidence_category'] for r in pilot)),
                       selected_years=dict(Counter(r['sale_year'] for r in pilot)), source_candidates=len(inventory['sources']),
                       evidence_attempt_rows=len(evidence), verification_counts=summarize(pilot, evidence),
                       categories_by_year={str(y): {c: sum(int(r['sale_year']) == y and r['evidence_category'] == c for r in diagnostics)
                                                   for c in 'ABCD'} for y in windows},
                       execution_checks=execution_checks,
                       checks=dict(unique_pairs=True, categories_unchanged=True, exact_calendar_unchanged=True,
                                   scope_excludes_2026=True, provenance_complete=True, no_final_label_columns=True,
                                   missing_evidence_never_negative=True, saved_csv_round_trip=True,
                                   baseline_verified=True, diagnostic_network_attempts=len(attempts), itad_pricing_requests=0,
                                   new_histories=0, protected_files_unchanged=True),
                       frozen_phase4_before_sha256=frozen, frozen_phase4_after_sha256=audit.frozen_hashes(root),
                       protected_before_sha256=before, protected_after_sha256=protected_hashes(root), source_sha256=sources,
                       external_research='Authorized documentation/public-page research separate from offline execution; HTTP totals unavailable; see ledger for exact attempted URLs.',
                       output_sha256={p: audit.digest(root / p) for p in (PILOT, EVIDENCE)})
        report = build_report(root, pilot, evidence, inventory, receipt)
        (root / REPORT).write_text(report, encoding='utf-8')
        receipt['output_sha256'][REPORT] = audit.digest(root / REPORT)
        (root / VALIDATION).write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
        coverage.require(before == protected_hashes(root), 'Prior-phase files changed')
    return pilot, evidence, receipt


def verify_execution(root=ROOT):
    root = Path(root)
    before = protected_hashes(root)
    with coverage.offline_guard():
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.discover(str(root / 'tests')))
        print(stream.getvalue(), end='')
        coverage.require(result.wasSuccessful(), 'Offline test suite failed')
        sources = source_hashes(root)
        checks = dict(full_offline_test_suite='PASS', tests_run=result.testsRun, failures=len(result.failures),
                      errors=len(result.errors), skipped=len(result.skipped), deterministic_full_runs='PENDING',
                      source_sha256=sources, protected_sha256=before)
        run(root, checks)
        first = {p: (root / p).read_bytes() for p in OUTPUTS}
        run(root, checks)
        coverage.require(first == {p: (root / p).read_bytes() for p in OUTPUTS}, 'Repeated execution differs')
        checks['deterministic_full_runs'] = 'PASS: all four outputs identical in two complete runs'
        run(root, checks)
        final = {p: (root / p).read_bytes() for p in OUTPUTS}
        result = run(root, checks)
        coverage.require(final == {p: (root / p).read_bytes() for p in OUTPUTS}, 'Verified execution differs')
        coverage.require(before == protected_hashes(root), 'Protected files changed in verification')
    print(f'Phase 5B.2: {len(result[0])} selected pairs; {len(result[1])} source attempts; verification PASS.')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--show-pilot', action='store_true', help='Print selection without writing')
    parser.add_argument('--verify', action='store_true', help='Run full offline suite and deterministic executions')
    args = parser.parse_args()
    if args.show_pilot:
        print(json.dumps(select_pilot(audit.read_csv(ROOT / coverage.DIAGNOSTICS)), indent=2))
    elif args.verify:
        verify_execution()
    else:
        run()


