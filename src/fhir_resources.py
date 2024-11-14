import json

import fhir.resources.patient

for r in fhir.resources.patient.Patient.__dict__.values():
    if isinstance(r, dict) and r.get("resource_type"):
        modelfield = r.get("resource_type").default
        if modelfield == "Patient":
            nj = r.get("resource_type").__dir__
            with open("out.json", "w") as f:
                json.dump(nj, f)
