"""Shared cohort schemas and isolated output paths; no network or secrets."""
import csv
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_CACHE = ROOT/'data/raw/itad'
SIZES = (500, 1000, 2000, 5000)

def require(ok, message):
    if not ok:
        raise ValueError(message)

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def read_json(path):
    def fields(items):
        obj = {}
        for k, v in items:
            require(k not in obj, 'Duplicate JSON field')
            obj[k] = v
        return obj
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=fields,
                      parse_constant=lambda _: require(False, 'Nonfinite JSON'))

def read_csv(path):
    with Path(path).open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        require(bool(fields) and len(fields) == len(set(fields)), 'Invalid or duplicate CSV columns')
        rows = list(reader)
    require(all(None not in r and all(v is not None for v in r.values()) for r in rows), 'Malformed CSV row')
    return rows

def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'src'/filename)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def checked_path(path, write=False):
    path = Path(path).expanduser().absolute()
    require(not any(p.is_symlink() for p in [path, *path.parents]), 'Symlink paths are not permitted')
    path = path.resolve()
    if write and path.is_relative_to(ROOT):
        require(path.is_relative_to(ROOT/'data/cohorts'),
                'Repository outputs must be under data/cohorts; original artifacts are read-only')
    if write and not path.is_relative_to(ROOT):
        # These external directories are never destinations of this pipeline.
        for forbidden in [Path.home()/'Documents/ITAD_Trial_Authorization',
                          Path.home()/'Documents/ITAD_Private_Custody']:
            require(not path.is_relative_to(forbidden), 'External authorization directories are retired')
    return path

def write_json(path, obj, key=''):
    path = checked_path(path, write=True)
    body = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+'\n'
    require(not key or (key not in body and json.dumps(key)[1:-1] not in body), 'Credential reflection withheld')
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        f.write(body)
        f.flush()
        import os
        os.fsync(f.fileno())
    temporary.replace(path)

def write_csv(path, rows, fields):
    path = checked_path(path, write=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)

def group_for(appid):
    # Stable across cohort sizes; excludes the original pilot from fresh unseen-game claims.
    value = int(hashlib.sha256(f'steam-autumn-scalable-game-split|42|{appid}'.encode()).hexdigest(), 16)
    return 'evaluation' if value % 5 == 0 else 'development'

def load_cohort(path):
    rows = read_csv(checked_path(path))
    require(bool(rows), 'Empty cohort')
    seen = set()
    original = {r['AppID'] for r in read_csv(ROOT/'data/intermediate/pilot_games.csv')}
    out = []
    for r in rows:
        appid = r.get('AppID', r.get('appid', ''))
        require(bool(re.fullmatch(r'[1-9][0-9]*', appid)) and int(appid) <= 2**32-1, 'Invalid cohort AppID')
        require(appid not in seen, 'Duplicate cohort AppID')
        seen.add(appid)
        name = r.get('Name', r.get('name', ''))
        release = r.get('release_date', '')
        require(bool(name.strip()), 'Missing game name')
        require(date.fromisoformat(release).isoformat() == release, 'Invalid release date')
        group = r.get('evaluation_group') or ('development' if appid in original else group_for(appid))
        require(group in {'development', 'evaluation'}, 'Invalid game-level evaluation group')
        require(appid not in original or group == 'development', 'Previously inspected pilot games must remain development')
        out.append(dict(AppID=appid, Name=name, release_date=release, release_year=str(date.fromisoformat(release).year),
                        evaluation_group=group, pilot_membership=int(appid in original),
                        sampling_stratum=r.get('sampling_stratum', ''),
                        probability_sample_rank=r.get('probability_sample_rank', '')))
    return out

def select_cohort(size, destination, candidate_path=None):
    require(size in SIZES, 'Supported planned totals: 500, 1000, 2000, 5000')
    candidate_path = Path(candidate_path or ROOT/'data/intermediate/autumn_sale_scaling_candidates.csv')
    frame = read_csv(candidate_path)
    selected = [r for r in frame if r[f'included_in_{size}'] == '1']
    require(len(selected) == size and len({r['appid'] for r in selected}) == size, 'Candidate cohort count mismatch')
    master = {r['AppID']: r for r in read_csv(ROOT/'data/intermediate/games_master.csv')}
    pilot = read_csv(ROOT/'data/intermediate/pilot_games.csv')
    ids = {r['AppID'] for r in pilot}
    require(ids <= {r['appid'] for r in selected}, 'Candidate cohort must include original pilot')
    selected.sort(key=lambda r: (r['pilot_membership'] != '1',
                                int(r['probability_sample_rank'] or 0), int(r['appid'])))
    rows = []
    for r in selected:
        game = master[r['appid']]
        require(game['release_date'] == r['release_date'], 'Candidate/master release disagreement')
        rows.append(dict(AppID=r['appid'], Name=game['Name'], release_date=r['release_date'], release_year=r['release_year'],
                         pilot_membership=int(r['appid'] in ids), sampling_stratum=r['sampling_stratum'],
                         probability_sample_rank=r['probability_sample_rank'],
                         evaluation_group='development' if r['appid'] in ids else group_for(r['appid'])))
    destination = checked_path(destination, write=True)
    require(not destination.exists(), 'Cohort already exists; reuse the frozen file instead of overwriting it')
    write_csv(destination, rows, list(rows[0]))
    return dict(target_games=size, cohort_sha256=digest(destination), candidate_sha256=digest(candidate_path),
                development_games=sum(r['evaluation_group'] == 'development' for r in rows),
                evaluation_games=sum(r['evaluation_group'] == 'evaluation' for r in rows),
                selection='Existing included_in_N flags and sample ranks; no retrieval/outcome-based replacements',
                split='Stable SHA-256 seed 42 at game level; diagnostic pilot remains development')
