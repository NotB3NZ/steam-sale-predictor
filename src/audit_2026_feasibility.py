"""Event-time 2026 feature feasibility and provider-availability audit; no predictions."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import os
from pathlib import Path
import statistics
import sys
from zoneinfo import ZoneInfo

from cohort_io import ROOT, digest, load_cohort, read_csv, read_json, require
import cohort_pipeline as pipeline
from incremental_itad import resolve_cache, Journal
from visualize_cohort_models import frozen_model_guard,write_csv
import train_cohort_temporal as temporal

FEATURES=pipeline.features_core


def verified_window(calendar):
    require(calendar['sale_year']==2026 and calendar['verified_on']=='2026-10-14' and calendar['sources'], 'Missing verified 2026 calendar')
    pacific=ZoneInfo('America/Los_Angeles')
    start=datetime.fromisoformat(calendar['sale_start_pacific'])
    end=datetime.fromisoformat(calendar['sale_end_pacific'])
    require(start.isoformat()==start.astimezone(pacific).isoformat() and end.isoformat()==end.astimezone(pacific).isoformat(), 'Wrong Pacific offsets')
    require(pipeline.audit.fmt(start.astimezone(timezone.utc))==calendar['sale_start_utc'] and
            pipeline.audit.fmt(end.astimezone(timezone.utc))==calendar['sale_end_utc'], 'Wrong UTC conversion')
    require(calendar['prediction_cutoff_utc']==calendar['sale_start_utc'] and start<end, 'Cutoff must use exclusive sale-start boundary')
    return (start.date().isoformat(),end.date().isoformat(),start.astimezone(timezone.utc),end.astimezone(timezone.utc))


def validate_vector(row,cutoff):
    require(tuple(row)==FEATURES.FIELDS and row['sale_year']==2026 and row['prediction_cutoff_utc']==pipeline.audit.fmt(cutoff), 'Feature schema/cutoff differs')
    integer=set(FEATURES.STATIC)|{'prior_price_record_count','prior_discount_count','has_prior_price_history','has_prior_discount_observation'}
    nullable=set(FEATURES.PRICE)-integer
    for name in FEATURES.ALLOWLIST:
        value=row[name]
        if value is None:
            require(name in nullable, 'Unexpected required-feature null')
        else:
            require(type(value) in {int,float} and math.isfinite(value) and value>=0, 'Invalid numeric feature')
            require(name not in integer or type(value) is int, 'Noninteger feature')
    require(1<=row['release_year']<=2026 and 1<=row['release_month']<=12 and
            row['release_quarter']==(row['release_month']-1)//3+1, 'Invalid release components')
    count,discounts=row['prior_price_record_count'],row['prior_discount_count']
    require(discounts<=count and row['has_prior_price_history']==int(count>0) and
            row['has_prior_discount_observation']==int(discounts>0), 'Count/flag inconsistency')
    require(row['prior_discount_rate'] is None if not count else math.isclose(row['prior_discount_rate'],discounts/count), 'Invalid ratio')
    for name in ('last_observed_discount_pct','max_prior_discount_pct','mean_prior_discount_pct'):
        require(row[name] is None or 0<=row[name]<=100, 'Invalid percentage')
    for name in ('days_since_last_price_record','days_since_last_discount'):
        require(row[name] is None or row[name]>0, 'Non-prior recency')
    if not count:require(all(row[name] is None for name in nullable),'Missing history zero-filled')
    if not discounts:require(all(row[name] is None for name in ('days_since_last_discount','max_prior_discount_pct','mean_prior_discount_pct')),'Missing discounts zero-filled')


def receipt_evidence(obj,cutoff):
    evidence=obj['history_evidence']
    received=pipeline.audit.utc_stamp(evidence['received_at'])
    server_date=parsedate_to_datetime(evidence['response_headers']['Date']).astimezone(timezone.utc) if evidence['response_headers'].get('Date') else None
    # Only receipt of this complete response before cutoff could demonstrate
    # its contents locally. A later receipt cannot date provider first-availability.
    return dict(history_received_at_utc=pipeline.audit.fmt(received),
                server_date_utc=pipeline.audit.fmt(server_date) if server_date else '',
                cache_snapshot_received_before_cutoff=received<cutoff,
                provider_available_before_cutoff_demonstrated=received<cutoff,
                availability_interpretation='Pre-cutoff response receipt evidence' if received<cutoff else
                 'Post-cutoff snapshot: record event time does not prove provider availability before cutoff')


def build(calendar,core):
    window=verified_window(calendar);cutoff=window[2]
    manifest=read_json(ROOT/'reports/cohort_2000_modeling/feature_manifest.json')
    require(manifest['baseline_feature_allowlist']==list(FEATURES.ALLOWLIST), 'Approved schema changed')
    training,_,_=temporal.load_frozen(ROOT/'reports/cohort_2000_modeling',core)
    games=load_cohort(ROOT/'data/cohorts/cohort_2000.csv');require(len(games)==2000,'Frozen sample must remain 2000')
    vectors=[];traces=[];availability=[];cells=[];receipt_times=[];raw_fields=Counter()
    total=pre_2026=pre_cutoff_2026=excluded=inside=after=before_release=request_boundary=0
    changed_by_old_filter=[]
    for game in games:
        appid=game['AppID'];obj,status,reason,path=resolve_cache(appid,ROOT/'data/cohorts/itad/cache',[ROOT/'data/raw/itad'])
        require(status=='valid','Incomplete cache: '+appid)
        parsed,issues,other=pipeline.audit.parse_history(obj['history_response'])
        require(not issues and not other,'Silent parsing failure: '+appid)
        for raw in obj['history_response']:raw_fields.update(raw.keys())
        rows,trace=FEATURES.build_features([(int(appid),2026)],{int(appid):game},{int(appid):parsed},{2026:window})
        row=rows[0];diagnostic=trace[0];validate_vector(row,cutoff)
        earlier=[r for r in parsed if pipeline.audit.utc_stamp(r['timestamp_utc'])<cutoff]
        exact=pipeline.audit.observation(dict(timestamp=pipeline.audit.fmt(cutoff),shop={'id':61},
             deal=dict(price=dict(amount=1,amountInt=100,currency='USD'),regular=dict(amount=100,amountInt=10000,currency='USD'),cut=99)),len(parsed))
        check,_=FEATURES.build_features([(int(appid),2026)],{int(appid):game},{int(appid):earlier+[exact]},{2026:window})
        require(check[0]==row,'Feature depends on target-sale/later record')
        raw_index={r['source_record_index']:r for r in parsed}
        require(diagnostic['cutoff_violations']==0 and all(pipeline.audit.utc_stamp(raw_index[i]['timestamp_utc'])<cutoff for i in diagnostic['valid_prior_raw_indices']),'Feature cutoff violation')
        legacy=[r for r in parsed if pipeline.audit.utc_stamp(r['timestamp_utc'])<pipeline.coverage.CUTOFF]
        legacy_row,_=FEATURES.build_features([(int(appid),2026)],{int(appid):game},{int(appid):legacy},{2026:window})
        if legacy_row[0]!=row:changed_by_old_filter.append(appid)
        ev=receipt_evidence(obj,cutoff);receipt_times.append(pipeline.audit.utc_stamp(ev['history_received_at_utc']))
        late=sum(pipeline.audit.utc_stamp(r['timestamp_utc'])>=cutoff for r in parsed)
        in_sale=sum(window[2]<=pipeline.audit.utc_stamp(r['timestamp_utc'])<window[3] for r in parsed)
        post=sum(pipeline.audit.utc_stamp(r['timestamp_utc'])>=window[3] for r in parsed)
        current_year=sum(datetime(2026,1,1,tzinfo=timezone.utc)<=pipeline.audit.utc_stamp(r['timestamp_utc'])<cutoff for r in parsed)
        total+=len(parsed);pre_2026+=len(legacy);pre_cutoff_2026+=current_year;excluded+=late;inside+=in_sale;after+=post
        before_release+=diagnostic['valid_prior_observations_before_reported_release_date']
        request_boundary+=diagnostic['valid_prior_observations_at_requested_since']
        missing=[name for name in FEATURES.ALLOWLIST if row[name] is None]
        availability.append(dict(appid=appid,game_name=game['Name'],cutoff_utc=pipeline.audit.fmt(cutoff),cache_path=str(path.relative_to(ROOT)),
              successful_empty_history=not obj['history_response'],raw_records=len(parsed),qualifying_prior_price_records=row['prior_price_record_count'],
              qualifying_prior_discounts=row['prior_discount_count'],pre_cutoff_2026_records=current_year,
              excluded_at_or_after_cutoff=late,excluded_in_sale_records=in_sale,excluded_post_sale_records=post,
              latest_qualifying_prior_timestamp=diagnostic['latest_valid_prior_timestamp'],
              missing_feature_count=len(missing),missing_feature_names=json.dumps(missing),event_time_vector_reconstructable=True,
              all_15_values_nonmissing=not missing,**ev,
              latest_prior_timestamp_conflict=diagnostic['latest_valid_timestamp_conflict'],
              days_from_snapshot_receipt_after_cutoff=(receipt_times[-1]-cutoff).total_seconds()/86400))
        for name in FEATURES.ALLOWLIST:
            static=name in FEATURES.STATIC
            cells.append(dict(appid=appid,feature=name,value=row[name],missing=row[name] is None,
                  calculation_reconstructable=True,valid_type_range=True,prediction_cutoff_utc=pipeline.audit.fmt(cutoff),
                  historical_availability='Reported historical release date assumed accurate/stable' if static else
                     'Demonstrated by pre-cutoff response receipt' if ev['cache_snapshot_received_before_cutoff'] else 'Event-time only; provider availability unverified',
                  point_in_time_availability_proven=False if static else ev['provider_available_before_cutoff_demonstrated']))
        vectors.append(row);traces.append(diagnostic)
    require(len(vectors)==2000 and len(cells)==30000 and len({r['appid'] for r in vectors})==2000,'Wrong audit size')
    missingness=[]
    for name in FEATURES.ALLOWLIST:
        values=[r[name] for r in vectors if r[name] is not None];lo=float(training[name].min());hi=float(training[name].max())
        missingness.append(dict(feature=name,total_games=2000,missing=2000-len(values),missing_percent=100*(2000-len(values))/2000,
                   observed_min=min(values) if values else None,observed_median=statistics.median(values) if values else None,
                   observed_max=max(values) if values else None,training_2023_2025_min=lo,training_2023_2025_max=hi,
                   values_outside_training_range=sum(value<lo or value>hi for value in values),
                   availability='Reported release-date assumption' if name in FEATURES.STATIC else 'Provider point-in-time availability unverified'))
    # Inspection only: do not transform with learned preprocessors, fit or predict.
    model_root=ROOT/'reports/cohort_2000_models';saved=read_json(model_root/'checksums.json')
    require(all(digest(model_root/name)==sha for name,sha in saved.items()),'Frozen Phase 7A output changed')
    selected=read_json(model_root/'selection.json');model=core.joblib.load(model_root/'selected_model.joblib')
    require(selected['selected_model']=='xgboost' and selected['threshold']==.5,'Selection changed')
    require(list(model[:-1].get_feature_names_out())==list(FEATURES.ALLOWLIST),'Fitted schema differs')
    for key,value in selected['selected_configuration'].items():require(model.named_steps['classifier'].get_params()[key]==value,'XGBoost configuration differs')
    matrix=core.numeric_predictors(core.pd.DataFrame(vectors))
    require(matrix.shape==(2000,15) and not core.np.isinf(matrix.to_numpy()).any(),'Incompatible predictor matrix')
    summary=dict(total_games=2000,total_predictor_cells=30000,event_time_reconstructable_vectors=2000,
       complete_nonmissing_vectors=sum(r['all_15_values_nonmissing'] for r in availability),
       vectors_with_missing_values=sum(not r['all_15_values_nonmissing'] for r in availability),
       games_with_prior_price_observations=sum(r['qualifying_prior_price_records']>0 for r in availability),
       games_with_prior_discount_observations=sum(r['qualifying_prior_discounts']>0 for r in availability),
       successful_empty_histories=sum(r['successful_empty_history'] for r in availability),
       demonstrated_pre_cutoff_cache_snapshots=sum(r['cache_snapshot_received_before_cutoff'] for r in availability),
       fully_point_in_time_proven_vectors=0,raw_history_records=total,pre_2026_records=pre_2026,
       pre_cutoff_2026_records=pre_cutoff_2026,excluded_at_or_after_cutoff_records=excluded,
       excluded_sale_window_records=inside,excluded_after_sale_records=after,
       raw_record_field_counts=dict(raw_fields),first_record_availability_timestamps_present=False,
       earliest_history_receipt_utc=pipeline.audit.fmt(min(receipt_times)),latest_history_receipt_utc=pipeline.audit.fmt(max(receipt_times)),
       event_time_cutoff_violations=0,post_cutoff_removal_and_exact_boundary_insertion_invariant_vectors=2000,
       latest_prior_conflict_games=sum(r['latest_prior_timestamp_conflict'] for r in availability),
       valid_prior_records_before_reported_release=before_release,valid_prior_records_at_since_boundary=request_boundary,
       vectors_changed_if_old_january_2026_filter_used=len(changed_by_old_filter),old_filter_affected_appids=changed_by_old_filter,
       prediction_scope='Retrospective event-time pre-sale reconstruction using later snapshots; not a prospective forecast or verified point-in-time dataset',
       computationally_feasible=True,verified_point_in_time_exercise_feasible=False,
       api_requests=0,models_fitted=0,predictions_generated=0)
    compatibility=dict(predictor_names=list(FEATURES.ALLOWLIST),predictor_order_matches=True,predictor_types_compatible=True,
       missing_handling='Existing median imputation; refit medians on 2023–2025 only in Phase 8B. No imputation fitted in this audit.',
       frozen_xgboost_configuration=selected['selected_configuration'],classification_threshold=.5,
       saved_model_preserved_sha256=digest(model_root/'selected_model.joblib'),
       necessary_adapters=['Pass explicit verified {2026: window} to unchanged feature core; use full parsed histories without historical wrapper Jan-2026 truncation',
                           'Use existing XGBoost pipeline constructor in a cohort-aware runner accepting 2023–2025; existing fit helpers reject that year set',
                           'Write new refit model/features/predictions with retrospective and provider-availability flags; do not overwrite Phase 7 artifacts'],
       original_historical_calendar_and_feature_definitions_unchanged=True)
    return dict(vectors=vectors,provenance=traces,availability=availability,cells=cells,missingness=missingness,
                summary=summary,compatibility=compatibility,calendar=calendar)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sale-dates',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();destination=args.output_dir.resolve()
    require(destination.is_relative_to(ROOT/'reports') and not destination.exists(),'Choose a new reports directory')
    require(not any(p.is_symlink() for p in [args.output_dir.absolute(),*args.output_dir.absolute().parents]),'Symlink output forbidden')
    runtime=Path('/private/tmp/steam-2026-feasibility-runtime');runtime.mkdir(exist_ok=True)
    os.environ['MPLCONFIGDIR']=str(runtime)
    import tempfile
    tempfile.tempdir=str(runtime)
    def guard(event,values):
        if event in ('socket.connect','socket.getaddrinfo'):raise RuntimeError('Offline cache audit; no HTTP')
        if event=='subprocess.Popen':raise OSError('External commands forbidden')
        if event=='open' and (values[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            if isinstance(values[0],(str,bytes,os.PathLike)):
                p=Path(os.fsdecode(values[0])).resolve();require(p.is_relative_to(destination) or p.is_relative_to(runtime),'Writes confined to new reports/runtime')
        if event in ('os.remove','os.rename','os.mkdir','os.rmdir','os.symlink','os.link','os.chmod','os.utime'):
            for value in values[:2] if event in ('os.rename','os.link') else values[:1]:
                if isinstance(value,(str,bytes,os.PathLike)):
                    p=Path(os.fsdecode(value)).resolve();require(p.is_relative_to(destination) or p.is_relative_to(runtime),'Mutations confined to new reports/runtime')
    sys.addaudithook(guard)
    baseline=read_json(ROOT/'tests/scalable_artifact_hashes.json')
    files={p for folder in ('data','reports','models') for p in (ROOT/folder).rglob('*') if p.is_file()};files.update(ROOT/name for name in baseline)
    before={str(p.relative_to(ROOT)):digest(p) for p in files}
    core=temporal.cores()
    with frozen_model_guard(core):result=build(read_json(args.sale_dates),core)
    require(all(digest(ROOT/name)==sha for name,sha in before.items()),'Preexisting artifact changed')
    destination.mkdir()
    for filename,key in [('audit_feature_values.csv','vectors'),('game_availability.csv','availability'),
                          ('game_feature_availability.csv','cells'),('feature_missingness.csv','missingness')]:
        write_csv(destination/filename,result[key])
    for filename,key in [('verified_sale_dates.json','calendar'),('feature_provenance.json','provenance'),
                          ('feasibility_summary.json','summary'),('model_compatibility.json','compatibility')]:
        (destination/filename).write_text(json.dumps(core.clean(result[key]),indent=2,sort_keys=True,allow_nan=False)+'\n')
    validation=dict(preserved_input_files=len(before),preservation_sha256=before,protected_artifacts_preserved_this_phase=len(baseline),
       historical_baseline_matches=sum(before[name]==value['sha256'] for name,value in baseline.items()),
       journal=Journal(ROOT/'data/cohorts/itad/cache',3816,readonly=True).counts(),
       source_sha256={name:digest(ROOT/name) for name in ('src/audit_2026_feasibility.py','src/07_build_autumn_features.py','src/cohort_pipeline.py','src/09_train_ensemble_models.py')},
       no_api_calls=True,no_training=True,no_predictions=True,no_feature_definition_or_cohort_changes=True,
       event_time_boundary_invariance=True,provider_availability_not_assumed=True)
    (destination/'validation.json').write_text(json.dumps(validation,indent=2,sort_keys=True)+'\n')
    (destination/'checksums.json').write_text(json.dumps({p.name:digest(p) for p in sorted(destination.iterdir()) if p.is_file()},indent=2,sort_keys=True)+'\n')
    print(json.dumps({name:value for name,value in result['summary'].items() if name!='old_filter_affected_appids'}))


if __name__=='__main__':main()
