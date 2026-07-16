import json
from pathlib import Path


def factor_template_schema():
    path = Path(__file__).parents[4] / "docs/quantmind2/implementation/schemas/factor_template_v1.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))
