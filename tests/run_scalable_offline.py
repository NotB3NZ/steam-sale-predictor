"""Run the reviewed offline suite with network and repository-write guards.

The existing full-execution tests regenerate historical reports and are excluded.
This runner uses pure legacy tests plus configurable temp-output regressions.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'src'))


def within_repository(value, dir_fd=None):
    if not isinstance(value, (str, bytes, os.PathLike)):
        return False
    path = Path(os.fsdecode(value))
    if not path.is_absolute() and isinstance(dir_fd, int) and dir_fd >= 0:
        if sys.platform == 'darwin':
            parent = fcntl.fcntl(dir_fd, 50, b'\0'*1024).split(b'\0', 1)[0]
            path = Path(os.fsdecode(parent))/path
        else:
            path = Path(os.readlink(f'/proc/self/fd/{dir_fd}'))/path
    return path.resolve().is_relative_to(ROOT)


def offline_audit(event, args):
    if event == 'open':
        path, mode, flags = args
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if writing and within_repository(path):
            raise RuntimeError('Offline test guard blocked repository write')
    if event in {'os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.utime', 'os.rename', 'os.link', 'os.symlink'}:
        if event in {'os.rename', 'os.link'}:
            targets = [(args[0], args[2]), (args[1], args[3])]
        elif event == 'os.symlink':
            targets = [(args[1], args[2])]
        elif event in {'os.remove', 'os.rmdir'}:
            targets = [(args[0], args[1])]
        elif event in {'os.mkdir', 'os.chmod'}:
            targets = [(args[0], args[2])]
        else:
            targets = [(args[0], None)]
        if any(within_repository(p, fd) for p, fd in targets):
            raise RuntimeError('Offline test guard blocked repository mutation')
    if event == 'subprocess.Popen':
        raise OSError('External commands are unnecessary in these offline tests')
    if event in {'socket.connect', 'socket.getaddrinfo'}:
        raise AssertionError('Network forbidden in offline tests')


def no_network(*args, **kwargs):
    raise AssertionError('Network forbidden in offline tests')


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def individual(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from individual(item)
        else:
            yield item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, help='Optional JSON summary outside repository')
    args = parser.parse_args()
    if args.results and args.results.resolve().is_relative_to(ROOT):
        parser.error('--results must be outside the repository')
    # No credential is read. Running with a real key in the environment is refused.
    if 'ITAD_API_KEY' in os.environ:
        parser.error('Run with env -u ITAD_API_KEY; tests only use synthetic credentials')
    os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'steam-scalable-test-mpl'))
    sys.addaudithook(offline_audit)
    loader = unittest.TestLoader()
    reviewed = {
        'test_itad_collection.py': None,
        'test_scaling_feasibility.py': None,
        'test_autumn_evidence_audit.py': ['EvidenceTests'],
        'test_autumn_sale_coverage.py': ['DiagnosticTests'],
        'test_historical_ground_truth.py': ['SourceFeasibilityTests'],
        'test_operational_labels.py': ['MappingTests'],
        'test_autumn_features.py': ['TemporalFeatureTests', 'PriceFeatureTests', 'StaticAndSchemaTests'],
        'test_scalable_pipeline.py': None,
    }
    tests = []
    with patch('socket.getaddrinfo', no_network), patch('socket.create_connection', no_network), \
         patch('socket.socket.connect', no_network), patch('socket.socket.connect_ex', no_network):
        for filename, classes in reviewed.items():
            m = load('safe_'+filename[:-3], 'tests/'+filename)
            suite = loader.loadTestsFromModule(m) if classes is None else unittest.TestSuite(
                loader.loadTestsFromTestCase(getattr(m, name)) for name in classes)
            tests.extend(t for t in individual(suite) if
                         t._testMethodName != 'test_complete_audit_manifest_plot_data_integrity_and_light_figures')
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests))
    from cohort_io import digest
    inventory = json.loads((ROOT/'tests/scalable_artifact_hashes.json').read_text())
    unchanged = all((ROOT/p).stat().st_size == v['size_bytes'] and digest(ROOT/p) == v['sha256']
                    for p, v in inventory.items())
    summary = dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                   skips=len(result.skipped), passed=result.wasSuccessful() and unchanged,
                   protected_artifacts_verified=len(inventory), protected_artifacts_unchanged=unchanged,
                   repository_write_guard=True, network_guard=True, real_credentials_available=False,
                   pilot_models_refitted=False, full_historical_regeneration_tests_excluded=True)
    if args.results:
        args.results.parent.mkdir(parents=True, exist_ok=True)
        args.results.write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n')
    print(json.dumps(summary))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
