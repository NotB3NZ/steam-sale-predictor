"""Phase 5B.1 offline evidence diagnostics; never infer persistent states or labels.

python3 src/05_investigate_sale_coverage.py --verify

Reuses the frozen Phase 5A.1 parser/calendar. --verify runs all offline tests and
checks repeated full executions under a network prohibition. Default execution
reuses a verification receipt only when its source/input fingerprints still match.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import importlib.util
import io
import json
from itertools import groupby
from pathlib import Path
import socket
import statistics
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('phase5a1_audit', ROOT / 'src/04_audit_autumn_evidence.py')
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)
CUTOFF = audit.utc_stamp('2026-01-01T00:00:00Z')
THRESHOLDS = (7, 14, 30, 60, 90, None)
STATES = ('full_price', 'discount', 'ambiguous', 'missing')
DIAGNOSTICS = 'data/intermediate/autumn_sale_coverage_diagnostics.csv'
SENSITIVITY = 'data/intermediate/autumn_sale_coverage_sensitivity.csv'
REPORT = 'reports/autumn_sale_coverage_investigation.md'
RECEIPT = 'reports/autumn_sale_coverage_validation.json'
DOC_NOTE = 'reports/sources/itad_history_semantics.json'
OUTPUTS = (DIAGNOSTICS, SENSITIVITY, REPORT, RECEIPT)


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


@contextmanager
def offline_guard():
    """Block DNS and socket connection attempts, including library calls."""
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append('network_attempt')
        raise AssertionError('Network forbidden during Phase 5B.1 execution')
    with patch.object(socket, 'getaddrinfo', forbidden), patch.object(socket, 'create_connection', forbidden), \
            patch.object(socket.socket, 'connect', forbidden), patch.object(socket.socket, 'connect_ex', forbidden):
        yield attempts
    require(not attempts, 'A network call was attempted')


def protected_hashes(root):
    """Inventory all preceding data, analytical reports, source and existing tests."""
    paths = set(audit.frozen_hashes(root)) | set(audit.baseline_hashes(root))
    for directory, pattern in [('data/intermediate', '*'), ('reports', '*'),
                               ('src', '*.py'), ('tests', '*.py'), ('reports/sources/autumn_sale_calendar', '*')]:
        for path in (root / directory).glob(pattern):
            if path.is_file() and str(path.relative_to(root)) not in OUTPUTS and path.name not in (
                    '05_investigate_sale_coverage.py', 'test_autumn_sale_coverage.py'):
                paths.add(str(path.relative_to(root)))
    paths.add('src/autumn_sale_calendar.json')
    return {p: audit.digest(root / p) for p in sorted(paths)}


def source_hashes(root):
    paths = ['src/05_investigate_sale_coverage.py', 'tests/test_autumn_sale_coverage.py', DOC_NOTE]
    return {p: audit.digest(root / p) for p in paths if (root / p).is_file()}


def percentile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def gap_stats(values):
    available = [v for v in values if v != '' and v is not None]
    result = dict(n=len(available), missing=len(values) - len(available))
    fields = ('min', 'p10', 'p25', 'median', 'mean', 'p75', 'p90', 'p95', 'max')
    numbers = ([min(available), percentile(available, .1), percentile(available, .25),
                statistics.median(available), statistics.mean(available), percentile(available, .75),
                percentile(available, .9), percentile(available, .95), max(available)] if available else [''] * 9)
    result.update(zip(fields, numbers))
    return result


def conflicts(records):
    groups = [list(g) for _, g in groupby(records, key=lambda r: r['timestamp_utc'])]
    return [g for g in groups if len({audit.state_signature(r) for r in g}) > 1]


def nearest(records, side):
    if not records:
        return [], 'missing'
    ts = records[-1 if side == 'pre' else 0]['timestamp_utc']
    ties = [r for r in records if r['timestamp_utc'] == ts]
    state = ('ambiguous' if any(r['observation_kind'] == 'ambiguous' for r in ties)
             or len({audit.state_signature(r) for r in ties}) > 1 else ties[0]['observation_kind'])
    return ties, state


def summarize_pair(game, year, window, records, cache_info, excluded_count=0):
    """Valid record means valid timestamp/Steam shop; ambiguous deals are retained.

    Latest/earliest timestamp wins, never skip ambiguity for an older price.
    Representative raw fields use the lowest index; conflicting ties make the
    aggregate observed state ambiguous and all tied raw records remain visible.
    """
    records = sorted(records, key=lambda r: (audit.utc_stamp(r['timestamp_utc']), r['source_record_index']))
    require(all(audit.utc_stamp(r['timestamp_utc']) < CUTOFF and r['shop_id'] == 61 for r in records),
            'Out-of-scope record passed to diagnostics')
    original, _ = audit.audit_pair(game, year, window, records, cache_info)
    require(original['eligible_for_sale'], 'Phase 5B.1 input has an ineligible pair; explicit review required')
    start, end = window[2:]
    before, inside, after = audit.partition(records, start, end)
    pre, pre_state = nearest(before, 'pre')
    post, post_state = nearest(after, 'post')
    row = dict(appid=game['AppID'], name=game['Name'], sale_year=year,
               evidence_category=original['evidence_category'], sale_start_utc=audit.fmt(start),
               sale_end_utc=audit.fmt(end), release_date=game['release_date'],
               eligible_for_sale=original['eligible_for_sale'], eligibility_reason=original['eligibility_reason'],
               cache_path=original['cache_path'], cache_status=cache_info['cache_status'],
               raw_history_record_count=cache_info['raw_history_record_count'],
               analyzed_history_record_count=len(records), records_excluded_at_or_after_2026=excluded_count,
               analysis_end_exclusive_utc=audit.fmt(CUTOFF), empty_raw_history=cache_info['raw_history_record_count'] == 0,
               empty_analyzed_history=not records,
               first_observed_timestamp=records[0]['timestamp_utc'] if records else '',
               last_observed_timestamp=records[-1]['timestamp_utc'] if records else '',
               pre_observed_state=pre_state, post_observed_state=post_state,
               history_conflicting_timestamp_groups=len(conflicts(records)))
    for prefix, partition_records in [('pre', before), ('in_window', inside), ('post', after)]:
        kinds = Counter(r['observation_kind'] for r in partition_records)
        row.update({f'{prefix}_record_count': len(partition_records),
                    f'{prefix}_price_usable_count': kinds['discount'] + kinds['full_price'],
                    f'{prefix}_discount_count': kinds['discount'], f'{prefix}_full_price_count': kinds['full_price'],
                    f'{prefix}_ambiguous_count': kinds['ambiguous'],
                    f'{prefix}_null_deal_count': sum(r['deal_status'] == 'null' for r in partition_records),
                    f'{prefix}_raw_indices_json': compact([r['source_record_index'] for r in partition_records]),
                    f'{prefix}_conflicting_timestamp_groups': len(conflicts(partition_records))})
    for prefix, ties, boundary in [('pre', pre, start), ('post', post, end)]:
        representative = min(ties, key=lambda r: r['source_record_index']) if ties else None
        for field in audit.OBS_FIELDS:
            row[f'{prefix}_{field}'] = representative[field] if representative else ''
        row[f'{prefix}_nearest_raw_indices_json'] = compact([r['source_record_index'] for r in ties])
        row[f'{prefix}_nearest_records_json'] = compact(ties)
        row[f'{prefix}_nearest_conflict'] = bool(conflicts(ties))
        row[f'{prefix}_gap_days'] = abs((boundary - audit.utc_stamp(ties[0]['timestamp_utc'])).total_seconds()) / 86400 if ties else ''
    row['surrounding_interval_days'] = ((audit.utc_stamp(post[0]['timestamp_utc']) -
                                      audit.utc_stamp(pre[0]['timestamp_utc'])).total_seconds() / 86400 if pre and post else '')
    # Full sequence of observed records, plus event markers. An equal-time marker
    # precedes records only for display: the interval determines their partition.
    events = [dict(event='observed_record', relation=prefix, **r)
              for prefix, partition_records in [('pre', before), ('in_window', inside), ('post', after)]
              for r in partition_records]
    events.extend([dict(event='sale_start', timestamp_utc=audit.fmt(start)),
                   dict(event='sale_end', timestamp_utc=audit.fmt(end))])
    events.sort(key=lambda e: (audit.utc_stamp(e['timestamp_utc']), e['event'] == 'observed_record',
                               e.get('source_record_index', -1)))
    row['observed_sequence_json'] = compact(events)
    row['in_window_records_json'] = compact(inside)
    for field in ('earliest_in_window_timestamp', 'latest_in_window_timestamp',
                  'min_observed_in_window_price', 'max_observed_in_window_regular_price',
                  'max_observed_in_window_cut', 'in_window_mixed_discount_full_price'):
        row[field] = original[field]
    has_discount = row['in_window_discount_count'] > 0
    row.update(pattern_direct_in_window_discount=has_discount,
               pattern_pre_discount_no_direct_discount=pre_state == 'discount' and not has_discount,
               pattern_pre_full_price_no_direct_discount=pre_state == 'full_price' and not has_discount,
               pattern_no_unambiguous_latest_pre_state=pre_state in ('missing', 'ambiguous'),
               no_temporal_pre_record=not pre)
    reasons = []
    if pre_state == 'missing' or post_state == 'missing':
        reasons.append('missing_surrounding_observation')
    if pre_state == 'ambiguous' or post_state == 'ambiguous' or row['in_window_ambiguous_count']:
        reasons.append('ambiguous_observed_information')
    if pre and post and {audit.state_signature(r) for r in pre} != {audit.state_signature(r) for r in post}:
        reasons.append('surrounding_observed_values_differ')
    if row['history_conflicting_timestamp_groups']:
        reasons.append('same_timestamp_history_conflict')
    if 'exact release hour unavailable' in row['eligibility_reason']:
        reasons.append('release_hour_unknown')
    row['interpretation_cues'] = ';'.join(reasons)
    row['pattern_surrounding_evidence_requires_review'] = bool(reasons)
    # Differences are ordinary observed transitions, NOT proven contradictions.
    return row


def sensitivity_rows(rows):
    """Overlapping aggregate slices. No inferred negatives, threshold selection or labels."""
    non_a = [r for r in rows if r['evidence_category'] != 'A']
    results = []
    for threshold in THRESHOLDS:
        for year in ['all', 2023, 2024, 2025]:
            for category in ['all_non_A', 'B', 'C', 'D']:
                for state in STATES:
                    pool = [r for r in non_a if (year == 'all' or r['sale_year'] == year)
                            and (category == 'all_non_A' or r['evidence_category'] == category)
                            and r['pre_observed_state'] == state]
                    matches = [r for r in pool if threshold is None or
                               (r['pre_gap_days'] != '' and r['pre_gap_days'] <= threshold)]
                    result = dict(scenario='unrestricted' if threshold is None else f'pre_within_{threshold}_days',
                                  pre_recency_limit_days='' if threshold is None else threshold,
                                  sale_year=year, evidence_category=category, pre_observed_state=state,
                                  stratum_pair_count=len(pool), satisfying_recency_count=len(matches),
                                  post_observation_exists_count=sum(r['post_gap_days'] != '' for r in matches),
                                  post_observation_missing_count=sum(r['post_gap_days'] == '' for r in matches),
                                  both_sides_within_limit_count=sum(
                                      r['pre_gap_days'] != '' and r['post_gap_days'] != '' and
                                      (threshold is None or r['post_gap_days'] <= threshold) for r in matches),
                                  matching_pair_keys_json=compact([[r['appid'], r['sale_year']] for r in matches]))
                    for post_state in STATES:
                        result[f'post_{post_state}_count'] = sum(r['post_observed_state'] == post_state for r in matches)
                    result.update({f'post_gap_days_{k}': v for k, v in gap_stats([r['post_gap_days'] for r in matches]).items()})
                    results.append(result)
    return results


def grouped_gap_statistics(rows):
    results = []
    axis_values = {'sale_year': ('2023', '2024', '2025'), 'evidence_category': tuple('ABCD'),
                   'pre_observed_state': STATES, 'post_observed_state': STATES}
    for axis in ('sale_year', 'evidence_category', 'pre_observed_state', 'post_observed_state'):
        for value in axis_values[axis]:
            subset = [r for r in rows if str(r[axis]) == value]
            for gap in ('pre_gap_days', 'post_gap_days', 'surrounding_interval_days'):
                results.append(dict(group_axis=axis, group_value=value, metric=gap,
                                    **gap_stats([r[gap] for r in subset])))
    # Cross-tabs allow year-specific gap assessment within categories/states.
    for year in (2023, 2024, 2025):
        for axis in ('evidence_category', 'pre_observed_state', 'post_observed_state'):
            for value in axis_values[axis]:
                subset = [r for r in rows if r['sale_year'] == year and str(r[axis]) == value]
                for gap in ('pre_gap_days', 'post_gap_days', 'surrounding_interval_days'):
                    results.append(dict(group_axis=f'{year}:{axis}', group_value=value, metric=gap,
                                        **gap_stats([r[gap] for r in subset])))
    return results


def validate(rows, sensitivity, histories, original_rows, original_records, windows):
    expected = {(r['AppID'], int(r['sale_year'])) for r in original_rows}
    keys = {(r['appid'], r['sale_year']) for r in rows}
    require(len(keys) == len(rows) == 300 and keys == expected, 'Pair inventory must match all 300 Phase 5A.1 pairs')
    old = {(r['AppID'], int(r['sale_year'])): r for r in original_rows}
    old_records = {(r['AppID'], int(r['sale_year']), int(r['source_record_index'])): r for r in original_records}
    new_records = {}
    for row in rows:
        key = (row['appid'], row['sale_year'])
        require(row['evidence_category'] == old[key]['evidence_category'], 'Phase 5A.1 category changed')
        require(row['sale_start_utc'] == old[key]['window_start_utc'] and
                row['sale_end_utc'] == old[key]['window_end_exclusive_utc'], 'Event boundary mismatch')
        partitions = audit.partition(histories[row['appid']], *windows[row['sale_year']][2:])
        for prefix, records in zip(('pre', 'in_window', 'post'), partitions):
            require(row[f'{prefix}_record_count'] == len(records), 'Partition count mismatch')
            require(json.loads(row[f'{prefix}_raw_indices_json']) == [r['source_record_index'] for r in records],
                    'Partition provenance mismatch')
            require(row[f'{prefix}_conflicting_timestamp_groups'] == len(conflicts(records)), 'Conflict mismatch')
        inside = partitions[1]
        require(row['evidence_category'] == audit.category(inside), 'Category/raw mismatch')
        for r in inside:
            new_records[(*key, r['source_record_index'])] = r
        for prefix, records in [('pre', partitions[0]), ('post', partitions[2])]:
            ties, state = nearest(records, prefix)
            require(row[f'{prefix}_observed_state'] == state and
                    json.loads(row[f'{prefix}_nearest_records_json']) == ties, 'Nearest observation mismatch')
            if not ties:
                require(row[f'{prefix}_gap_days'] == row[f'{prefix}_timestamp_utc'] == row[f'{prefix}_price'] == '',
                        'Missing context was fabricated')
        require(row['pre_record_count'] + row['in_window_record_count'] + row['post_record_count'] ==
                len(histories[row['appid']]), 'Partition total mismatch')
        direct_discount = any(r['observation_kind'] == 'discount' for r in inside)
        require(row['pattern_direct_in_window_discount'] == direct_discount, 'Diagnostic pattern mismatch')
        require(row['pattern_pre_discount_no_direct_discount'] ==
                (row['pre_observed_state'] == 'discount' and not direct_discount), 'Pre-discount pattern mismatch')
        require(row['pattern_pre_full_price_no_direct_discount'] ==
                (row['pre_observed_state'] == 'full_price' and not direct_discount), 'Pre-full-price pattern mismatch')
        require(row['pattern_no_unambiguous_latest_pre_state'] ==
                (row['pre_observed_state'] in ('missing', 'ambiguous')), 'Unavailable-state pattern mismatch')
        for prefix, part, boundary in [('pre', partitions[0], windows[row['sale_year']][2]),
                                        ('post', partitions[2], windows[row['sale_year']][3])]:
            expected_gap = (abs((boundary - audit.utc_stamp(part[-1 if prefix == 'pre' else 0]['timestamp_utc']))
                                .total_seconds()) / 86400 if part else '')
            require(row[f'{prefix}_gap_days'] == expected_gap, 'Gap calculation mismatch')
        interval = ((audit.utc_stamp(partitions[2][0]['timestamp_utc']) -
                     audit.utc_stamp(partitions[0][-1]['timestamp_utc'])).total_seconds() / 86400
                    if partitions[0] and partitions[2] else '')
        require(row['surrounding_interval_days'] == interval, 'Surrounding interval mismatch')
        sequence = json.loads(row['observed_sequence_json'])
        observations = [e for e in sequence if e['event'] == 'observed_record']
        require([e['source_record_index'] for e in observations] ==
                [r['source_record_index'] for r in histories[row['appid']]], 'Chronology provenance mismatch')
        require(all(r['shop_id'] == 61 and audit.utc_stamp(r['timestamp_utc']) < CUTOFF
                    for r in histories[row['appid']]), 'Non-Steam or 2026 record')
    require(new_records.keys() == old_records.keys(), 'In-window record inventory changed')
    for key, r in new_records.items():
        require(json.loads(r['raw_record_json']) == json.loads(old_records[key]['raw_record_json']),
                'In-window raw provenance changed')
    require(len(sensitivity) == 384, 'Sensitivity cell inventory mismatch')
    non_a = { (r['appid'], r['sale_year']): r for r in rows if r['evidence_category'] != 'A' }
    for cell in sensitivity:
        members = [non_a[tuple(key)] for key in json.loads(cell['matching_pair_keys_json'])]
        limit = cell['pre_recency_limit_days']
        pool = [r for r in non_a.values() if r['pre_observed_state'] == cell['pre_observed_state']
                and cell['sale_year'] in ('all', r['sale_year'])
                and cell['evidence_category'] in ('all_non_A', r['evidence_category'])]
        expected_members = [r for r in pool if limit == '' or
                            (r['pre_gap_days'] != '' and r['pre_gap_days'] <= limit)]
        require(members == expected_members and cell['satisfying_recency_count'] == len(members)
                and cell['stratum_pair_count'] == len(pool), 'Sensitivity membership/count mismatch')
        post_available = sum(r['post_record_count'] > 0 for r in members)
        require(cell['post_observation_exists_count'] == post_available and
                cell['post_observation_missing_count'] == len(members) - post_available, 'Sensitivity post counts mismatch')
        for state in STATES:
            require(cell[f'post_{state}_count'] == sum(r['post_observed_state'] == state for r in members),
                    'Sensitivity post-state mismatch')
        require(cell['both_sides_within_limit_count'] == sum(
                    r['pre_record_count'] > 0 and r['post_record_count'] > 0 and
                    (limit == '' or r['post_gap_days'] <= limit) for r in members), 'Two-sided scenario mismatch')
        require({k: cell[f'post_gap_days_{k}'] for k in gap_stats([])} ==
                gap_stats([r['post_gap_days'] for r in members]), 'Sensitivity gap statistics mismatch')
    require(not {'target', 'label', 'discounted'} & set(rows[0]), 'Final label column generated')
    return dict(unique_pairs=True, all_expected_years=True, exact_boundaries=True, temporal_partitions=True,
                nearest_observations=True, missing_and_ambiguous_preserved=True, conflicts_detected=True,
                gap_calculations=True, diagnostic_patterns=True, chronological_raw_provenance=True,
                categories_and_in_window_raw_records_unchanged=True, sensitivity_reconciled=True,
                no_final_label_columns=True, no_2026_observations=True)


def display(value):
    return 'missing' if value == '' or value is None else round(value, 6) if isinstance(value, float) else value


def state_table(rows, side, by_category=False):
    groups = (('all', rows),) + tuple((y, [r for r in rows if r['sale_year'] == y]) for y in (2023, 2024, 2025))
    if by_category:
        groups = tuple((c, [r for r in rows if r['evidence_category'] == c]) for c in 'ABCD')
    return audit.md_table(['Category' if by_category else 'Year', 'Pairs', 'Full price', 'Discounted', 'Ambiguous', 'Missing'],
                          [(group, len(subset), *[sum(r[f'{side}_observed_state'] == s for r in subset) for s in STATES])
                           for group, subset in groups])


def case_report(row, description):
    evidence = []
    for side in ('pre', 'in_window', 'post'):
        records = json.loads(row[f'{side}_nearest_records_json' if side != 'in_window' else 'in_window_records_json'])
        for r in records:
            evidence.append([side, r['source_record_index'], r['timestamp_utc'], r['price'], r['regular_price'],
                             r['cut'], r['price_currency'], r['observation_kind']])
    return '\n'.join([f"### {description}: {row['name']} ({row['appid']}), {row['sale_year']} — {row['evidence_category']}", '',
                       f"Pre/post observed states: {row['pre_observed_state']} / {row['post_observed_state']}. "
                       f"Pre/post gaps: {display(row['pre_gap_days'])} / {display(row['post_gap_days'])} days. "
                       f"Surrounding interval: {display(row['surrounding_interval_days'])} days. "
                       f"Observed counts pre/in/post: {row['pre_record_count']}/{row['in_window_record_count']}/{row['post_record_count']}.", '',
                       audit.md_table(['Relation', 'Raw index', 'UTC timestamp', 'Price', 'Regular', 'Cut', 'Currency', 'Kind'], evidence), '',
                       'Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.', ''])


def build_report(rows, sensitivity, histories, receipt, calendar, doc):
    counts, transitions, gaps, repeats, conflict_examples, full_changes = audit.empirical_semantics(histories)
    lines = ['# Autumn Sale Historical Price-State and Coverage Investigation — Phase 5B.1', '',
             '## A. Research objective', '',
             '> Given information available about a Steam game before a specific Steam Autumn Sale begins, '
             'what is the probability that the game will be discounted during that sale?', '',
             'This investigation measures observed surrounding prices and missing evidence before designing final labels. '
             '**OBSERVED FACTS** are timestamps and returned fields. **DIAGNOSTIC INTERPRETATIONS** flag uncertainty. '
             '**HYPOTHETICAL ASSUMPTIONS** appear only in sensitivity scenarios. No persistent price states, '
             'daily histories, final 1/0/UNKNOWN labels, modeling features or models are produced.', '',
             '## B. Input datasets and provenance', '',
             'Inputs are the frozen 100-game pilot, Phase 4 collection manifest and cached `data/raw/itad/<AppID>.json` '
             'wrappers, plus the unchanged Phase 5A.1 audit/record CSVs and verified centralized event calendar. '
             'The Phase 5A calendar-date baseline is verified against its preserved manifest before execution. '
             'The existing Phase 5A.1 parser is reused without changing its price, cut, currency, null-deal or provenance rules.', '',
             f"The cache contains **{receipt['raw_records']} records**. To exclude 2026 from this investigation, "
             f"**{receipt['excluded_2026_records']} observations at or after 2026-01-01T00:00:00Z are excluded**, leaving "
             f"**{receipt['analyzed_records']} timestamp-usable Steam records**. Exclusion is by timestamp, without analyzing "
             'their prices. Thus post-sale context can differ from the previous audit, which searched the whole cache. '
             'A missing post-sale observation means none was returned before this cutoff; it does not establish absence after it. '
             'The cutoff is an experimental scope restriction, not a coverage threshold.', '',
             'A valid temporal observation has a parsed timezone-aware timestamp and integer Steam shop ID 61. '
             'Ambiguous/null deals remain temporal observations; `price_usable_count` separately counts discount/full-price records. '
             'Cached HTTP response text, wrapper configuration and manifest counts are verified. Invalid caches/parsing failures '
             'stop this investigation rather than becoming D.', '',
             '## C. Event windows and eligibility', '',
             'The unchanged Phase 5A.1 calendar uses **start <= timestamp < end**. A record exactly at end is post-sale. '
             'No new event-time verification or calendar changes are made here.', '',
             audit.md_table(['Year', 'UTC start', 'UTC end', 'Pacific start', 'Pacific end', 'Official source'],
                            [(e['sale_year'], e['sale_start_utc'], e['sale_end_utc'], e['sale_start_pacific'],
                              e['sale_end_pacific'], f"[Valve announcement]({e['source_url']})") for e in calendar['events']]), '',
             '**300 unique pairs** (100 games × 2023/2024/2025); all 300 meet the existing date-level eligibility rule; '
             'zero ineligible pairs. nekowater’s 2023 same-day release has unresolved hour precision. '
             'Only pre-2026 historical observations are examined. Intended experiments remain 2023–2024 training, '
             '2025 validation, 2026 retrospective evaluation; no 2026 outcomes enter development.', '',
             '## D. Coverage summary for all 300 pairs', '',
             audit.md_table(['Year', 'A', 'B', 'C', 'D', 'In-window records', 'Pre exists', 'Post exists', 'Both exist'],
                            [(y, *[sum(r['sale_year'] == y and r['evidence_category'] == c for r in rows) for c in 'ABCD'],
                              sum(r['in_window_record_count'] for r in rows if r['sale_year'] == y),
                              sum(r['pre_gap_days'] != '' for r in rows if r['sale_year'] == y),
                              sum(r['post_gap_days'] != '' for r in rows if r['sale_year'] == y),
                              sum(r['pre_gap_days'] != '' and r['post_gap_days'] != '' for r in rows if r['sale_year'] == y))
                             for y in (2023, 2024, 2025)]), '',
             'Categories remain A=direct discount; B=only full-price in-window observations; '
             'C=ambiguous in-window evidence without a discount; D=no in-window observations. '
             '**175 A, 3 B, 0 C, 122 D; 178 in-window records**, each observed pair has one record. '
             'These are unchanged descriptive categories, not target labels. No null/ambiguous or mixed in-window records occur.', '',
             f"Empty raw histories: {receipt['empty_history_games']} games; "
             f"{sum(r['empty_analyzed_history'] for r in rows)} pairs have no analyzed observations. "
             f"Missing pre: {sum(r['pre_observed_state'] == 'missing' for r in rows)} pairs; "
             f"missing post before cutoff: {sum(r['post_observed_state'] == 'missing' for r in rows)} pairs.", '',
             audit.md_table(['Overlapping diagnostic pattern', 'Pairs'],
                            [(k, sum(r[k] for r in rows)) for k in (
                                'pattern_direct_in_window_discount', 'pattern_pre_discount_no_direct_discount',
                                'pattern_pre_full_price_no_direct_discount', 'pattern_no_unambiguous_latest_pre_state',
                                'pattern_surrounding_evidence_requires_review')]), '',
             'Patterns overlap. The review cue covers missing/ambiguous surrounding observations, differing observed '
             'surrounding values, history conflicts or unknown release hour. A value change is not a proven contradiction '
             'and missing evidence is not a discount-state finding.', '',
             '## E. Pre-sale observed-state distributions', '', state_table(rows, 'pre'), '',
             state_table(rows, 'pre', True), '',
             '“Latest observed state” refers only to the last pre-sale timestamp, not the state at sale start. '
             'The pipeline never skips a latest null/ambiguous record to select an older known price. '
             'Divergent nearest same-time records make the aggregated state ambiguous even if both have cut=0. '
             'The lowest raw index supplies explicitly representative fields; all ties remain serialized. '
             'A conflict is more than one signature at the same timestamp: price amount/amountInt/currency, '
             'regular amount/amountInt/currency, cut and deal status define that signature. '
             'Different raw metadata outside these fields alone does not constitute a price-state conflict.', '',
             '## F. Post-sale observed-state distributions', '', state_table(rows, 'post'), '',
             state_table(rows, 'post', True), '',
             'Earliest post evidence is at or after exact end and strictly before 2026. It describes that timestamp only. '
             'No post-sale observation retroactively establishes an in-sale state.', '',
             '## G. Observation-gap statistics', '',
             'Gaps use exact elapsed seconds / 86,400, not rounded calendar days. Missing gaps remain empty CSV cells '
             'and count as missing, never zero. Surrounding interval = post timestamp − pre timestamp, when both exist; '
             'for A/B this interval may contain observations and must not be mistaken for an observation-free gap. '
             'For D it spans the whole event without a returned observation. Percentiles use linear interpolation '
             'at (n−1) × percentile. All statistics below are days.', '']
    stats_headers = ['Group', 'Metric', 'N', 'Missing', 'Min', 'P10', 'P25', 'Median', 'Mean', 'P75', 'P90', 'P95', 'Max']
    stats_rows = lambda selection: [(f"{s['group_axis']}={s['group_value']}", s['metric'],
                                     *[display(s[k]) for k in ('n', 'missing', 'min', 'p10', 'p25', 'median',
                                                              'mean', 'p75', 'p90', 'p95', 'max')]) for s in selection]
    gaps_summary = receipt['gap_statistics']
    lines += [audit.md_table(stats_headers, stats_rows([s for s in gaps_summary if ':' not in s['group_axis']])), '',
              '<details>', '<summary>Year × evidence category / pre-state / post-state gap distributions</summary>', '',
              audit.md_table(stats_headers, stats_rows([s for s in gaps_summary if ':' in s['group_axis']])), '', '</details>', '',
              'Counts of historical observations before and after each sale, full observed chronology, raw indices, '
              'nearest raw fields, price summaries and conflicting groups are in '
              '[the pair-level diagnostics](../data/intermediate/autumn_sale_coverage_diagnostics.csv). '
              'Long gaps leave broad intervals without direct observations. Neither large nor small gaps alone '
              'demonstrate completeness; no gap cutoff is adopted.', '',
              '## H. Detailed Category B and D analysis', '',
              'All three B pairs follow. One full-price record proves only that observed timestamp, not that '
              'the whole event was undiscounted. Two B pairs have a pre-sale discount; one has no pre-sale observation.', '']
    for row in rows:
        if row['evidence_category'] == 'B':
            lines.append(case_report(row, 'Every Category B case'))
    lines += ['HOPE LEFT ME: the cache stops at the in-window full-price observation; no post-sale price is available. '
              'Hentai Beauty: a pre-sale discount precedes the one in-window full-price record and a later discount. '
              'nekowater: release date equals sale-start date; the observed full price at 22:39:17Z is after sale start, '
              'but release availability at 18:00:00Z is unverified. A later full-price record has a lower regular price, '
              'showing that cut=0 alone does not mean an unchanged base price.', '',
              'D pairs by year and latest pre-sale state:', '',
              audit.md_table(['Year', 'Full price', 'Discounted', 'Ambiguous', 'Missing'],
                             [(y, *[sum(r['sale_year'] == y and r['evidence_category'] == 'D' and
                                       r['pre_observed_state'] == s for r in rows) for s in STATES])
                              for y in (2023, 2024, 2025)]), '',
              'The sensitivity section quantifies recency for every D pair. There is no direct in-window observation '
              'to resolve any D pair regardless of whether surrounding values agree.', '',
              '## I. ITAD history-semantics assessment', '',
              f"Official [History endpoint documentation]({doc['documentation_url']}) and "
              f"[official OpenAPI schema]({doc['openapi_url']}) were reviewed on {doc['reviewed_on']} "
              f"(documented API {doc['api_documentation_version']}). The endpoint returns a historical price log; "
              f"its `since` parameter says “{doc['since_description_quote']}” "
              'The schema allows null deals. A local [documentation evidence note](sources/itad_history_semantics.json) '
              'records review scope. The diagnostic pipeline reads it offline.', '',
              audit.md_table(['Claim', 'Supporting evidence', 'Counterevidence / limitation', 'Assessment'], [
                  ('1. Returns historical records', 'Official endpoint and schema; timestamped cached response arrays',
                   'A history array does not define coverage quality', 'Supported'),
                  ('2. Change-oriented', 'Official since description explicitly refers to price changes; observed transitions dominate',
                   'Repeated states, tied conflicts and requested-since observations do occur', 'Supported orientation; not a strict unique-change log'),
                  ('3. Captures every Steam change', 'No completeness guarantee found in reviewed materials',
                   'Gaps cannot establish completeness or prove that specific changes were omitted', 'Unresolved; not established'),
                  ('4. Safe persistence until next record', 'Would require additional capture/timestamp/state assumptions',
                   'No such guarantee found; ambiguous/conflicting and potentially initialized records complicate reconstruction',
                   'Unresolved; never applied here')]), '',
              '**Observed facts (pre-2026 records only):**', '',
              audit.md_table(['Measure', 'Count'], sorted(counts.items())), '',
              audit.md_table(['From observed state', 'To observed state', 'Singleton consecutive pairs'],
                             [(a, b, n) for (a, b), n in sorted(transitions.items())]), '',
              audit.md_table(['Consecutive distinct timestamp gap (days)', *gap_stats(gaps).keys()],
                             [('All analyzed histories', *[display(v) for v in gap_stats(gaps).values()])]), '',
              f"Of {counts['singleton_adjacent_pairs']} adjacent singleton timestamp pairs, "
              f"{transitions[('discount', 'full_price')] + transitions[('full_price', 'discount')]} alternate "
              f"between discounted and full-price observations. There are {counts['consecutive_cut_zero']} consecutive "
              f"cut=0 pairs, with {counts['identical_full_price_pairs']} identical full-price signatures. "
              'These analyzed observations do not show regular unchanged full-price polling. '
              'Directional counts exclude tied groups rather than arbitrarily ordering conflicting states. '
              'Consecutive identical states contradict a strict “every record is a unique changed price” interpretation, '
              'but do not disprove change-oriented collection. Consecutive cut=0 records can reflect changed regular prices. '
              'Requested-since timestamps could be initialized snapshots; their origin is an interpretation, not established fact. '
              'No polling schedule, perfect coverage, price-duration guarantee or null-deal sale meaning is inferred.', '',
              '## J. Hypothetical coverage sensitivity scenarios', '',
              '**HYPOTHETICAL ASSUMPTION:** a pre-sale observation within each listed elapsed-day limit is available for '
              'possible later methodological review. This is a recency test, not a negative-label rule. '
              'Only 125 non-A pairs enter these scenarios. States remain separate; discounted pre-state counts are '
              'not combined with full-price counts as potential negatives. Missing and ambiguous states remain separate.', '',
              'Unrestricted imposes no recency filter, so missing-pre pairs appear as a separate availability bucket; '
              'finite limits cannot be satisfied without a pre timestamp. Optional two-sided counts require a post timestamp '
              'within the same limit as well (unrestricted requires both timestamps). Neither condition establishes coverage. '
              'CSV aggregate rows overlap across year/category slices; do not sum “all” rows with their component rows.', '',
              audit.md_table(['Scenario', 'Year', 'Pre full price', 'Pre discounted', 'Pre ambiguous', 'Pre missing'],
                             [(scenario, y, *[next(r['satisfying_recency_count'] for r in sensitivity
                                                  if r['scenario'] == scenario and r['sale_year'] == y
                                                  and r['evidence_category'] == 'all_non_A' and r['pre_observed_state'] == s)
                                             for s in STATES])
                              for scenario in dict.fromkeys(r['scenario'] for r in sensitivity)
                              for y in ('all', 2023, 2024, 2025)]), '',
              'Post evidence and its gap distributions, keeping pre states separate:', '',
              audit.md_table(['Scenario', 'Pre state', 'Meets recency', 'Post exists', 'Post missing', 'Both within limit',
                              'Post gap min', 'Median', 'Mean', 'P90', 'Max'],
                             [(r['scenario'], r['pre_observed_state'], r['satisfying_recency_count'],
                               r['post_observation_exists_count'], r['post_observation_missing_count'],
                               r['both_sides_within_limit_count'], *[display(r[f'post_gap_days_{k}'])
                                                                      for k in ('min', 'median', 'mean', 'p90', 'max')])
                              for r in sensitivity if r['sale_year'] == 'all' and r['evidence_category'] == 'all_non_A']), '',
              '<details>', '<summary>B/C/D scenario breakdown by pre state</summary>', '',
              audit.md_table(['Scenario', 'Category', 'Pre state', 'Stratum pairs', 'Meets recency', 'Post exists', 'Post missing'],
                             [(r['scenario'], r['evidence_category'], r['pre_observed_state'], r['stratum_pair_count'],
                               r['satisfying_recency_count'], r['post_observation_exists_count'], r['post_observation_missing_count'])
                              for r in sensitivity if r['sale_year'] == 'all' and r['evidence_category'] != 'all_non_A']), '',
              '</details>', '',
              'The [sensitivity CSV](../data/intermediate/autumn_sale_coverage_sensitivity.csv) includes all 384 '
              'scenario/year/category/pre-state cells, zero-count strata, post-state counts, missing counts, '
              'full post-gap percentiles and matching pair keys. No optimum threshold is selected.', '',
              '## K. Special-case investigations', '']
    d_rows = [r for r in rows if r['evidence_category'] == 'D']
    selections = []
    for state in ('discount', 'full_price'):
        candidates = [r for r in d_rows if r['pre_observed_state'] == state]
        if candidates:
            selections.append((min(candidates, key=lambda r: r['pre_gap_days']), f'D with recent pre-sale {state} evidence'))
    missing = [r for r in d_rows if r['pre_observed_state'] == 'missing']
    if missing:
        selections.append((missing[0], 'D without pre-sale evidence'))
        lines += ['All D pairs without pre-sale observations:', '',
                  audit.md_table(['AppID', 'Name', 'Year', 'Analyzed records', 'Post state'],
                                 [(r['appid'], r['name'], r['sale_year'], r['analyzed_history_record_count'],
                                   r['post_observed_state']) for r in missing]), '']
    available_pre = [r for r in d_rows if r['pre_gap_days'] != '']
    if available_pre:
        selections.append((max(available_pre, key=lambda r: r['pre_gap_days']),
                           'D with the longest pre-sale gap (ranking, no cutoff)'))
    longest = sorted([r for r in d_rows if r['surrounding_interval_days'] != ''],
                     key=lambda r: r['surrounding_interval_days'], reverse=True)[:3]
    selections.extend((r, 'D with one of the longest observed surrounding intervals') for r in longest)
    nearest_end = [r for r in d_rows if r['pre_observed_state'] == 'discount' and r['post_observed_state'] == 'full_price']
    if nearest_end:
        selections.append((min(nearest_end, key=lambda r: r['post_gap_days']), 'Possible discount end near boundary (unproven in-window persistence)'))
    selected_a = [r for r in rows if r['evidence_category'] == 'A' and r['pre_observed_state'] != 'full_price']
    selections.extend((r, 'A with an already-discounted pre-sale observation') for r in selected_a)
    for r, why in selections:
        lines.append(case_report(r, why))
    lines += ['An early post-sale full price following a pre-sale discount is consistent with a discount ending '
              'near the boundary, but cannot establish when it began/ended or its persistence inside the event. '
              'A pairs directly establish an observed discount; an already-discounted pre-state does not establish '
              'a sale-triggered change or formal Valve event enrollment.', '',
              '### Every conflicting same-timestamp group', '',
              audit.md_table(['AppID', 'Name', 'Raw index', 'UTC timestamp', 'Price', 'Regular', 'Cut', 'Kind'],
                             [(appid, next(r['name'] for r in rows if r['appid'] == appid),
                               r['source_record_index'], r['timestamp_utc'], r['price'], r['regular_price'],
                               r['cut'], r['observation_kind']) for appid, group in conflict_examples for r in group]), '',
              'Tied conflicts are retained, not deduplicated or ordered as simultaneous start/end transitions. '
              'Zero price with zero regular and cut=0 remains the existing parser’s full-price observation; '
              'this arithmetic classification does not establish free-game status or what Steam offered throughout an interval.', '',
              '### Repeated consecutive states and full-price changes', '',
              audit.md_table(['Pattern', 'AppID', 'Raw index', 'UTC timestamp', 'Price', 'Regular', 'Cut'],
                             [('Identical state across adjacent timestamp groups', appid, r['source_record_index'],
                               r['timestamp_utc'], r['price'], r['regular_price'], r['cut'])
                              for appid, group in repeats for r in group] +
                             [('Full price with changed values', appid, r['source_record_index'], r['timestamp_utc'],
                               r['price'], r['regular_price'], r['cut']) for appid, group in full_changes[:3] for r in group]), '',
              'No observed null/ambiguous deal records occur in this pilot’s analyzed histories. Synthetic tests '
              'retain such records without assigning full price. Same-timestamp price conflicts are distinct from '
              'a malformed/null individual deal.', '',
              '## L. Implications for negative-label feasibility', '',
              '**DIAGNOSTIC INTERPRETATION:** direct discounted observations exist for 175 pairs. The other 125 '
              'pairs have varying surrounding evidence, including pre-sale discounts and completely absent histories. '
              'Recent full-price evidence only establishes an earlier observation. Even equal full prices on both '
              'sides do not exclude an unobserved intervening discount. B’s one in-window full-price timestamp also '
              'does not prove absence of a discount elsewhere in the event. Coverage and state persistence require '
              'independent justification before any final negative label. Convenient class balance supplies none.', '',
              '## M. Unresolved methodological questions', '',
              '- What capture/completeness evidence would justify any price-state reconstruction?',
              '- How should polling latency, corrections, same-time variants and initialized records be treated?',
              '- What event-wide evidence can support absence of a discount, beyond a single full-price timestamp?',
              '- Can surrounding observations contribute to coverage, and under which independently justified assumptions?',
              '- How should missing/ambiguous records, long gaps, censoring and unknown release hours affect later UNKNOWN decisions?',
              '- Which metadata can be verified as available before each event, without leakage?', '',
              'No threshold, persistence policy or labeling rule is finalized. Formal Valve enrollment remains outside '
              'the observed-discount target. The diversity pilot is diagnostic, not a population-representative sample.', '',
              '## N. Validation and reproducibility results', '',
              'Run `python3 src/05_investigate_sale_coverage.py --verify` to execute the full offline test suite '
              'and repeated complete diagnostics under a socket/DNS prohibition. '
              'A normal run reads only local files and reuses execution checks only if source and protected-input '
              'fingerprints match. No credentials or extra dependencies beyond the standard library are needed.', '',
              audit.md_table(['Check', 'Result'], [(k, v) for k, v in receipt['checks'].items()]), '',
              audit.md_table(['Execution check', 'Result'], [(k, v) for k, v in sorted(receipt['execution_checks'].items())
                                                           if k not in ('source_sha256', 'protected_sha256')]), '',
              f"Before/after SHA-256 inventories match for **{len(receipt['protected_before_sha256'])} protected prior-phase files**, "
              f"including **{len(receipt['frozen_phase4_before_sha256'])} frozen Phase 4 inputs**. "
              'Both inventories and output hashes are in [the validation receipt](autumn_sale_coverage_validation.json). '
              'Phase 5A/5A.1 outputs, original baseline and all raw caches remain unchanged. '
              'Saved CSVs are parsed back and reconciled to generated diagnostics; sensitivity subsets reconcile '
              'to pair-level raw indices. Missing values use empty CSV cells, not zero; JSON arrays use `[]`.', '',
              '**Zero diagnostic network attempts or requests; zero ITAD/pricing API calls; zero new histories.** '
              'Documentation-only research was separate from diagnostic execution; web-tool underlying HTTP totals '
              'are unavailable. No claims of a total external HTTP request count are made.', '',
              '**STOP: Phase 5B.1 completed pending human review. Phase 5B.2 has not started. '
              'No final labels, features or trained models exist.**', '']
    return '\n'.join(lines)


def run(root=ROOT, execution_checks=None):
    root = Path(root)
    with offline_guard() as network_attempts:
        before = protected_hashes(root)
        frozen_before = audit.frozen_hashes(root)
        audit.verify_baseline(root)
        calendar = audit.calendar_data(root)
        windows = audit.canonical_windows(root)
        require(set(windows) == {2023, 2024, 2025}, 'Unexpected event years')
        games = audit.read_csv(root / 'data/intermediate/pilot_games.csv')
        require(len(games) == len({g['AppID'] for g in games}) == 100, 'Expected 100 unique pilot games')
        manifest = {r['AppID']: r for r in audit.read_csv(root / 'data/intermediate/itad_collection_manifest.csv')}
        original_rows = audit.read_csv(root / 'data/intermediate/autumn_sale_evidence_audit.csv')
        original_records = audit.read_csv(root / 'data/intermediate/autumn_sale_evidence_records.csv')
        doc = json.loads((root / DOC_NOTE).read_text(encoding='utf-8'))
        histories, rows = {}, []
        raw_total = excluded_total = empty_games = 0
        for game in games:
            all_records, info = audit.load_cache(root, game, manifest[game['AppID']])
            require(info['cache_status'] == 'ok', f"Invalid cache or parsing failure: {game['AppID']} {info}")
            require(info['non_steam_records_excluded'] == 0, 'Unexpected non-Steam input; review required')
            records = [r for r in all_records if audit.utc_stamp(r['timestamp_utc']) < CUTOFF]
            excluded = len(all_records) - len(records)
            raw_total += info['raw_history_record_count']
            excluded_total += excluded
            empty_games += info['raw_history_record_count'] == 0
            histories[game['AppID']] = records
            for year, window in windows.items():
                rows.append(summarize_pair(game, year, window, records, info, excluded))
        sensitivity = sensitivity_rows(rows)
        checks = validate(rows, sensitivity, histories, original_rows, original_records, windows)
        sources = source_hashes(root)
        if execution_checks is None:
            prior = json.loads((root / RECEIPT).read_text()) if (root / RECEIPT).exists() else {}
            candidate = prior.get('execution_checks', {})
            execution_checks = candidate if candidate.get('source_sha256') == sources and candidate.get('protected_sha256') == before else {
                'full_offline_test_suite': 'NOT RUN for this fingerprint; use --verify',
                'deterministic_full_runs': 'NOT RUN for this fingerprint; use --verify',
                'source_sha256': sources, 'protected_sha256': before}
        require(execution_checks['source_sha256'] == sources and execution_checks['protected_sha256'] == before,
                'Execution verification fingerprint mismatch')
        audit.write_csv(root / DIAGNOSTICS, rows, list(rows[0]))
        audit.write_csv(root / SENSITIVITY, sensitivity, list(sensitivity[0]))
        # Verify every saved field, including all raw serialized sequences.
        for path, values in [(DIAGNOSTICS, rows), (SENSITIVITY, sensitivity)]:
            require(audit.read_csv(root / path) == [{k: str(v) for k, v in r.items()} for r in values],
                    f'Saved CSV round-trip mismatch: {path}')
        after = protected_hashes(root)
        require(before == after, 'Prior-phase input or artifact changed')
        checks.update(saved_csv_round_trip=True, prior_artifacts_hashes_unchanged=True,
                      phase4_hashes_unchanged=frozen_before == audit.frozen_hashes(root),
                      preserved_baseline_verified=True, diagnostic_network_attempts=len(network_attempts),
                      itad_pricing_api_requests=0, new_histories=0)
        receipt = dict(phase='5B.1', status='diagnostics_complete_pending_human_review',
                       game_sale_pairs=len(rows), pilot_games=len(games), years=list(windows),
                       raw_records=raw_total, analyzed_records=sum(len(h) for h in histories.values()),
                       excluded_2026_records=excluded_total, analysis_end_exclusive_utc=audit.fmt(CUTOFF),
                       empty_history_games=empty_games, eligible_pairs=sum(r['eligible_for_sale'] for r in rows),
                       categories_by_year={str(y): {c: sum(r['sale_year'] == y and r['evidence_category'] == c for r in rows)
                                                    for c in 'ABCD'} for y in windows},
                       pre_states_by_category={c: {s: sum(r['evidence_category'] == c and r['pre_observed_state'] == s for r in rows)
                                                   for s in STATES} for c in 'ABCD'},
                       post_states_by_category={c: {s: sum(r['evidence_category'] == c and r['post_observed_state'] == s for r in rows)
                                                    for s in STATES} for c in 'ABCD'},
                       checks=checks, execution_checks=execution_checks,
                       gap_statistics=grouped_gap_statistics(rows),
                       history_semantics_counts=dict(audit.empirical_semantics(histories)[0]),
                       frozen_phase4_before_sha256=frozen_before,
                       frozen_phase4_after_sha256=audit.frozen_hashes(root),
                       protected_before_sha256=before, protected_after_sha256=after,
                       source_sha256=sources, documentation_research=doc,
                       output_sha256={p: audit.digest(root / p) for p in (DIAGNOSTICS, SENSITIVITY)})
        (root / REPORT).write_text(build_report(rows, sensitivity, histories, receipt, calendar, doc), encoding='utf-8')
        receipt['output_sha256'][REPORT] = audit.digest(root / REPORT)
        (root / RECEIPT).write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
        require(before == protected_hashes(root), 'Prior artifacts changed during report generation')
    return rows, sensitivity, receipt


def verify_execution(root=ROOT):
    """Verify whole runs, including all four output files; no timestamp in receipts."""
    root = Path(root)
    before = protected_hashes(root)
    with offline_guard():
        stream = io.StringIO()
        suite = unittest.defaultTestLoader.discover(str(root / 'tests'), pattern='test_*.py')
        result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
        print(stream.getvalue(), end='')
        require(result.wasSuccessful(), 'Offline tests failed')
        require(before == protected_hashes(root), 'Tests changed protected inputs')
        sources = source_hashes(root)
        provisional = dict(full_offline_test_suite='PASS', tests_run=result.testsRun,
                           failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
                           deterministic_full_runs='PENDING', network_requests=0,
                           source_sha256=sources, protected_sha256=before)
        run(root, provisional)
        first = {p: (root / p).read_bytes() for p in OUTPUTS}
        run(root, provisional)
        require(first == {p: (root / p).read_bytes() for p in OUTPUTS}, 'Repeated full execution differs')
        verified = dict(provisional, deterministic_full_runs='PASS: all four outputs identical in two complete runs')
        run(root, verified)
        final = {p: (root / p).read_bytes() for p in OUTPUTS}
        rows, sensitivity, receipt = run(root, verified)
        require(final == {p: (root / p).read_bytes() for p in OUTPUTS}, 'Verified receipt rerun differs')
        require(before == protected_hashes(root), 'Protected inputs changed during repeated execution')
    print(f"Phase 5B.1: {len(rows)} unique pairs; {len(sensitivity)} sensitivity cells; verification PASS.")
    return rows, sensitivity, receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Run the full offline suite and verify deterministic full executions')
    args = parser.parse_args()
    if args.verify:
        verify_execution()
    else:
        result = run()
        print(f'Phase 5B.1: {len(result[0])} pairs; diagnostic execution offline; use --verify for execution checks.')
