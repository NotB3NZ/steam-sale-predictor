"""Standard-library, read-only verification of the delivered public research.

No Git, ignored inputs, model loading, training, inference, or plot generation.
The new current-state pins supplement rather than replace historical receipts.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import statistics
import struct
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'scripts/public_artifact_baseline.json'
MODELING = 'reports/cohort_2000_modeling'
MODELS = 'reports/cohort_2000_models'
PRED = 'reports/cohort_2000_2026_predictions'
V26 = 'reports/cohort_2000_2026_visualizations'
EVIDENCE = 'data/intermediate/autumn_sale_evidence_records.csv'
PRED_CSV = PRED + '/predictions_2026.csv'
CUTOFF = '2026-10-01T17:00:00Z'
NOTICE = 'Retrospective event-time-filtered predictions using post-cutoff-collected historical data.'
FIGURES = [
    'reports/cohort_2000_eda/01_games_by_release_year.png',
    'reports/cohort_2000_visualizations/held_out_xgboost_confusion.png',
    V26 + '/06_positive_rate_by_coverage.png',
    V26 + '/01_probability_histogram.png',
]
PHASES = [MODELING, MODELS, 'reports/cohort_2000_visualizations',
          'reports/cohort_2000_2026_feasibility', PRED, V26, 'reports/cohort_2000_eda']
LEGACY_LOCAL = {'games.csv', 'games.json', 'test.py'}
FEATURES = ['game_age_days', 'release_year', 'release_month', 'release_quarter',
            'prior_price_record_count', 'prior_discount_count', 'prior_discount_rate',
            'days_since_last_price_record', 'days_since_last_discount',
            'max_prior_discount_pct', 'mean_prior_discount_pct', 'last_observed_price',
            'last_observed_discount_pct', 'has_prior_price_history',
            'has_prior_discount_observation']


class VerificationError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def safe_path(root, name):
    require(isinstance(name, str) and bool(name) and '\\' not in name,
            'Invalid relative artifact path')
    relative = Path(name)
    require(not relative.is_absolute() and '..' not in relative.parts,
            'Artifact path must remain inside the repository')
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), 'Artifact path escapes repository')
    return path


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load_json(root, name):
    return json.loads(safe_path(root, name).read_text(encoding='utf-8'))


def rows(root, name):
    with safe_path(root, name).open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)),
                'Invalid CSV header: ' + name)
        result = list(reader)
        require(all(None not in row and all(v is not None for v in row.values()) for row in result),
                'Malformed CSV row: ' + name)
        return result


def install_guard(root):
    """Reject writes and prohibited execution; reject reads of private local inputs."""
    root = root.resolve()
    def guard(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'socket.bind', 'urllib.Request'}:
            raise VerificationError('Public verification forbids network activity')
        if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn'}:
            raise VerificationError('Public verification forbids external processes')
        if event == 'import' and args[0].split('.')[0] in {
                'sklearn', 'xgboost', 'joblib', 'pickle', 'requests', 'httpx'}:
            raise VerificationError('Public verification forbids model/network imports')
        if event == 'pickle.find_class':
            raise VerificationError('Public verification forbids deserialization')
        if event == 'open':
            writing = (isinstance(args[1], str) and any(c in args[1] for c in 'wax+')) or (
                isinstance(args[2], int) and args[2] & (
                    os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            require(not writing, 'Public verification forbids filesystem writes')
            if isinstance(args[0], (str, bytes, os.PathLike)):
                path = Path(os.fsdecode(args[0])).resolve()
                if path.is_relative_to(root):
                    rel = path.relative_to(root)
                    public_input = (rel.parts[0] not in {'.git', '.venv', 'apikey', *LEGACY_LOCAL}
                                    and '.DS_Store' not in rel.parts
                                    and not rel.parts[0].startswith(('.env', '.venv')))
                    require(public_input or rel.as_posix() == '.env.example',
                            'Public verification cannot read ignored private inputs')
        if event in {'os.remove', 'os.rmdir', 'os.mkdir', 'os.rename', 'os.link',
                     'os.symlink', 'os.chmod', 'os.utime', 'os.truncate', 'os.chown'}:
            raise VerificationError('Public verification forbids filesystem mutations')
    sys.addaudithook(guard)


def check_installed_guard(root):
    """Exercise audit events only; no request, import, process, or write occurs."""
    probes = [('socket.connect', (None, None)),
              ('subprocess.Popen', (None, None, None, None)),
              ('import', ('xgboost', None, None, None, None)),
              ('pickle.find_class', ('model', 'Class')),
              ('open', (str(root / 'README.md'), 'w', 577)),
              ('open', (str(root / 'apikey'), 'r', 0)),
              ('os.remove', (str(root / 'README.md'), -1))]
    for event, args in probes:
        try:
            sys.audit(event, *args)
        except VerificationError:
            continue
        raise VerificationError('Installed guard did not reject ' + event)
    return len(probes)


def check_hashes(root, pins):
    for name, expected in pins.items():
        path = safe_path(root, name)
        require(path.is_file(), 'Missing public artifact: ' + name)
        require(sha(path) == expected, 'Unexpected current-state hash: ' + name)
    return len(pins)


def prediction_equivalence(predictions, availability, original_hash):
    lookup = {row['appid']: dict(row) for row in predictions}
    require(len(lookup) == len(predictions) == len(availability) == 2000,
            'Prediction equivalence requires 2,000 unique games')
    require(len({r['appid'] for r in availability}) == 2000
            and set(lookup) == {r['appid'] for r in availability},
            'Prediction/availability membership mismatch')
    differences = []
    for row in availability:
        if lookup[row['appid']]['game_name'] != row['game_name']:
            differences.append(row['appid'])
        lookup[row['appid']]['game_name'] = row['game_name']
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(predictions[0]))
    writer.writeheader()
    writer.writerows(lookup[row['appid']] for row in availability)
    require(hashlib.sha256(output.getvalue().encode('utf-8')).hexdigest() == original_hash,
            'Prediction discrepancy exceeds original row-order/name equivalence')
    require(differences == ['2402900'], 'Current committed name discrepancy changed')
    return dict(original_hash_reproduced=True, non_name_fields_unchanged=True,
                current_name_discrepancy_appids=differences, source_written=False)


def check_historical(root, baseline):
    checks = baseline['historical_exceptions']
    require(sha(safe_path(root, EVIDENCE)) == checks['historical_evidence']['current_sha256'],
            'Preserved historical evidence mismatch changed')
    legacy = load_json(root, 'tests/scalable_artifact_hashes.json')
    require(len(legacy) == 219, 'Historical baseline scope changed')
    unavailable = set(legacy) - set(baseline['immutable_sha256']) - {'.gitignore', 'README.md'}
    require(unavailable == LEGACY_LOCAL, 'Unexpected publicly omitted legacy inputs')
    mismatches = []
    for name, record in legacy.items():
        if name in LEGACY_LOCAL:
            continue  # Deliberately do not open ignored files, even when present.
        if sha(safe_path(root, name)) != record['sha256']:
            mismatches.append(name)
            require(name in {EVIDENCE, '.gitignore'}, 'Unexpected historical baseline difference: ' + name)
    require(set(mismatches) == {EVIDENCE, '.gitignore'}, 'Historical exception set changed')
    require(legacy[EVIDENCE]['sha256'] == checks['historical_evidence']['original_sha256'],
            'Original evidence hash differs from documented exception')
    note = load_json(root, V26 + '/source_integrity_notes.json')
    prediction_hash = sha(safe_path(root, PRED_CSV))
    require(prediction_hash == checks['prediction_csv']['current_sha256']
            and note['current_sha256'] == checks['prediction_csv']['phase8c_recorded_sha256'],
            'Prediction discrepancy or historical note changed')
    manifest_entries = 0
    for folder in PHASES:
        for name, expected in load_json(root, folder + '/checksums.json').items():
            manifest_entries += 1
            actual = sha(safe_path(root, folder + '/' + name))
            if actual != expected:
                require(folder == PRED and name == 'predictions_2026.csv'
                        and expected == checks['prediction_csv']['original_sha256']
                        and actual == prediction_hash, 'Unexpected phase manifest difference: ' + folder + '/' + name)
    proof = prediction_equivalence(rows(root, PRED_CSV),
        rows(root, 'reports/cohort_2000_2026_feasibility/game_availability.csv'),
        checks['prediction_csv']['original_sha256'])
    return dict(legacy_entries_checked=len(legacy) - len(LEGACY_LOCAL),
                legacy_entries_omitted=sorted(LEGACY_LOCAL), legacy_mismatches=mismatches,
                phase_manifest_entries=manifest_entries, phase_manifest_exceptions=[PRED_CSV],
                prediction_equivalence=proof,
                old_phase9a_checker='Expected failure: Known Phase 8B discrepancy changed',
                old_phase8c_adapter='Expected failure: Unexpected preexisting name discrepancy')


def ranks(values):
    ordered = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0] * len(values)
    i = 0
    while i < len(ordered):
        end = i + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[i]]:
            end += 1
        for index in ordered[i:end]:
            result[index] = (i + end - 1) / 2 + 1
        i = end
    return result


def spearman(a, b):
    x, y = ranks(a), ranks(b)
    mx, my = statistics.mean(x), statistics.mean(y)
    dx, dy = [v - mx for v in x], [v - my for v in y]
    return math.fsum(u * v for u, v in zip(dx, dy)) / math.sqrt(
        math.fsum(v * v for v in dx) * math.fsum(v * v for v in dy))


def check_tables(cohort, modeling, predictions, features):
    ids = {row['AppID'] for row in cohort}
    require(len(cohort) == len(ids) == 2000, 'Original cohort membership/count changed')
    recent = sum(int(r['release_year']) >= 2015 for r in cohort)
    require(recent == 1883, 'Release-year headline changed')
    require(len(modeling) == len({(r['appid'], r['sale_year']) for r in modeling}) == 6000,
            'Historical game-year keys changed')
    require({r['sale_year'] for r in modeling} == {'2023', '2024', '2025'}, 'Historical years changed')
    expected_counts = {'2023': (979, 1021), '2024': (1068, 932), '2025': (983, 1017)}
    cutoffs = {'2023': '2023-11-21T18:00:00Z', '2024': '2024-11-27T18:00:00Z',
               '2025': '2025-09-29T17:00:00Z'}
    for year, (positive, zero) in expected_counts.items():
        group = [r for r in modeling if r['sale_year'] == year]
        require(len(group) == 2000 and {r['appid'] for r in group} == ids, 'Historical membership changed')
        require(Counter(r['discount_observed'] for r in group) == {'1': positive, '0': zero},
                'Historical label counts changed')
        require(all(r['prediction_cutoff_utc'] == cutoffs[year] and
                    r['evidence_category'] in {'A', 'B', 'D'} and
                    r['discount_observed'] == str(int(r['evidence_category'] == 'A')) for r in group),
                'Historical cutoff or evidence policy changed')
    missing = {name: sum(r[name] == '' for r in modeling) for name in FEATURES}
    discount_nulls = {'days_since_last_discount', 'max_prior_discount_pct', 'mean_prior_discount_pct'}
    price_nulls = {'prior_discount_rate', 'days_since_last_price_record', 'last_observed_price', 'last_observed_discount_pct'}
    require(missing == {name: 1134 if name in discount_nulls else 253 if name in price_nulls else 0
                        for name in FEATURES}, 'Historical predictor missingness changed')
    require(len(predictions) == len(features) == 2000 and
            len({r['appid'] for r in predictions}) == len({r['appid'] for r in features}) == 2000 and
            {r['appid'] for r in predictions} == {r['appid'] for r in features} == ids,
            '2026 cohort membership changed')
    feature_lookup = {r['appid']: r for r in features}
    probabilities, incomplete, groups = [], [], Counter()
    for row in predictions:
        feature = feature_lookup[row['appid']]
        require(all(r['sale_year'] == '2026' and r['prediction_cutoff_utc'] == CUTOFF for r in [row, feature]),
                '2026 year/cutoff changed')
        p = float(row['predicted_probability'])
        require(math.isfinite(p) and 0 <= p <= 1 and row['predicted_operational_label'] == str(int(p >= .5)),
                'Saved probability/class consistency changed')
        require(row['prediction_description'] == NOTICE and row['retrospective_event_time_filtered'] == 'True'
                and row['point_in_time_provider_availability_proven'] == 'False', '2026 provenance semantics changed')
        nulls = [name for name in FEATURES if feature[name] == '']
        require(int(row['missing_feature_count']) == len(nulls)
                and int(row['observed_feature_count']) == 15 - len(nulls), '2026 missingness changed')
        if nulls:
            incomplete.append(row)
        count = int(row['prior_price_record_count'])
        require(count >= 0 and row['prior_price_record_count'] == feature['prior_price_record_count'],
                'Coverage count differs from saved feature')
        group = '0' if count == 0 else '1-9' if count <= 9 else '10-29' if count <= 29 else '30+'
        require(group == row['coverage_group'], 'Coverage group changed')
        groups[(group, row['predicted_operational_label'])] += 1
        probabilities.append(p)
    require(Counter(r['predicted_operational_label'] for r in predictions) == {'1': 1026, '0': 974},
            '2026 saved class counts changed')
    require(len(incomplete) == 336 and all(r['predicted_operational_label'] == '0' for r in incomplete),
            'Missing-predictor prediction finding changed')
    expected_groups = {('0', '0'): 81, ('1-9', '1'): 6, ('1-9', '0'): 499,
                       ('10-29', '1'): 74, ('10-29', '0'): 221, ('30+', '1'): 946, ('30+', '0'): 173}
    require(groups == expected_groups, '2026 coverage breakdown changed')
    return dict(cohort_games=2000, release_2015_or_later=recent, historical_rows=6000, historical_positives=3030,
                historical_operational_zeros=2970, predicted_positive=1026, predicted_operational_zero=974,
                probability_mean=statistics.mean(probabilities), probability_median=statistics.median(probabilities),
                missing_predictor_games=336, all_incomplete_predicted_zero=True,
                score_coverage_spearman_2026=spearman(probabilities,
                    [int(r['prior_price_record_count']) for r in predictions]))


def check_saved_evaluation(root):
    selection = load_json(root, MODELS + '/selection.json')
    require(selection['selected_model'] == 'xgboost' and selection['primary_metric'] == 'average_precision'
            and selection['selection_data'] == '2023 training -> 2024 development validation only'
            and selection['threshold'] == .5 and not selection['hyperparameter_search'], 'Selection protocol changed')
    saved = load_json(root, MODELS + '/held_out_metrics.json')['models']
    historical = rows(root, MODELS + '/held_out_predictions.csv')
    target = {r['appid']: r['discount_observed'] for r in rows(root, MODELING + '/modeling.csv') if r['sale_year'] == '2025'}
    require(set(saved) == {'bernoulli_baseline', 'logistic_regression', 'random_forest', 'xgboost'},
            'Model comparison membership changed')
    require(len(historical) == len({(r['appid'], r['model_name']) for r in historical}) == 8000,
            'Saved held-out model keys changed')
    accuracies = {}
    for name, metrics in saved.items():
        group = [r for r in historical if r['model_name'] == name]
        require(len(group) == 2000 and {r['appid'] for r in group} == set(target)
                and all(r['sale_year'] == '2025' and r['actual_label'] == target[r['appid']] for r in group),
                'Held-out membership/label assignment changed')
        matrix = [[0, 0], [0, 0]]
        for r in group:
            p = float(r['predicted_probability'])
            require(math.isfinite(p) and 0 <= p <= 1 and r['predicted_class'] == str(int(p >= .5)),
                    'Held-out probability/class consistency changed')
            matrix[int(r['actual_label'])][int(r['predicted_class'])] += 1
        accuracy = (matrix[0][0] + matrix[1][1]) / 2000
        brier = statistics.mean((float(r['predicted_probability']) - int(r['actual_label'])) ** 2 for r in group)
        require(matrix == metrics['confusion_matrix'] and accuracy == metrics['accuracy']
                and math.isclose(brier, metrics['brier_score'], abs_tol=1e-12), 'Saved evaluation metrics do not reconcile')
        accuracies[name] = accuracy
    require(saved['xgboost']['accuracy'] == .914 and saved['xgboost']['confusion_matrix'] == [[912, 105], [67, 916]],
            '2025 headline changed')
    xgb = [r for r in historical if r['model_name'] == 'xgboost']
    rho = spearman([float(r['predicted_probability']) for r in xgb], [int(r['prior_price_record_count']) for r in xgb])
    require(math.isclose(rho, .8972032335044287, abs_tol=1e-12), '2025 coverage association changed')
    return dict(selected_model='xgboost', selected_using='2024 average precision',
                accuracy_2025=accuracies['xgboost'], score_coverage_spearman_2025=rho,
                model_accuracy=accuracies)


def check_readme(body, metrics):
    for text in ['2,000', '6,000', '2023–2025', '2024 average precision', '91.4%', '1,026', '974',
                 NOTICE, CUTOFF, 'No independently verified 2026 outcome evaluation exists',
                 'same games recur', 'not genuine prospective forecasts', 'not independently verified Steam sale participation']:
        require(text in body, 'README scientific statement missing: ' + text)
    for name, label in [('bernoulli_baseline', 'Training-prior baseline'), ('logistic_regression', 'Logistic Regression'),
                        ('random_forest', 'Random Forest'), ('xgboost', '**XGBoost**')]:
        row = next((line for line in body.splitlines() if line.startswith('| ' + label + ' |')), '')
        require(bool(row), 'README model row missing')
        for value in [f"{metrics[name]['accuracy'] * 100:.2f}%", f"{metrics[name]['average_precision']:.4f}",
                      f"{metrics[name]['brier_score']:.4f}"]:
            require(value in row, 'README model metric differs from saved result')
    images = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', body)
    require(images == FIGURES, 'README must embed exactly the four approved figures')


def markdown_links(root, documents):
    count = 0
    for name in documents:
        path = safe_path(root, name)
        body = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8'), flags=re.S)
        for target in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', body):
            parsed = urlsplit(target.strip('<>'))
            if parsed.scheme:  # External references are deliberately not fetched.
                continue
            require(not Path(unquote(parsed.path)).is_absolute(), 'Local Markdown links must be relative')
            destination = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            require(destination.is_relative_to(root.resolve()) and destination.exists(),
                    'Broken local Markdown link in ' + name + ': ' + target)
            if parsed.fragment:
                require(destination.is_file(), 'Anchor requires a file')
                headings = re.findall(r'^#+\s+(.+)$', destination.read_text(encoding='utf-8'), re.M)
                counts, slugs = Counter(), set()
                for heading in headings:
                    slug = re.sub(r'\s', '-', re.sub(r'[^\w\- ]', '', heading.lower()))
                    slugs.add(slug + ('-' + str(counts[slug]) if counts[slug] else ''))
                    counts[slug] += 1
                require(unquote(parsed.fragment) in slugs, 'Broken local Markdown anchor: ' + target)
            count += 1
    return count


def png_metadata(path):
    data = path.read_bytes()
    require(data.startswith(b'\x89PNG\r\n\x1a\n'), 'Invalid PNG signature')
    offset, dpi = 8, None
    while offset < len(data):
        size = struct.unpack('>I', data[offset:offset + 4])[0]
        tag, chunk = data[offset + 4:offset + 8], data[offset + 8:offset + 8 + size]
        if tag == b'pHYs':
            x, y, unit = struct.unpack('>IIB', chunk)
            if unit == 1 and x == y:
                dpi = x * .0254
        offset += size + 12
    require(dpi is not None and abs(dpi - 300) < .01, 'Figure DPI is not 300')
    return dpi


def verify(root):
    baseline = load_json(root, BASELINE)
    require(baseline['schema_version'] == 1 and len(baseline['immutable_sha256']) == 2474,
            'Public immutable baseline scope changed')
    immutable = check_hashes(root, baseline['immutable_sha256'])
    presentation = check_hashes(root, baseline['presentation_sha256'])
    historical = check_historical(root, baseline)
    require(load_json(root, MODELING + '/feature_manifest.json')['baseline_feature_allowlist'] == FEATURES,
            'Approved predictor list changed')
    facts = check_tables(rows(root, 'data/cohorts/cohort_2000.csv'), rows(root, MODELING + '/modeling.csv'),
                         rows(root, PRED_CSV), rows(root, PRED + '/features_2026.csv'))
    summary = load_json(root, PRED + '/prediction_summary.json')
    for field, saved_field in [('probability_mean', 'probability_mean'),
                               ('score_coverage_spearman_2026', 'probability_vs_observation_count_spearman')]:
        require(math.isclose(facts[field], summary[saved_field], abs_tol=1e-12), 'Prediction summary does not reconcile')
    require(facts['probability_median'] == summary['probability_quantiles']['0.5']
            and not summary['observed_2026_outcomes_used'] and not summary['calibration_or_performance_estimated'],
            '2026 summary semantics changed')
    facts.update(check_saved_evaluation(root))
    check_readme(safe_path(root, 'README.md').read_text(encoding='utf-8'),
                 load_json(root, MODELS + '/held_out_metrics.json')['models'])
    documents = sorted(name for name in {**baseline['immutable_sha256'], **baseline['presentation_sha256']} if name.endswith('.md'))
    links = markdown_links(root, documents)
    for figure in FIGURES:
        png_metadata(safe_path(root, figure))
    return dict(status='PASS WITH DOCUMENTED EXCEPTIONS', immutable_files_verified=immutable,
                presentation_files_verified=presentation, markdown_documents=len(documents),
                local_links_verified=links, showcase_figures_verified=len(FIGURES),
                facts=facts, historical_integrity=historical,
                scope='Current tracked artifact identity and frozen statistical reconciliation; no outcome verification',
                no_network_requests=True, no_files_written=True, no_models_loaded=True,
                no_training=True, no_prediction_generation=True, ignored_inputs_required=False)


def main():
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Print full public result to stdout')
    args = parser.parse_args()
    install_guard(ROOT)
    try:
        guard_checks = check_installed_guard(ROOT)
        result = verify(ROOT)
        result['safety_guard_checks_passed'] = guard_checks
    except (VerificationError, OSError, ValueError, KeyError, TypeError) as exc:
        print('FAIL: ' + str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    else:
        print(result['status'])
        print(f"Verified {result['immutable_files_verified']} immutable and {result['presentation_files_verified']} presentation files; "
              f"{result['local_links_verified']} local links; four existing 300-DPI showcase figures.")
        print('2,000 games; 6,000 historical rows; XGBoost selected by 2024 average precision; 2025 label accuracy 91.4%.')
        print('2026 saved classes: 1,026 positives / 974 operational zeros; independently verified outcomes unavailable.')
        print('Exceptions: historical evidence hash; prediction CSV names/order with exact original-hash proof; authorized .gitignore edit.')
        print('Legacy local-only inventory entries omitted explicitly: games.csv, games.json, test.py. Old verifiers remain unchanged and can fail.')
        print('No API key, network, writes, model loading, training, inference, or new plots.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
