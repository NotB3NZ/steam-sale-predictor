"""Guarded Phase 8B suite: immutable inputs, synthetic XGBoost, optional final artifacts."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_scalable_offline import ROOT, offline_audit, load


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--artifacts',type=Path)
    args=parser.parse_args()
    if args.results.resolve().is_relative_to(ROOT):parser.error('Use an external temporary results path')
    runtime=Path('/private/tmp/steam-2026-prediction-tests');runtime.mkdir(exist_ok=True)
    os.environ['MPLCONFIGDIR']=str(runtime);tempfile.tempdir=str(runtime)
    sys.addaudithook(offline_audit)
    prediction=load('safe_prediction_2026','tests/test_prediction_2026.py')
    cutoff=load('safe_feasibility_2026','tests/test_2026_feasibility.py')
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(prediction.PredictionTests),
                             unittest.defaultTestLoader.loadTestsFromModule(cutoff)])
    if args.artifacts:
        prediction.PredictionArtifactTests.destination=args.artifacts.resolve()
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(prediction.PredictionArtifactTests))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    from cohort_io import digest
    names=('src/predict_cohort_2026.py','tests/test_prediction_2026.py','tests/run_prediction_2026_offline.py','tests/test_2026_feasibility.py')
    summary=dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),
                 passed=result.wasSuccessful(),network_guard=True,repository_write_guard=True,
                 only_synthetic_models_fitted=True,original_models_refitted=False,
                 final_artifacts_tested=bool(args.artifacts),test_source_sha256={n:digest(ROOT/n) for n in names})
    args.results.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
