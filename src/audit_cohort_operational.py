"""Offline original-target adapter and historical feature audit; never fits models."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from cohort_io import ROOT, digest, load_cohort, read_json, require
import cohort_pipeline as pipeline
from audit_cohort_labelability import build as diagnostic_build, mismatch_comparison
from incremental_itad import Journal, resolve_cache


def feature_audit():
    manifest = pipeline.features_core.feature_manifest()
    rows = []
    for entry in manifest['features']:
        static = entry['feature_name'] in pipeline.features_core.STATIC
        price = entry['feature_name'] in pipeline.features_core.PRICE
        rows.append(dict(feature=entry['feature_name'], implemented=True,
                         predictor=entry['baseline_allowlist'], definition=entry['definition'],
                         data_source='frozen cohort release_date; original pilot/master selection metadata' if static else entry['source'],
                         historical_availability=entry['historical_availability_justification'],
                         prediction_cutoff='Target year official sale start UTC; strictly timestamp < cutoff' if price else
                                           'Reported release date on/before sale-start Pacific date' if static else 'Identity/calendar/audit only',
                         potential_leakage=entry['leakage_risk'], missing_value_meaning=entry['missing_value_meaning'],
                         required_change='None to existing calculation; retain retrospective availability caveat' if price else
                                         'None; retain reported-date accuracy and missing release-hour caveats' if static else
                                         'Keep excluded from predictors'))
    rows.extend([
        dict(feature='previous_autumn_sale_participation', implemented=False, predictor=False,
             definition='Not implemented in the approved feature core', data_source='Earlier game-year operational labels could describe observed discount evidence only',
             historical_availability='No verified participation source; not needed by existing 15-feature baseline',
             prediction_cutoff='If separately authorized later: only completed earlier-year sale windows',
             potential_leakage='Using target-year labels or later windows would leak outcomes',
             missing_value_meaning='Not a generated column', required_change='None for reuse; do not add implicitly'),
        dict(feature='popularity_indicators', implemented=False, predictor=False,
             definition='Owners, lifetime Peak CCU, reviews, recommendations and scores excluded',
             data_source='Undated master/pilot snapshots', historical_availability='Historical snapshots unavailable',
             prediction_cutoff='No supported historical as-of cutoff', potential_leakage='Snapshot may incorporate target sale or later popularity',
             missing_value_meaning='Excluded, not imputed', required_change='Keep excluded; timestamped snapshots required before any future inclusion'),
        dict(feature='current_price_and_discount', implemented=False, predictor=False,
             definition='Master Price/Discount excluded; last_observed_price uses only earlier ITAD observations',
             data_source='Undated contemporary master snapshot', historical_availability='No supported historical as-of snapshot',
             prediction_cutoff='No supported historical as-of cutoff', potential_leakage='Contemporary values contain later price information',
             missing_value_meaning='Excluded, not imputed', required_change='Keep excluded')])
    return rows


def build(cohort, cache_dir, reuse_dirs):
    # Reuse the Phase 6A evidence audit without changing its separate policy/output.
    diagnostic, _, games_audit, conflicts, prior_summary = diagnostic_build(cohort, cache_dir, reuse_dirs)
    games = load_cohort(cohort)
    caches = {g['AppID']: resolve_cache(g['AppID'], cache_dir, reuse_dirs) for g in games}
    require(all(status == 'valid' for _, status, _, _ in caches.values()), 'All caches must be complete and valid')
    result = pipeline.evidence(games, caches, include_features=False, label_policy='operational')
    require(result['pairs'] == diagnostic['pairs'], 'Evidence policy changed the classifications')
    require([(r['appid'], r['sale_year'], r['discount_observed']) for r in result['labels']] ==
            [(r['appid'], r['sale_year'], r['discount_observed']) for r in diagnostic['labels']],
            'Original target mapping changed')
    labels, windows = result['labels'], result['windows']
    expected = {(g['AppID'], year) for g in games for year in windows}
    require(len(games) == 2000 and len(expected) == len(labels) == 6000, 'Expected 2000 games / 6000 pairs')
    require({(r['appid'], r['sale_year']) for r in labels} == expected, 'Missing or duplicate label keys')
    require(sum(r['discount_observed'] == 1 for r in labels) == 3030 and
            sum(r['discount_observed'] == 0 for r in labels) == 2970, 'Operational counts differ from established evidence')
    yearly = {}
    for year in windows:
        rr = [r for r in labels if r['sale_year'] == year]
        categories = Counter(r['evidence_category'] for r in rr)
        yearly[str(year)] = dict(pairs=len(rr), categories={c: categories[c] for c in 'ABCD'},
                                positive=sum(r['discount_observed'] == 1 for r in rr),
                                negative=sum(r['discount_observed'] == 0 for r in rr),
                                unknown=sum(r['discount_observed'] == '' for r in rr))
    availability, provenance, nulls = [], [], Counter()
    tested = violations = selected_records = 0
    for game in games:
        appid = game['AppID']
        parsed, issues, other = pipeline.audit.parse_history(caches[appid][0]['history_response'])
        require(not issues and not other, 'Silent parsing exclusions forbidden')
        pairs = [(int(appid), year) for year in windows]
        features, trace = pipeline.features_core.build_features(pairs, {int(appid): game}, {int(appid): parsed}, windows)
        indexed = {r['source_record_index']: r for r in parsed}
        for feature, diagnostic in zip(features, trace):
            year = feature['sale_year']
            cutoff = windows[year][2]
            # Remove all target-sale/later data, then append a synthetic discount
            # exactly at the boundary. Neither operation may alter any feature.
            earlier = [r for r in parsed if pipeline.audit.utc_stamp(r['timestamp_utc']) < cutoff]
            exact = pipeline.audit.observation(dict(timestamp=pipeline.audit.fmt(cutoff), shop={'id': 61},
                 deal=dict(price=dict(amount=1, amountInt=100, currency='USD'),
                           regular=dict(amount=100, amountInt=10000, currency='USD'), cut=99)), len(parsed))
            check, _ = pipeline.features_core.build_features([(int(appid), year)], {int(appid): game},
                                                              {int(appid): earlier + [exact]}, windows)
            require(check[0] == feature, 'Feature depends on target-sale or later evidence')
            indices = diagnostic['valid_prior_raw_indices']
            selected_records += len(indices)
            violations += sum(pipeline.audit.utc_stamp(indexed[i]['timestamp_utc']) >= cutoff for i in indices)
            missing = [name for name in pipeline.features_core.ALLOWLIST if feature[name] is None]
            nulls.update(missing)
            availability.append(dict(appid=appid, sale_year=year, prediction_cutoff_utc=feature['prediction_cutoff_utc'],
                                     has_prior_price_history=feature['has_prior_price_history'],
                                     has_prior_discount_observation=feature['has_prior_discount_observation'],
                                     prior_price_record_count=feature['prior_price_record_count'],
                                     missing_feature_names=json.dumps(missing),
                                     latest_valid_timestamp_conflict=diagnostic['latest_valid_timestamp_conflict'],
                                     release_hour_uncertain=feature['audit_release_hour_uncertain']))
            provenance.append(diagnostic)
            tested += 1
    require(violations == 0 and tested == 6000, 'Feature cutoff audit failed')
    def split(group, years):
        rows = [r for r in labels if r['model_eligible'] and r['evaluation_group'] == group and r['sale_year'] in years]
        return dict(rows=len(rows), games=len({r['appid'] for r in rows}),
                    classes={str(k): n for k,n in sorted(Counter(r['discount_observed'] for r in rows).items())})
    feature_summary = dict(approved_predictors=list(pipeline.features_core.ALLOWLIST),
                          audited_pairs=tested, cutoff_violations=violations,
                          future_removal_and_exact_cutoff_insertion_invariant_pairs=tested,
                          selected_pre_cutoff_record_uses=selected_records,
                          missing_pairs_by_feature={name: nulls[name] for name in pipeline.features_core.ALLOWLIST},
                          pairs_without_prior_price_history=sum(not r['has_prior_price_history'] for r in availability),
                          games_without_prior_price_history_in_any_year=len({g['AppID'] for g in games} -
                              {r['appid'] for r in availability if r['has_prior_price_history']}),
                          pairs_without_prior_discount_observation=sum(not r['has_prior_discount_observation'] for r in availability),
                          latest_price_conflict_pairs=sum(r['latest_valid_timestamp_conflict'] for r in availability),
                          before_reported_release_observation_uses=sum(r['valid_prior_observations_before_reported_release_date'] for r in provenance),
                          requested_since_boundary_observation_uses=sum(r['valid_prior_observations_at_requested_since'] for r in provenance),
                          release_hour_uncertain_pairs=sum(r['release_hour_uncertain'] for r in availability),
                          contemporaneous_provider_availability_proven=False,
                          final_feature_or_model_dataset_generated=False)
    summary = dict(total_games=2000, total_game_year_pairs=6000, positive=3030, negative=2970, unknown=0,
                   operational_label_coverage_percent=100.0, label_policy='operational',
                   original_label_rule=pipeline.labels_core.RULE, mapping={'A': 1, 'B': 0, 'C': 'Unknown', 'D': 0},
                   semantics='Operational zero means no discount observed in available ITAD evidence; not verified Steam Autumn Sale nonparticipation.',
                   distribution_by_year=yearly, sale_windows=prior_summary['sale_windows'],
                   successful_empty_histories=prior_summary['successful_empty_histories'],
                   empty_history_operational_zero_pairs=sum(r['empty_raw_history'] and r['discount_observed'] == 0 for r in labels),
                   games_with_pre_2026_price_evidence=prior_summary['games_with_usable_historical_evidence'],
                   timestamp_shop_conflict_groups=len(conflicts), conflict_appids=prior_summary['affected_conflict_appids'],
                   original_11_ambiguity_groups_preserved=prior_summary['original_11_groups_across_9_games_preserved'],
                   record_parsing_failures=prior_summary['record_parsing_failures'],
                   feature_audit=feature_summary, prospective_split={'training': split('development', {2023, 2024}),
                                                                  'evaluation': split('evaluation', {2025})},
                   no_network=True, no_model_training=True, phase6a_policy_unchanged=True)
    return labels, availability, provenance, feature_audit(), conflicts, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', type=Path, required=True)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--reuse-cache', type=Path, action='append', default=[])
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    require(destination.is_relative_to(ROOT/'reports') and not destination.exists(), 'Use a new reports directory')
    require(not any(p.is_symlink() for p in [args.output_dir.absolute(), *args.output_dir.absolute().parents]), 'Symlink output forbidden')
    def guard(event, values):
        if event.startswith('socket.'):
            raise RuntimeError('Network forbidden in operational audit')
        if event == 'open':
            path, mode, flags = values
            writing = bool((flags or 0) & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            if writing and isinstance(path, (str, bytes, os.PathLike)):
                require(Path(os.fsdecode(path)).resolve().is_relative_to(destination), 'Writes restricted to new reports directory')
        if event in {'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.symlink', 'os.link', 'os.chmod', 'os.utime'}:
            for path in values[:2] if event in {'os.rename', 'os.link'} else values[:1]:
                if isinstance(path, (str, bytes, os.PathLike)):
                    require(Path(os.fsdecode(path)).resolve().is_relative_to(destination), 'Mutations restricted to new reports directory')
    sys.addaudithook(guard)
    inputs = {p for folder in ('data', 'reports', 'models') for p in (ROOT/folder).rglob('*') if p.is_file()}
    baseline = read_json(ROOT/'tests/scalable_artifact_hashes.json')
    inputs.update(ROOT/p for p in baseline)
    before = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    labels, available, provenance, features, conflicts, summary = build(args.cohort, args.cache_dir.resolve(), [p.resolve() for p in args.reuse_cache])
    comparison = mismatch_comparison()
    require(all(digest(ROOT/p) == value for p,value in before.items()), 'Existing artifact changed')
    summary.update(journal=Journal(args.cache_dir.resolve(), 3816, readonly=True).counts(),
                   preserved_input_files=len(before), protected_artifacts_preserved_this_phase=len(baseline),
                   historical_baseline_matches=sum(before[p] == value['sha256'] for p,value in baseline.items()),
                   baseline_comparison=comparison, validated_at_utc=datetime.now(timezone.utc).isoformat(),
                   input_sha256=before, source_sha256={str(p.relative_to(ROOT)): digest(p) for p in
                     [Path(__file__), ROOT/'src/cohort_pipeline.py', ROOT/'src/06_build_operational_labels.py',
                      ROOT/'src/07_build_autumn_features.py', ROOT/'src/autumn_sale_calendar.json']})
    destination.mkdir()
    for name, rows in {'operational_labels.csv': labels, 'feature_availability.csv': available,
                       'feature_leakage_audit.csv': features, 'timestamp_shop_conflicts.csv': conflicts}.items():
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with (destination/name).open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    (destination/'feature_provenance.json').write_text(json.dumps(provenance, indent=2, sort_keys=True)+'\n')
    (destination/'operational_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n')
    print(json.dumps({k: summary[k] for k in ('total_games', 'total_game_year_pairs', 'positive', 'negative', 'unknown',
                          'distribution_by_year', 'feature_audit', 'prospective_split', 'historical_baseline_matches')}))


if __name__ == '__main__':
    main()
