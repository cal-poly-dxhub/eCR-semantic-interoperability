from datetime import date

from fhir.resources.humanname import HumanName
from fhir.resources.patient import Patient

json_obj: dict[str, object] = {
    "resourceType": "Patient",
    "id": "p001",
    "active": True,
    "name": [{"text": "Adam Smith"}],
    "birthDate": "1985-06-12",
}

pat = Patient.validate(json_obj)
isinstance(pat.name[0], HumanName)
print(pat.birthDate == date(year=1985, month=6, day=12))
print(pat.active)
