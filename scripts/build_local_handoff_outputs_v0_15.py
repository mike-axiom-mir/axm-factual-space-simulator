from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"output"/"local_handoff"
OUT.mkdir(parents=True,exist_ok=True)
T=ROOT/"assets"/"demo_templates"
(OUT/"LOCAL_HANDOFF_REPORT.html").write_text((T/"LOCAL_HANDOFF_REPORT.html").read_text(encoding="utf-8"),encoding="utf-8")
example=json.loads((T/"BUILDER_CAPABILITY_DECLARATION_EXAMPLE.json").read_text(encoding="utf-8"))
(OUT/"BUILDER_CAPABILITY_DECLARATION_EXAMPLE.json").write_text(json.dumps(example,indent=2,ensure_ascii=False),encoding="utf-8")
print("Local handoff report and capability declaration example rebuilt.")
