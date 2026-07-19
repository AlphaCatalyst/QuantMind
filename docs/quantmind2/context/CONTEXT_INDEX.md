# QuantMind 2.0 Context Index

Project ID: `quantmind2`  
Architecture version: `v1`  
Indexed base commit: `65389084b36abd1ee0b5b9f3577b44a2dd6ff3cb`

## Mandatory read order

1. [Project Charter](PROJECT_CHARTER.md)
2. [Architecture v1](../architecture/QUANTMIND_2_ARCHITECTURE_V1.md)
3. [Current State](CURRENT_STATE.md)
4. [Handoff](HANDOFF.md)
5. [ADR Index](../adr/ADR_INDEX.md)
6. [Component Catalog](COMPONENT_CATALOG.md)
7. [Implementation Runs](../implementation/README.md)
8. Current code, Git status, and relevant tests
9. [ADR-0011 Tushare-only authority](../adr/ADR-0011-tushare-only-data-authority-and-legacy-retirement.md)
10. [Tushare authority record](../data/TUSHARE_AUTHORITY_V1.json)

## Context documents

- [Known Issues](KNOWN_ISSUES.md)
- [Roadmap](ROADMAP.md)
- [Terminology](TERMINOLOGY.md)
- [Data Semantics](DATA_SEMANTICS.md)
- [API Contract Index](API_CONTRACT_INDEX.md)
- [Database Schema Index](DATABASE_SCHEMA_INDEX.md)

The JSON peer, `context_index.json`, is the machine-readable bootstrap. A
successful validator result proves structural consistency only; code and
runtime claims still require direct verification.
