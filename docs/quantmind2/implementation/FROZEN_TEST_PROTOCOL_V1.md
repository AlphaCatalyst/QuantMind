# Frozen Test Protocol v1

The threat is adaptive research after observing 2026 labels. Agent, Campaign
Memory, DSL and Optimizer have no label or Frozen reader. Ordinary validation
can read only Train and Validation labels. The only frozen-label reader is the
independent `factor_validation.frozen` module.

Access requires a `FrozenTestAccessContext` containing protocol, Validation
Dataset, already-published Candidate Selection, reason and requester. It does
not accept a Template, parameter space or replacement candidate list. Protocol
`qm2-frozen-2026-v1` locks the Selection and Dataset on first publication;
subsequent calls can only validate and replay the exact result. A different
candidate set conflicts. Poor results cannot trigger reselection or tuning in
the same protocol.

The final immutable result is
`fvt_734478fcc0291910667321669e5b5293f64594efe6f0e5b1334779f4d921c787`.
Oriented mean RankIC for Validation ranks 1–3 was respectively -0.004275,
0.000909 and 0.004020 across 111 valid dates. Results are reported without
changing the Selection history. They are not a backtest or a future-return
guarantee and are insufficient by themselves for production promotion.

If another research cycle is required after this observation, it must use a
new Experiment/protocol and a new, explicitly unobserved Frozen period. The
old artifact remains immutable and is marked contaminated for any subsequent
adaptive use; it is never overwritten.
