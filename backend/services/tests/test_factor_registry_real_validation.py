import os
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

import pytest

from backend.services.engine.factor_registry import active_factors, build_entries_from_evidence, default_promotion_policy, promotion_candidates, publish_snapshot
from backend.services.engine.factor_registry.errors import RegistryEvidenceError
from backend.services.engine.factor_validation.errors import ValidationArtifactError


ROOT=Path(__file__).resolve().parents[3]
OPT=Path(os.getenv("QM2_FACTOR_OPTIMIZATION_REAL_ROOT","/private/tmp/qm2-p0-005-optimization"))
VAL=Path(os.getenv("QM2_FACTOR_VALIDATION_REAL_ARTIFACT_ROOT","/private/tmp/qm2-p0-006-validation/artifacts"))
RESULT="fvr_b9f247e42487267754d5e6128beb4f90a379b77853462b6ca25f0f2918c51ab0"
SELECTION="fvs_f679a63089f076c11315f522f4d59dc8248731863ec6aafc02b70c9762819e9c"
FROZEN="fvt_734478fcc0291910667321669e5b5293f64594efe6f0e5b1334779f4d921c787"
pytestmark=pytest.mark.skipif(not OPT.is_dir() or not VAL.is_dir(),reason="real immutable Registry evidence is unavailable")


def test_real_fourteen_entries_lineage_status_and_exact_replay(tmp_path):
    policy=default_promotion_policy()
    entries=build_entries_from_evidence(repository_root=ROOT,optimization_root=OPT,validation_root=VAL,
        validation_result_id=RESULT,selection_id=SELECTION,frozen_result_id=FROZEN,policy=policy)
    assert len(entries)==14 and len({x.factor_instance_id for x in entries})==14
    assert Counter(x.status.value for x in entries)==Counter({"validation_rejected":10,"validation_passed_not_selected":1,"frozen_rejected":3})
    assert {x.family_id for x in entries}=={"ft_8174c2c375fe504dfada1d0cdb953ac94469ec8c017276382f365bfebccad8b5","ft_c75dc9f65292b6711a939bb178c2b48455df07653708508b315395fc3b2e2453"}
    frozen=[x for x in entries if x.frozen_result_id]
    assert len(frozen)==3 and all(x.frozen_result_id==FROZEN for x in frozen)
    assert all(x.candidate_selection_id==SELECTION and x.validation_result_id==RESULT for x in entries)
    assert all("correction_artifact" in x.evidence_hashes for x in entries)
    first=publish_snapshot(tmp_path,policy,entries); second=publish_snapshot(tmp_path,policy,entries)
    assert second.exact_existing and first.registry_snapshot_id==second.registry_snapshot_id
    assert promotion_candidates(first)==() and active_factors(first)==()


def test_parameter_lineage_mismatch_is_rejected_even_with_updated_file_hash(tmp_path):
    copied=tmp_path/"optimization"; shutil.copytree(OPT,copied)
    study=copied/"fos_969d431e553ad29d1d7bcdd4d912a6ab92471b5c4faf833a18abe2607baa1cb2"
    manifest_path=study/"manifest.json"; manifest=json.loads(manifest_path.read_text())
    trial_id=manifest["trial_ids"][0]; trial_path=study/"trials"/f"{trial_id}.json"
    trial=json.loads(trial_path.read_text()); key=next(iter(trial["parameters"])); trial["parameters"][key]+=1
    trial_path.write_text(json.dumps(trial,sort_keys=True,separators=(",",":"))+"\n")
    manifest["file_hashes"][f"trials/{trial_id}.json"]=hashlib.sha256(trial_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest,sort_keys=True,separators=(",",":"))+"\n")
    with pytest.raises(RegistryEvidenceError,match="parameter lineage"):
        build_entries_from_evidence(repository_root=ROOT,optimization_root=copied,validation_root=VAL,
            validation_result_id=RESULT,selection_id=SELECTION,frozen_result_id=FROZEN,policy=default_promotion_policy())


def test_metric_source_tampering_is_rejected_by_validation_authority(tmp_path):
    copied=tmp_path/"validation"; shutil.copytree(VAL,copied)
    result=copied/"results"/RESULT; trial_path=next((result/"trials").glob("*.json"))
    trial=json.loads(trial_path.read_text()); trial["validation_oriented_metrics"]["mean_rank_ic"]=99
    trial_path.write_text(json.dumps(trial,sort_keys=True,separators=(",",":"))+"\n")
    with pytest.raises(ValidationArtifactError):
        build_entries_from_evidence(repository_root=ROOT,optimization_root=OPT,validation_root=copied,
            validation_result_id=RESULT,selection_id=SELECTION,frozen_result_id=FROZEN,policy=default_promotion_policy())
