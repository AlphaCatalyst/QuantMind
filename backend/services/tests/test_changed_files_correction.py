import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tools.quantmind2.changed_files_correction import (
    OUTPUT, ROOT, SCHEMA, TARGET_COMMIT, TARGET_MANIFEST, TARGET_RUN_ID,
    build_correction, canonical_inventory_hash, classify_inventory,
    git_inventory, validate_correction,
)


def test_inventory_classification_covers_missing_unexpected_hash_and_type_mismatch():
    base={"path":"a","change_type":"modified","before_hash":"1"*64,"after_hash":"2"*64,"previous_path":None}
    missing={**base,"path":"missing"}; unexpected={**base,"path":"unexpected"}
    wrong_hash={**base,"after_hash":"3"*64}; wrong_type={**base,"change_type":"added","before_hash":None}
    m,u,x=classify_inventory([base,unexpected],[base,missing]); assert m==[missing] and u==[unexpected] and x==[]
    _,_,x=classify_inventory([wrong_hash],[base]); assert x[0]["recorded"]["after_hash"]=="3"*64
    _,_,x=classify_inventory([wrong_type],[base]); assert x[0]["recorded"]["change_type"]=="added"


def test_git_inventory_handles_add_modify_delete_rename_and_raw_bytes(tmp_path):
    subprocess.run(["git","init","-q",tmp_path],check=True)
    subprocess.run(["git","-C",tmp_path,"config","user.email","test@example.invalid"],check=True)
    subprocess.run(["git","-C",tmp_path,"config","user.name","test"],check=True)
    (tmp_path/"modify").write_bytes(b"before\r\n"); (tmp_path/"delete").write_bytes(b"gone\n"); (tmp_path/"old").write_bytes(b"rename\x00bytes")
    subprocess.run(["git","-C",tmp_path,"add","."],check=True); subprocess.run(["git","-C",tmp_path,"commit","-qm","base"],check=True)
    base=subprocess.check_output(["git","-C",tmp_path,"rev-parse","HEAD"],text=True).strip()
    (tmp_path/"modify").write_bytes(b"after\r\n"); (tmp_path/"delete").unlink(); (tmp_path/"old").rename(tmp_path/"new"); (tmp_path/"added").write_bytes(b"new\n")
    subprocess.run(["git","-C",tmp_path,"add","-A"],check=True); subprocess.run(["git","-C",tmp_path,"commit","-qm","change"],check=True)
    end=subprocess.check_output(["git","-C",tmp_path,"rev-parse","HEAD"],text=True).strip()
    rows=git_inventory(tmp_path,base,end,"none"); by={x["path"]:x for x in rows}
    assert {x["change_type"] for x in rows}=={"added","modified","deleted","renamed"}
    committed_before=subprocess.check_output(["git","-C",tmp_path,"show",f"{base}:modify"])
    assert by["modify"]["before_hash"]==hashlib.sha256(committed_before).hexdigest()
    assert by["modify"]["before_hash"]!=hashlib.sha256((tmp_path/"modify").read_bytes()).hexdigest()
    assert by["new"]["previous_path"]=="old"


def test_real_correction_is_git_derived_stable_closed_and_preserves_target():
    payload=build_correction(); Draft202012Validator(json.loads(SCHEMA.read_text())).validate(payload)
    assert payload["target_run_id"]==TARGET_RUN_ID and payload["recorded_entry_count"]==12
    assert payload["verified_entry_count"]==35 and len(payload["missing_entries"])==23
    assert payload["unexpected_entries"]==[] and payload["mismatched_entries"]==[]
    assert payload["verified_inventory"]==sorted(payload["verified_inventory"],key=lambda x:x["path"])
    assert payload["verified_inventory_sha256"]==canonical_inventory_hash(payload["verified_inventory"])
    assert TARGET_MANIFEST not in payload["actual_paths"]
    committed=subprocess.check_output(["git","show",f"{TARGET_COMMIT}:{TARGET_MANIFEST}"])
    assert hashlib.sha256(committed).hexdigest()==payload["immutable_target_manifest_sha256"]


def test_published_correction_exactly_matches_git_and_schema():
    payload=json.loads(OUTPUT.read_text()); assert validate_correction(payload)==payload


def test_correction_relationship_contract_is_corrects_only():
    run_root=ROOT/"docs/quantmind2/implementation/runs/2026/2026-07"
    candidates=list(run_root.glob("QM2-P0-009F-*/manifest.json"))
    if not candidates: pytest.skip("009F Manifest is created after focused correction tests")
    manifest=json.loads(candidates[0].read_text()); assert len(manifest["relationships"])==1
    relationship=manifest["relationships"][0]
    assert relationship["relationship_type"]=="corrects" and relationship["target_run_id"]==TARGET_RUN_ID
    assert "supersedes" not in json.dumps(manifest)
