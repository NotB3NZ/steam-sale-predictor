"""Guarded Phase 8C suite; excludes all fitting and inference tests."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_scalable_offline import offline_audit, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.results.resolve().is_relative_to(root): parser.error('Use an external temporary results path')
    if 'ITAD_API_KEY' in os.environ: parser.error('Run with env -u ITAD_API_KEY')
    runtime = Path(tempfile.mkdtemp(prefix='steam-phase8c-tests-', dir='/private/tmp'))
    os.environ['MPLCONFIGDIR'] = str(runtime / 'mpl'); tempfile.tempdir = str(runtime)
    sys.addaudithook(offline_audit)
    import numpy
    import pandas
    module = load('safe_visualization_2026', 'tests/test_visualization_2026.py')
    module.v.install_guard(args.results.resolve().parent, runtime)
    if args.artifacts: module.ARTIFACTS = args.artifacts.resolve()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.FrozenVisualizationTests)
    if args.artifacts: suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(module.DeliveredArtifactTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    receipt = dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                   skips=len(result.skipped), passed=result.wasSuccessful(), network_guard=True,
                   repository_write_guard=True, model_import_and_deserialization_guard=True,
                   model_fitting_tests_excluded=True, no_models_trained=True, no_model_predictions=True,
                   delivered_artifacts_checked=bool(args.artifacts))
    args.results.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__': raise SystemExit(main())
