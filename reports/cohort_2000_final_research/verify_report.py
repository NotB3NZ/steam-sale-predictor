"""Read-only checks for Phase 9A prose, frozen statistics, links and integrity.

No model/plot/data-generation entry point is imported or executed.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DOCS = ['narrative_research_report.md', 'executive_summary.md', 'research_timeline.md',
        'technical_appendix.md', 'figure_index.md', 'README.md']
MODELS = 'reports/cohort_2000_models'
DATA = 'reports/cohort_2000_modeling'
PRED = 'reports/cohort_2000_2026_predictions'
EDA = 'reports/cohort_2000_eda'
VIZ = 'reports/cohort_2000_visualizations'
V26 = 'reports/cohort_2000_2026_visualizations'
MISMATCH = 'data/intermediate/autumn_sale_evidence_records.csv'
NAMES = {'Training-prior baseline': 'bernoulli_baseline', 'Logistic Regression': 'logistic_regression',
         'Random Forest': 'random_forest', 'XGBoost': 'xgboost'}
METRICS = {'Accuracy': 'accuracy', 'Balanced accuracy': 'balanced_accuracy', 'Precision': 'precision',
           'Recall': 'recall', 'F1': 'f1', 'ROC-AUC': 'roc_auc', 'Average precision': 'average_precision',
           'Brier score': 'brier_score'}


def require(ok, message):
    if not ok: raise AssertionError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(name):
    with (ROOT / name).open(newline='', encoding='utf-8') as stream: return list(csv.DictReader(stream))


def plain(body):
    body = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', body)
    body = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', body)
    body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
    body = re.sub(r'^```.*$', '', body, flags=re.M)
    body = re.sub(r'[`*_#>|]', '', body)
    return body


def word_count(body):
    return sum(bool(re.search(r'\w', token)) for token in plain(body).split())


def table_rows(body):
    return [[c.strip() for c in line.strip().split('|')[1:-1]] for line in body.splitlines()
            if line.startswith('|') and not re.match(r'^\|\s*:?-', line)]


def install_guard(writable):
    def allowed(value):
        return isinstance(value, (str, bytes, os.PathLike)) and Path(os.fsdecode(value)).resolve() in writable
    def guard(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'socket.bind', 'urllib.Request'}:
            raise RuntimeError('Phase 9A verification forbids network requests')
        if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn'}:
            raise OSError('Phase 9A verification forbids external commands')
        if event == 'import' and args[0].split('.')[0] in {'sklearn', 'xgboost', 'joblib', 'pickle', 'requests', 'httpx'}:
            raise RuntimeError('Model/network imports forbidden in synthesis')
        if event == 'pickle.find_class': raise RuntimeError('Model deserialization forbidden')
        if event == 'open':
            writing = (isinstance(args[1], str) and any(c in args[1] for c in 'wax+')) or (
                isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing: require(allowed(args[0]), 'Verification cannot modify preexisting project files')
        if event in {'os.rename', 'os.remove', 'os.rmdir', 'os.mkdir', 'os.symlink', 'os.link', 'os.chmod', 'os.utime'}:
            raise RuntimeError('Filesystem mutations unnecessary for synthesis verification')
    sys.addaudithook(guard)


def run(before, sealed=None):
    text = {name: (HERE / name).read_text(encoding='utf-8') for name in DOCS}
    main = text[DOCS[0]]; appendix = text['technical_appendix.md']
    checks = []
    def checked(label, ok, source, value=None):
        require(ok, label)
        checks.append(dict(check=label, source=source, value=value))
    def fact(label, value, source, literal=None, files=None):
        literal = str(value) if literal is None else literal
        for name in files or [DOCS[0]]:
            checked(label + ' in ' + name, literal in text[name], source,
                    dict(source_value=value, reported=literal))
    checked('Exactly eight chapters in order', [int(n) for n in re.findall(r'^## Chapter (\d+) — ', main, re.M)] == list(range(1, 9)), DOCS[0])
    checked('Post-modeling EDA chronology explicit', 'after model development' in main and
            'after model development' in text['research_timeline.md'] and 'Phase 8D' in main, 'reports/cohort_2000_eda/README.md')
    checked('Separate evaluated fit and later refit explicit', 'not the earlier 2023–2024 fit' in main and
            'cannot be transferred' in main, PRED + '/README.md')
    checked('Known limitations explicit', all(s in main for s in ['not an evaluation on completely unseen titles',
            'not an untouched confirmatory holdout', 'not genuine prospective forecasts',
            'No independently verified 2026 outcome evaluation has been conducted.',
            'Pre-cutoff provider availability cannot be established.',
            'Retrospective event-time-filtered predictions using post-cutoff-collected historical data.']),
            'Phase 6C/7A/8A/8B/8C/8D reports')

    selection = read_json(ROOT / MODELS / 'selection.json')
    held = read_json(ROOT / MODELS / 'held_out_metrics.json')['models']
    dev = read_json(ROOT / MODELS / 'development_metrics.json')['models']
    checked('Selection uses 2024 average precision before held-out predictions', selection['selected_model'] == 'xgboost' and
            selection['primary_metric'] == 'average_precision' and not selection['hyperparameter_search'] and
            selection['selection_data'] == '2023 training -> 2024 development validation only', MODELS + '/selection.json')
    fact('Selection lock timestamp', selection['selection_locked_at_utc'], MODELS + '/selection.json', files=['research_timeline.md'])
    fact('Frozen threshold', selection['threshold'], MODELS + '/selection.json', '0.50', [DOCS[0], 'technical_appendix.md'])
    for report, length in [(DOCS[0], 4), ('technical_appendix.md', 10)]:
        found = {r[0]: r for r in table_rows(text[report]) if len(r) == length and r[0] in NAMES}
        checked('All predefined models represented in ' + report, set(found) == set(NAMES), MODELS + '/held_out_metrics.json')
        for label, key in NAMES.items():
            keys = ['accuracy', 'average_precision', 'brier_score'] if length == 4 else list(METRICS.values())
            actual = found[label][1:]
            expected = [f'{held[key][metric]:.4f}' for metric in keys]
            if length == 10: expected.insert(0, f'{dev[key]["average_precision"]:.4f}')
            checked('Frozen model metrics: ' + label + ' / ' + report, actual == expected,
                    MODELS + '/held_out_metrics.json and development_metrics.json', expected)
    metric_rows = {r[0]: r[1] for r in table_rows(main) if len(r) == 3 and r[0] in METRICS}
    for label, key in METRICS.items():
        checked('XGBoost metric explanation table: ' + label, metric_rows.get(label) == f'{held["xgboost"][key]:.4f}',
                MODELS + '/held_out_metrics.json', held['xgboost'][key])
    for label, key in [('XGBoost', 'xgboost'), ('Logistic Regression', 'logistic_regression'), ('Random Forest', 'random_forest')]:
        fact('Development AP: ' + label, dev[key]['average_precision'], MODELS + '/development_metrics.json',
             f'{dev[key]["average_precision"]:.4f}')
    matrix = held['xgboost']['confusion_matrix']
    for label, value in [('true zero', matrix[0][0]), ('positive-on-zero', matrix[0][1]),
                         ('missed positive', matrix[1][0]), ('true positive', matrix[1][1]),
                         ('total agreements', matrix[0][0] + matrix[1][1])]:
        fact('Confusion count: ' + label, value, MODELS + '/held_out_metrics.json', f'{value:,}', [DOCS[0], 'technical_appendix.md'])
    fact('Headline accuracy percent', held['xgboost']['accuracy'], MODELS + '/held_out_metrics.json',
         f'{held["xgboost"]["accuracy"]:.1%}', [DOCS[0], 'executive_summary.md'])
    labels = read_json(ROOT / DATA / 'label_distribution.json')
    windows = read_json(ROOT / DATA / 'input_manifest.json')['sale_windows']
    label_table = {r[0]: r for r in table_rows(appendix) if len(r) == 5 and r[0] in windows}
    for year in ['2023', '2024', '2025']:
        d = labels['by_year'][year]
        expected = [year, windows[year]['start_inclusive'], windows[year]['end_exclusive'], f'{d["positives"]:,}', f'{d["operational_zeros"]:,}']
        checked('Historical labels, year and cutoff: ' + year, label_table.get(year) == expected,
                DATA + '/label_distribution.json and input_manifest.json', expected)
        fact('Yearly positives ' + year, d['positives'], DATA + '/label_distribution.json', f'{d["positives"]:,}')
    for key, value in [('unique_games', 2000), ('rows', 6000), ('positives', 3030), ('operational_zeros', 2970), ('unknowns', 0)]:
        checked('Frozen historical dataset: ' + key, labels['overall'][key] == value, DATA + '/label_distribution.json', value)
    for key in ['unique_games', 'rows', 'positives', 'operational_zeros']:
        fact('Historical size: ' + key, labels['overall'][key], DATA + '/label_distribution.json', f'{labels["overall"][key]:,}', ['technical_appendix.md', 'research_timeline.md'])
    training = read_json(ROOT / DATA / 'temporal_split_manifest.json')
    checked('Historical split counts and game overlap', training['development_training_years'] == [2023] and
            training['development_validation_year'] == 2024 and training['held_out_test_year'] == 2025 and
            training['final_training_years'] == [2023, 2024] and training['final_train_test_game_overlap'] == 2000,
            DATA + '/temporal_split_manifest.json')
    for key, value in [('rows', 4000), ('positives', 2047), ('operational_zeros', 1953)]:
        checked('Final historical training size: ' + key, labels['by_split']['final_training'][key] == value, DATA + '/label_distribution.json', value)
        fact('Final training text ' + key, value, DATA + '/label_distribution.json', f'{value:,}', ['technical_appendix.md'])
    feature_manifest = read_json(ROOT / DATA / 'feature_manifest.json')
    feature_rows = [r[0].strip('`') for r in table_rows(appendix) if len(r) == 2 and r[0].startswith('`')]
    checked('All approved predictor definitions present, no additions', feature_rows == feature_manifest['baseline_feature_allowlist'] and len(feature_rows) == 15,
            DATA + '/feature_manifest.json', feature_rows)
    missing = {r['feature']: int(r['missing']) for r in rows(DATA + '/missingness.csv') if r['sale_year'] == 'all'}
    checked('Historical missingness groups', Counter(missing.values()) == Counter({0: 8, 253: 4, 1134: 3}), DATA + '/missingness.csv', dict(Counter(missing.values())))
    for value in [1134, 253]: fact('Historical missing cells', value, DATA + '/missingness.csv', f'{value:,}', [DOCS[0], 'technical_appendix.md'])
    config = read_json(ROOT / MODELS / 'model_configuration_manifest.json')['fixed_configurations']
    config_rows = {r[0]: r[1] for r in table_rows(appendix) if len(r) == 2}
    config_labels = {'Training-prior Dummy': 'bernoulli_baseline', 'Logistic Regression': 'logistic_regression', 'Random Forest': 'random_forest', 'XGBoost': 'xgboost'}
    for label, key in config_labels.items():
        for param, value in config[key].items():
            if param == 'penalty': literal = 'L2 penalty'
            else: literal = param + '=' + (json.dumps(value) if isinstance(value, str) else str(value))
            checked('Configuration: ' + key + '/' + param, literal in config_rows[label], MODELS + '/model_configuration_manifest.json', value)
    diagnostics = read_json(ROOT / MODELS / 'held_out_diagnostics.json')['summary']
    fact('Final training-prior probability', diagnostics['bernoulli_baseline']['mean_probability'], MODELS + '/held_out_diagnostics.json', '0.51175', ['technical_appendix.md'])
    rho25 = diagnostics['xgboost']['probability_vs_record_count_spearman']
    fact('2025 Spearman association', rho25, MODELS + '/held_out_diagnostics.json', f'{rho25:.4f}', [DOCS[0], 'executive_summary.md', 'technical_appendix.md'])
    subgroup = next(r for r in rows(VIZ + '/coverage_summary.csv') if r['stage'] == 'held_out' and r['segment'] == '1-9')
    for key in ['observations', 'actual_positive']:
        fact('Sparse subgroup: ' + key, int(subgroup[key]), VIZ + '/coverage_summary.csv', f'{int(subgroup[key]):,}', [DOCS[0], 'technical_appendix.md'])
    checked('Sparse subgroup detects seven and misses twelve', int(subgroup['tp']) == 7 and int(subgroup['fn']) == 12, VIZ + '/coverage_summary.csv', [7, 12])
    fact('Sparse subgroup accuracy', float(subgroup['accuracy']), VIZ + '/coverage_summary.csv', f'{float(subgroup["accuracy"]):.1%}', [DOCS[0], 'technical_appendix.md'])

    stats = read_json(ROOT / EDA / 'descriptive_statistics.json')
    for key, fmt in [('release_2015_or_later', ',d'), ('release_year_min', 'd'), ('release_year_max', 'd'),
                     ('price_games', ',d'), ('price_missing_games', 'd'), ('price_below_10_games', ',d'),
                     ('price_median', '.2f'), ('price_max', '.2f'), ('observation_median', '.0f'),
                     ('observation_min', 'd'), ('observation_max', 'd'), ('zero_observation_games', 'd'),
                     ('valid_discount_records', ',d'), ('discounted_record_games', ',d'), ('discount_median', '.0f')]:
        literal = format(stats[key], fmt)
        # Not all per-source statistics are quoted verbatim: the price threshold
        # share is reported rather than its numerator; range zero is prose elsewhere.
        if key in {'price_below_10_games', 'observation_min'}: continue
        fact('EDA: ' + key, stats[key], EDA + '/descriptive_statistics.json', literal)
    fact('Recent release share', stats['release_2015_or_later'] / stats['games'], EDA + '/descriptive_statistics.json',
         f'{stats["release_2015_or_later"] / stats["games"]:.1%}')
    fact('Price-below-ten share', stats['price_below_10_games'] / stats['price_games'], EDA + '/descriptive_statistics.json',
         f'{stats["price_below_10_games"] / stats["price_games"]:.1%}')
    release = {int(r['release_year']): int(r['games']) for r in rows(EDA + '/release_years.csv')}
    checked('Largest release-year group', max(release, key=release.get) == 2022 and release[2022] == 327, EDA + '/release_years.csv', [2022, 327])
    checked('Observed zero prices and chart exclusions', stats['price_zero_games'] == 2 and
            stats['discount_conflicting_records_excluded'] == 2 and stats['discount_full_price_records_excluded'] == 24,
            EDA + '/descriptive_statistics.json', [2, 2, 24])
    recurrence = [int(r['games']) for r in rows(EDA + '/evidence_recurrence.csv')]
    checked('Three-year evidence recurrence', recurrence == [741, 201, 345, 713] and sum(recurrence) == 2000, EDA + '/evidence_recurrence.csv', recurrence)
    fact('Recurrence statement', recurrence, EDA + '/evidence_recurrence.csv', ', '.join(map(str, recurrence[:-1])) + ' and ' + str(recurrence[-1]), [DOCS[0], 'technical_appendix.md'])
    historical_cov = [r for r in rows(EDA + '/coverage.csv') if r['sale_year'] == '2025']
    for r in historical_cov[1:]:
        fact('Historical coverage rate ' + r['coverage_group'], float(r['discount_observed_rate']), EDA + '/coverage.csv', f'{float(r["discount_observed_rate"]):.2%}')

    summary = read_json(ROOT / PRED / 'prediction_summary.json')
    refit = read_json(ROOT / PRED / 'configuration_manifest.json')
    checked('Separate refit configuration and training scope', refit['selected_configuration'] == selection['selected_configuration'] and
            refit['training_years'] == [2023, 2024, 2025] and refit['training_rows'] == 6000 and
            refit['positive_labels'] == 3030 and refit['operational_zero_labels'] == 2970 and refit['no_2026_outcomes_used'],
            PRED + '/configuration_manifest.json')
    for key in ['predicted_positive', 'predicted_operational_zero']:
        fact('2026 total: ' + key, summary[key], PRED + '/prediction_summary.json', f'{summary[key]:,}', [DOCS[0], 'executive_summary.md', 'technical_appendix.md'])
    fact('2026 positive percent', summary['predicted_positive_percent'], PRED + '/prediction_summary.json', f'{summary["predicted_positive_percent"]:.1f}%')
    fact('2026 zero percent', summary['predicted_zero_percent'], PRED + '/prediction_summary.json', f'{summary["predicted_zero_percent"]:.1f}%')
    for label, value in [('mean', summary['probability_mean']), ('median', summary['probability_quantiles']['0.5']),
                         ('Spearman', summary['probability_vs_observation_count_spearman'])]:
        fact('2026 score summary: ' + label, value, PRED + '/prediction_summary.json', f'{value:.4f}', [DOCS[0], 'executive_summary.md', 'technical_appendix.md'])
    cov26 = rows(PRED + '/coverage.csv')
    cov_table = [r for r in table_rows(appendix) if len(r) == 5 and r[0] in {'0', '1–9', '10–29', '30+'}]
    expected = [[r['coverage_group'].replace('-', '–'), f'{int(r["games"]):,}', f'{int(r["predicted_positive"]):,}',
                 f'{int(r["predicted_operational_zero"]):,}', f'{float(r["predicted_positive_percent"]):.2f}%'] for r in cov26]
    checked('Complete 2026 coverage table', cov_table == expected, PRED + '/coverage.csv', expected)
    patterns = {int(r['missing_features']): r for r in rows(PRED + '/missingness_patterns.csv')}
    incomplete = sum(int(r['games']) for n, r in patterns.items() if n > 0)
    checked('All incomplete vectors predicted zero', incomplete == 336 and all(int(r['predicted_positive']) == 0 for n, r in patterns.items() if n > 0),
            PRED + '/missingness_patterns.csv', incomplete)
    for n in [3, 7]: fact('2026 missingness pattern', int(patterns[n]['games']), PRED + '/missingness_patterns.csv', str(patterns[n]['games']))
    complete_zeros = int(patterns[0]['games']) - int(patterns[0]['predicted_positive'])
    for label, value in [('incomplete games', incomplete), ('complete-vector zeros', complete_zeros)]:
        fact('2026 missingness: ' + label, value, PRED + '/missingness_patterns.csv', str(value), [DOCS[0], 'executive_summary.md', 'technical_appendix.md'])
    missing_status = next(r for r in rows(V26 + '/missingness_status_summary.csv') if r['predictor_status'] == 'Any missing')
    checked('Incomplete-vector observation range', float(missing_status['observation_count_min']) == 0 and
            float(missing_status['observation_count_max']) == 4, V26 + '/missingness_status_summary.csv', [0, 4])
    feasibility = read_json(ROOT / 'reports/cohort_2000_2026_feasibility/feasibility_summary.json')
    cutoff = read_json(ROOT / PRED / 'feature_schema_manifest.json')['cutoff_utc']
    fact('2026 cutoff', cutoff, PRED + '/feature_schema_manifest.json', files=[DOCS[0], 'executive_summary.md', 'technical_appendix.md', 'README.md'])
    checked('All history receipts postdate cutoff', feasibility['earliest_history_receipt_utc'] > cutoff and
            feasibility['earliest_history_receipt_utc'].startswith('2026-10-05') and feasibility['latest_history_receipt_utc'].startswith('2026-10-13') and
            feasibility['demonstrated_pre_cutoff_cache_snapshots'] == feasibility['fully_point_in_time_proven_vectors'] == 0,
            'reports/cohort_2000_2026_feasibility/feasibility_summary.json')
    for k, filename, values in [('original metadata', 'reports/source_data_report.md', ['125,855']),
                                ('catalog', 'reports/games_master_report.md', ['99,194']),
                                ('pilot history', 'reports/itad_collection_report.md', ['100', '97', '3', '5568']),
                                ('independent verification pilot', 'reports/autumn_sale_ground_truth_feasibility.md', ['18'])]:
        source = (ROOT / filename).read_text()
        checked('Documented earlier phase quantities: ' + k, all(v in source for v in values), filename, values)
    pilot = rows('data/intermediate/pilot_games.csv'); cohort = rows('data/cohorts/cohort_2000.csv')
    checked('Pilot retained in original frozen cohort', len(pilot) == 100 and len(cohort) == len({r['AppID'] for r in cohort}) == 2000 and
            {r['AppID'] for r in pilot} <= {r['AppID'] for r in cohort}, 'data/intermediate/pilot_games.csv; data/cohorts/cohort_2000.csv', [100, 1900, 2000])
    recovered = read_json(ROOT / 'data/cohorts/runs/first_live_10/recovery_20261012T192136Z/recovery_results.json')
    checked('Initial ten-game recovery completed', recovered['sample_size'] == recovered['successful_game_caches'] == 10 and
            not recovered['unresolved_appids'] and not recovered['completed_games_refetched'],
            'data/cohorts/runs/first_live_10/recovery_20261012T192136Z/recovery_results.json')
    last_batch = read_json(ROOT / 'data/cohorts/runs/2000_batch_004/collection_quality.json')
    checked('Final collection completed', last_batch['games_with_complete_caches'] == 2000 and
            last_batch['games_with_unresolved_failures'] == 0, 'data/cohorts/runs/2000_batch_004/collection_quality.json')
    journal = [json.loads(line) for line in (ROOT / 'data/cohorts/itad/cache/http_attempts.jsonl').read_text().splitlines()]
    statuses = Counter(str(r.get('http_status')) for r in journal if r['kind'] == 'result')
    checked('Expansion request accounting', sum(r['kind'] == 'attempt' for r in journal) == 3816 and
            statuses == Counter({'200': 3801, '429': 5, '403': 1, 'None': 9}),
            'data/cohorts/itad/cache/http_attempts.jsonl', dict(statuses))
    checked('Empty successful histories', feasibility['successful_empty_histories'] == 81, 'reports/cohort_2000_2026_feasibility/feasibility_summary.json', 81)

    # Every link is resolved locally. No source URL is fetched.
    links, images, external = [], [], []
    for name, body in text.items():
        for image_flag, label, target in re.findall(r'(!?)\[([^\]]*)\]\(([^)]+)\)', body):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                external.append(target); continue
            require(not Path(unquote(parsed.path)).is_absolute(), 'Report links must be relative')
            path = (HERE / unquote(parsed.path)).resolve() if parsed.path else HERE / name
            require(path.is_relative_to(ROOT) and path.is_file(), 'Unresolved Markdown link: ' + name + ' -> ' + target)
            if parsed.fragment:
                headings = re.findall(r'^#+\s+(.+)$', path.read_text(), re.M)
                slugs = [re.sub(r'\s+', '-', re.sub(r'[^\w\- ]', '', h.lower())) for h in headings]
                require(unquote(parsed.fragment) in slugs, 'Unresolved Markdown anchor: ' + target)
            links.append(dict(document=name, target=target))
            if image_flag:
                require(path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'), 'Invalid linked PNG')
                images.append(dict(document=name, path=str(path.relative_to(ROOT)), sha256=sha(path)))
    checked('Ten unique existing figure embeds', len(images) == len({r['path'] for r in images}) == 10 and
            all(r['document'] == DOCS[0] for r in images), 'figure_index.md', len(images))
    checked('Ten numbered explanatory captions', re.findall(r'^\*Figure (\d+)\.', main, re.M) == [str(i) for i in range(1, 11)], DOCS[0])
    index_paths = {str((HERE / target).resolve().relative_to(ROOT)) for _, target in
                   re.findall(r'\[([^\]]+)\]\(([^)]+\.png)\)', text['figure_index.md'])}
    checked('Figure index exactly matches embeds', index_paths == {r['path'] for r in images}, 'figure_index.md')
    caveat = read_json(ROOT / V26 / 'source_integrity_notes.json')
    require(sha(ROOT / caveat['file']) == caveat['current_sha256'] and caveat['original_manifest_hash_reproduced'] and
            caveat['all_other_fields_unchanged'] and not caveat['source_repaired'], 'Known Phase 8B discrepancy changed')
    checked('Original name discrepancies documented without replacement games',
            [r['appid'] for r in caveat['name_discrepancies']] == [1518000, 2402900] and
            all(str(r['appid']) in appendix and r['current_prediction_csv_name'] in appendix and r['frozen_cohort_name'] in appendix
                for r in caveat['name_discrepancies']), V26 + '/source_integrity_notes.json')
    source_indexes = {}
    for folder in [DATA, MODELS, VIZ, 'reports/cohort_2000_2026_feasibility', PRED, V26, EDA]:
        index = read_json(ROOT / folder / 'checksums.json')
        exceptions = []
        for name, expected_hash in index.items():
            require(not Path(name).is_absolute() and '..' not in Path(name).parts and
                    (ROOT / folder / name).resolve().is_relative_to((ROOT / folder).resolve()), 'Unsafe source manifest path')
            actual = sha(ROOT / folder / name)
            if actual != expected_hash:
                require(folder == PRED and name == 'predictions_2026.csv' and actual == caveat['current_sha256'] and
                        expected_hash == caveat['manifest_sha256'], 'Unexpected source manifest discrepancy: ' + folder + '/' + name)
                exceptions.append(name)
        source_indexes[folder] = dict(files=len(index), sha256=sha(ROOT / folder / 'checksums.json'), known_exceptions=exceptions)
    original = read_json(ROOT / 'tests/scalable_artifact_hashes.json')
    mismatches = [name for name, value in original.items() if sha(ROOT / name) != value['sha256']]
    require(len(original) == 219 and mismatches == [MISMATCH], 'Protected historical baseline state changed')
    require(all((ROOT / name).is_file() and sha(ROOT / name) == value for name, value in before.items()), 'Preexisting artifact modified')
    expected_mismatch = read_json(ROOT / PRED / 'validation.json')['existing_baseline_mismatch_preserved_sha256']
    require(sha(ROOT / MISMATCH) == expected_mismatch, 'Historical mismatch modified')
    output_hashes = {name: sha(HERE / name) for name in [*DOCS, 'verify_report.py']}
    if sealed: require(output_hashes == sealed['output_sha256'], 'Delivered synthesis bytes changed')
    # Exercise guards with audit events only: no request, process, import or write happens.
    for event, args in [('socket.connect', (None, None)), ('subprocess.Popen', (None, None, None, None)),
                        ('import', ('xgboost', None, None, None, None)), ('pickle.find_class', ('model', 'Class')),
                        ('open', (str(ROOT / 'reports/forbidden-phase9a-write'), 'w', 577))]:
        try: sys.audit(event, *args)
        except (AssertionError, RuntimeError, OSError): pass
        else: raise AssertionError('Guard did not reject ' + event)
    return dict(passed=True, numerical_and_structural_checks=len(checks), checks=checks,
        local_links_checked=len(links), links=links, external_urls_not_fetched=external,
        figures=images, figure_count=10, chapters=8,
        word_counts={name: word_count(body) for name, body in text.items()},
        total_six_document_words=sum(word_count(body) for body in text.values()),
        word_count_convention='Whitespace-delimited visible Markdown tokens containing letters/numbers; headings, captions and table content included; image syntax/alt text and link destinations excluded.',
        source_indexes=source_indexes, output_sha256=output_hashes,
        preserved_preexisting_files=len(before), protected_artifacts_preserved=219,
        historical_baseline_matches=218, historical_baseline_total=219, historical_mismatch=MISMATCH,
        historical_mismatch_current_sha256=expected_mismatch, historical_mismatch_preserved_without_repair=True,
        phase8b_prediction_csv_discrepancy=caveat, phase_start_sha256=before,
        no_network_requests=True, no_models_loaded=True, no_models_trained=True, no_new_predictions=True,
        no_new_experiments=True, no_new_figures=True, no_cohort_or_label_changes=True,
        guard_checks_passed=5, journal_attempts=3816, journal_lines=len(journal),
        review=dict(narrative_flow=True, technical_accuracy=True, accessibility=True, chronology=True,
                    no_invented_events=True, source_traceability=True, limitations_explicit=True,
                    reviewed_by='Authoring agent against local frozen documentation; not an independent scientific peer review'))


def main():
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase-start-checksums', type=Path)
    parser.add_argument('--record', action='store_true', help='Create the initial receipt once; refuses overwrite')
    parser.add_argument('--results', type=Path, help='Optional result JSON outside the repository')
    args = parser.parse_args()
    require('ITAD_API_KEY' not in os.environ, 'Run with env -u ITAD_API_KEY')
    if args.results: require(not args.results.resolve().is_relative_to(ROOT) and args.results.parent.is_dir(), 'Use an existing external results directory')
    receipt_path = HERE / 'verification.json'
    require(not args.record or (args.phase_start_checksums and not receipt_path.exists()), 'Initial recording requires snapshot and a fresh receipt')
    writable = {args.results.resolve()} if args.results else set()
    if args.record: writable.add(receipt_path)
    install_guard(writable)
    sealed = None if args.record else read_json(receipt_path)
    before = read_json(args.phase_start_checksums) if args.phase_start_checksums else sealed['phase_start_sha256']
    result = run(before, sealed)
    if args.record:
        with receipt_path.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n')
    if args.results:
        args.results.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['passed', 'numerical_and_structural_checks', 'local_links_checked', 'figure_count',
        'word_counts', 'total_six_document_words', 'preserved_preexisting_files', 'protected_artifacts_preserved', 'historical_baseline_matches']}))


if __name__ == '__main__': main()
