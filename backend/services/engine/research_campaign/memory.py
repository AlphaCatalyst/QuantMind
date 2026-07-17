def sanitize_memory(events, admitted_fingerprints, admission_outcomes=(), fresh_validation_outcomes=()):
    rejected = [event["reason"] for event in events if event.get("event_type") == "proposal_rejected"]
    completed = [event for event in events if event.get("event_type") == "proposal_completed"]
    return {"schema_version": "research-memory-v1", "completed_proposal_count": len(completed),
            "known_structure_fingerprints": sorted(admitted_fingerprints),
            "recent_rejection_reasons": rejected[-8:],
            "development_feedback": [{"proposal_id": item["proposal_id"],
                "development_mean_rank_ic": item.get("development_mean_rank_ic"),
                "development_rank_icir": item.get("development_rank_icir"),
                "warning": "adaptive contaminated Development feedback; not Validation or Frozen evidence"}
                for item in completed[-8:]],
            "fresh_validation_feedback": ([{"factor_instance_id": item["factor_instance_id"],
                "outcome": "advanced_to_fresh_validation" if item["admitted"] else "not_advanced_to_fresh_validation"}
                for item in admission_outcomes] + [{"factor_instance_id": item["factor_instance_id"],
                "outcome": item["outcome"]} for item in fresh_validation_outcomes]),
            "forbidden_content": ["Frozen Test", "labels", "raw rows", "filesystem paths", "promotion state"]}
