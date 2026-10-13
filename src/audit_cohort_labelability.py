"""Offline evidence/labelability adapter; reuses existing rules without features or fitting."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from cohort_io import ROOT, digest, load_cohort, read_csv, read_json, require
import cohort_pipeline as pipeline
from incremental_itad import Journal, resolve_cache


def labelability_view(labels):
    rows = []
    for label in labels:
        row = dict(label)
        # This is the existing expanded model_eligible mask, not a new mapping.
        row['discount_observed'] = label['discount_observed'] if label['model_eligible'] else ''
        row['labelability_status'] = ('usable_observed_discount' if label['model_eligible'] and
                                     label['discount_observed'] == 1 else
                                     'usable_observed_full_price' if label['model_eligible'] else
                                     'unknown_or_excluded')
        rows.append(row)
    return rows


def mismatch_comparison():
    name = 'data/intermediate/autumn_sale_evidence_records.csv'
    baseline = read_json(ROOT/'tests/scalable_artifact_hashes.json')[name]
    current = (ROOT/name).read_bytes()
    old = subprocess.run(['git', '--no-optional-locks', 'show', 'HEAD:'+name],
                         cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    import io
    prior_rows = list(csv.DictReader(io.StringIO(old.decode('utf-8'), newline='')))
    current_rows = read_csv(ROOT/name)
    canonical = lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False)
    prior_counts = Counter(map(canonical, prior_rows))
    current_counts = Counter(map(canonical, current_rows))
    positions = lambda rows: {canonical(r): i+1 for i, r in enumerate(rows)}
    prior_positions, current_positions = positions(prior_rows), positions(current_rows)
    return dict(path=name, baseline=baseline, current_sha256=digest(ROOT/name),
                git_head_sha256=hashlib.sha256(old).hexdigest(),
                git_head_matches_baseline=hashlib.sha256(old).hexdigest() == baseline['sha256'],
                baseline_rows=len(prior_rows), current_rows=len(current_rows),
                row_multisets_identical=prior_counts == current_counts,
                row_order_identical=prior_rows == current_rows,
                removed_rows=sum((prior_counts-current_counts).values()),
                added_rows=sum((current_counts-prior_counts).values()),
                moved_rows=[dict(appid=r['AppID'], sale_year=r['sale_year'],
                                 source_record_index=r['source_record_index'],
                                 baseline_position=prior_positions[canonical(r)],
                                 current_position=current_positions[canonical(r)])
                            for r in current_rows if canonical(r) in prior_positions and
                            prior_positions[canonical(r)] != current_positions[canonical(r)]],
                interpretation='Ordering-only mismatch' if prior_counts == current_counts else
                               'Content mismatch requires review; no repair performed')


def build(cohort, cache_dir, reuse_dirs):
    games = load_cohort(cohort)
    caches = {g['AppID']: resolve_cache(g['AppID'], cache_dir, reuse_dirs) for g in games}
    result = pipeline.evidence(games, caches, include_features=False)
    require(not result['features'] and not result['provenance'] and not result['modeling'],
            'Audit must not calculate features or modeling tables')
    windows = result['windows']
    require(set(windows) == {2023, 2024, 2025}, 'Expected exactly three target years')
    expected = {(g['AppID'], year) for g in games for year in windows}
    require(len(result['pairs']) == len(result['labels']) == len(expected), 'Missing game-year pairs')
    require({(r['AppID'], r['sale_year']) for r in result['pairs']} == expected, 'Audit keys differ')
    require({(r['appid'], r['sale_year']) for r in result['labels']} == expected, 'Label keys differ')
    labelability = labelability_view(result['labels'])
    for row in result['records']:
        start, end = windows[row['sale_year']][2:]
        require(start <= pipeline.audit.utc_stamp(row['timestamp_utc']) < end, 'Out-of-window evidence')
        require(row['shop_id'] == 61, 'Non-Steam evidence')
    game_rows, conflict_rows = [], []
    raw_count = duplicate_records = ambiguity_records = excluded_2026 = 0
    for game in games:
        appid = game['AppID']
        obj, status, reason, path = caches[appid]
        parsed, issues, other = pipeline.audit.parse_history(obj['history_response']) if status == 'valid' else ([], [], 0)
        analyzed = [r for r in parsed if pipeline.audit.utc_stamp(r['timestamp_utc']) < pipeline.coverage.CUTOFF]
        raw = obj['history_response'] if status == 'valid' else []
        signatures = Counter(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in raw)
        duplicates = sum(count-1 for count in signatures.values())
        conflicts = pipeline.coverage.conflicts(parsed)
        usable = appid in result['usable_history_ids']
        game_rows.append(dict(AppID=appid, Name=game['Name'], cache_path=str(path.relative_to(ROOT)),
                              cache_status=status, issue=reason,
                              collection_history_status=obj['collection_metadata']['history_status'] if obj else '',
                              successful_empty_history=status == 'valid' and not raw,
                              raw_history_records=len(raw), pre_2026_records=len(analyzed),
                              parsing_failures=len(issues), parsing_issues_json=json.dumps(issues),
                              non_steam_records_excluded=other, identical_duplicate_records=duplicates,
                              ambiguous_records=sum(r['observation_kind'] == 'ambiguous' for r in parsed),
                              timestamp_shop_conflict_groups=len(conflicts), usable_historical_records=usable))
        for group in conflicts:
            conflict_rows.append(dict(AppID=appid, timestamp_utc=group[0]['timestamp_utc'], shop_id=61,
                                      source_record_indices=json.dumps([r['source_record_index'] for r in group]),
                                      observation_kinds=json.dumps([r['observation_kind'] for r in group]),
                                      raw_records_json=json.dumps([json.loads(r['raw_record_json']) for r in group]),
                                      in_sale_years=json.dumps([year for year, w in windows.items()
                                          if w[2] <= pipeline.audit.utc_stamp(group[0]['timestamp_utc']) < w[3]])))
        raw_count += len(raw)
        duplicate_records += duplicates
        ambiguity_records += sum(r['observation_kind'] == 'ambiguous' for r in parsed)
        excluded_2026 += len(parsed)-len(analyzed)
    yearly = {}
    for year in windows:
        labels = [r for r in result['labels'] if r['sale_year'] == year]
        views = [r for r in labelability if r['sale_year'] == year]
        cats = Counter(r['evidence_category'] or 'not_classified' for r in labels)
        positives = sum(r['discount_observed'] == 1 for r in views)
        negatives = sum(r['discount_observed'] == 0 for r in views)
        yearly[str(year)] = dict(game_year_pairs=len(labels), evidence_categories={c: cats[c] for c in
                                ['A', 'B', 'C', 'D', 'not_classified']},
                                usable_positive_labels=positives, usable_negative_labels=negatives,
                                unknown_or_excluded=len(labels)-positives-negatives,
                                reliably_observed_label_percent=100*(positives+negatives)/len(labels),
                                legacy_operational_ones=sum(r['discount_observed'] == 1 for r in labels),
                                legacy_operational_zeros=sum(r['discount_observed'] == 0 for r in labels),
                                legacy_operational_nulls=sum(r['discount_observed'] == '' for r in labels),
                                release_ineligible=sum(r['eligibility_status'] == 'ineligible_by_release_date' for r in labels),
                                release_hour_uncertain=sum(r['eligibility_status'] == 'uncertain_release_hour' for r in labels),
                                in_window_conflict_pairs=sum(r.get('in_window_conflicting_timestamp_groups', 0)>0 for r in labels),
                                verified_participation_negative_labels=0)
    groups = Counter(r['AppID'] for r in conflict_rows)
    original = read_json(ROOT/'data/cohorts/preparation_1000/validation.json')['timestamp_ambiguity_games']
    # The historical eleven groups cover pilot AND early expansion caches.
    preserved_groups = {appid: groups.get(appid, 0) for appid in original}
    require(preserved_groups == original, 'Historical timestamp ambiguity groups changed')
    usable_total = sum(r['model_eligible'] for r in result['labels'])
    summary = dict(total_games=len(games), total_game_year_pairs=len(expected),
                   sale_windows={str(y): dict(start_inclusive=pipeline.audit.fmt(w[2]),
                                             end_exclusive=pipeline.audit.fmt(w[3])) for y,w in windows.items()},
                   coverage_by_year=yearly, cache_status_counts=dict(Counter(r['cache_status'] for r in game_rows)),
                   successful_empty_histories=sum(r['successful_empty_history'] for r in game_rows),
                   games_with_usable_historical_evidence=len(result['usable_history_ids']),
                   games_with_usable_labels=len({r['appid'] for r in result['labels'] if r['model_eligible']}),
                   usable_label_pairs=usable_total, usable_label_percent=100*usable_total/len(expected),
                   raw_history_records=raw_count, records_excluded_at_or_after_2026=excluded_2026,
                   record_parsing_failures=sum(r['parsing_failures'] for r in game_rows),
                   non_steam_records_excluded=sum(r['non_steam_records_excluded'] for r in game_rows),
                   ambiguous_history_records=ambiguity_records, identical_duplicate_records=duplicate_records,
                   timestamp_shop_conflict_groups=len(conflict_rows), affected_conflict_appids=sorted(groups, key=int),
                   original_11_groups_across_9_games_preserved=preserved_groups == original,
                   historical_label_rule=pipeline.labels_core.RULE,
                   usable_label_rule='Existing cohort_pipeline model_eligible mask: A/B and not requires_review',
                   semantics='Recorded discounts/full-price observations only; unknowns stay blank. No verified full-sale negatives or official participation labels.',
                   no_feature_calculation=True, no_model_training=True, no_network=True)
    return result, labelability, game_rows, conflict_rows, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', type=Path, required=True)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--reuse-cache', type=Path, action='append', default=[])
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    require(destination.is_relative_to(ROOT/'reports') and not destination.exists(),
            'Choose a new reports directory; existing artifacts cannot be overwritten')
    require(not any(p.is_symlink() for p in [args.output_dir.absolute(), *args.output_dir.absolute().parents]),
            'Symlink output paths forbidden')
    def guard(event, values):
        if event.startswith('socket.'):
            raise RuntimeError('Network forbidden in labelability audit')
        if event == 'open':
            path, mode, flags = values
            writing = bool((flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            if writing and isinstance(path, (str, bytes, os.PathLike)):
                require(Path(os.fsdecode(path)).resolve().is_relative_to(destination), 'Audit writes confined to new report directory')
        if event in {'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.symlink', 'os.link', 'os.chmod', 'os.utime'}:
            for path in values[:2] if event in {'os.rename', 'os.link'} else values[:1]:
                if isinstance(path, (str, bytes, os.PathLike)):
                    require(Path(os.fsdecode(path)).resolve().is_relative_to(destination), 'Audit mutations confined to new report directory')
    sys.addaudithook(guard)
    baseline = read_json(ROOT/'tests/scalable_artifact_hashes.json')
    protected = {p: digest(ROOT/p) for p in baseline}
    inputs = [args.cohort.resolve(), *(p for d in [args.cache_dir, *args.reuse_cache] for p in d.rglob('*') if p.is_file())]
    before = {str(p): digest(p) for p in inputs}
    result, views, games, conflicts, summary = build(args.cohort, args.cache_dir.resolve(), [d.resolve() for d in args.reuse_cache])
    journal = Journal(args.cache_dir.resolve(), 3816, readonly=True)
    comparison = mismatch_comparison()
    require(all(digest(Path(p)) == sha for p,sha in before.items()), 'Raw input changed during audit')
    require(all(digest(ROOT/p) == sha for p,sha in protected.items()), 'Protected artifact changed during audit')
    summary.update(journal=journal.counts(), baseline_comparison=comparison,
                   protected_artifacts_preserved_during_phase=len(protected),
                   historical_baseline_matches=sum(protected[p] == baseline[p]['sha256'] for p in protected),
                   input_files_preserved=len(before), cohort_sha256=digest(args.cohort),
                   validated_at_utc=datetime.now(timezone.utc).isoformat(),
                   source_sha256={p: digest(ROOT/p) for p in ['src/audit_cohort_labelability.py',
                     'src/cohort_pipeline.py', 'src/04_audit_autumn_evidence.py', 'src/05_investigate_sale_coverage.py',
                     'src/06_build_operational_labels.py', 'src/autumn_sale_calendar.json']})
    destination.mkdir()
    tables = {'evidence_audit.csv': result['pairs'], 'evidence_records.csv': result['records'],
              'coverage_diagnostics.csv': result['diagnostics'], 'labelability.csv': views,
              'game_cache_audit.csv': games, 'timestamp_shop_conflicts.csv': conflicts}
    for name, rows in tables.items():
        fields = list(dict.fromkeys(k for row in rows for k in row)) or ['AppID']
        with (destination/name).open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    (destination/'labelability_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n')
    print(json.dumps({k: summary[k] for k in ['total_games', 'total_game_year_pairs', 'coverage_by_year',
          'successful_empty_histories', 'games_with_usable_historical_evidence', 'usable_label_percent',
          'timestamp_shop_conflict_groups', 'protected_artifacts_preserved_during_phase', 'historical_baseline_matches']}))


if __name__ == '__main__':
    main()
