"""Guarded visualization-only suite; excludes every model-fitting test."""
import argparse
import json
from pathlib import Path
import os
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_scalable_offline import offline_audit,load


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    if args.results.resolve().is_relative_to(root):parser.error('Use an external temporary results path')
    os.environ.setdefault('MPLCONFIGDIR','/private/tmp/steam-scalable-mpl')
    sys.addaudithook(offline_audit)
    module=load('safe_cohort_visualizations','tests/test_cohort_visualizations.py')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
    summary=dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                 passed=result.wasSuccessful(),network_guard=True,repository_write_guard=True,
                 model_fitting_tests_excluded=True,no_models_trained=True,no_model_predictions=True)
    args.results.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
