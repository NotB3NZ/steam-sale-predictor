# Python environment

The research artifacts and offline regression suite currently work with
`/usr/bin/python3` (CPython 3.9.6) and its already installed packages:

| Dependency | Verified version |
|---|---|
| NumPy | 2.0.2 |
| pandas | 2.3.3 |
| scikit-learn | 1.6.1 |
| SciPy | 1.13.1 |
| matplotlib | 3.9.4 |
| joblib | 1.5.3 |
| threadpoolctl | 3.6.0 |
| XGBoost | 2.1.4 |
| Pillow | 11.3.0 |

The existing `.venv` uses CPython 3.14.7 and lacks the research dependencies.
It was inspected without installing anything, changing it, or deleting it.
Use the verified interpreter for present regression checks; activating `.venv`
does not provide the research environment.

`requirements-scalable.txt` includes the unchanged baseline and ensemble
requirements and pins the remaining direct dependencies used by the reviewed
offline suite. The collector and evidence/label/feature processing use only
Python's standard library. Modeling preparation and model regression require
pandas and the research libraries. Python 3.9 is the minimum syntax/API version.

For a future isolated environment, use a separately installed CPython 3.11 and
the direct dependency pins. Python 3.11 is a portable setup target; that exact
interpreter has not been tested on this machine. For strict original artifact
reproduction, retain the verified Python 3.9.6 stack. The dependency declaration
pins direct packages; it is not a hash-locked wheel archive of all transitive
dependencies or operating-system libraries.

The following setup commands are instructions only. Package installation needs
separate researcher authorization if wheels must be downloaded. They were not
executed:

```sh
python3.11 -m venv .venv-scalable
.venv-scalable/bin/python -m pip install -r requirements-scalable.txt
```

If an authorized, compatible wheelhouse is already available, the offline
installation equivalent is:

```sh
.venv-scalable/bin/python -m pip install --no-index --find-links /path/to/wheelhouse -r requirements-scalable.txt
```

Run the current safe regression suite without a real API credential:

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  MPLCONFIGDIR=/private/tmp/steam-scalable-mpl \
  /usr/bin/python3 -B tests/run_scalable_offline.py \
  --results /private/tmp/steam-scalable-test-results.json
```

The runner denies network access, repository writes, and subprocess execution.
It uses synthetic credentials for mocked HTTP only. Generated files remain in
temporary directories. It does not fit the original models. Original full-run
tests that regenerate historical datasets/reports are deliberately excluded;
original label/feature values and saved model predictions are checked directly.
No command installs dependencies automatically, reads an API-key file, or
consults retired authorization or private-custody directories.
