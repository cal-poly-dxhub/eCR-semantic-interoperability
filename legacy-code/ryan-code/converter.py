from fhir.resources.patient import Patient
from fhir.resources.humanname import HumanName
from fhir.resources.fhirtypes import Date
import xml.etree.ElementTree as ET

with open("./samplecda.xml" , 'r') as f:
  cda = f.read()

root = ET.fromstring(cda)
namespace = {'cda': 'urn:hl7-org:v3'}
patient_path = 'ClinicalDocument.recordTarget.patientRole'

patient_gender_entity = root.find(".//cda:recordTarget/cda:patientRole/cda:patient/cda:administrativeGenderCode", namespaces=namespace)
patient_name = root.find(".//cda:recordTarget/cda:patientRole/cda:patient/cda:name/cda:given", namespaces=namespace).text
patient_birth_entity = root.find(".//cda:recordTarget/cda:patientRole/cda:patient/cda:birthTime", namespaces=namespace)

gender_code = patient_gender_entity.attrib["code"]
birthdate = patient_birth_entity.attrib['value']

date = Date(int(birthdate[0:4]),int(birthdate[4:6]), int(birthdate[6:]) )

pat = Patient( birthDate=date, gender=gender_code, name=[HumanName(given=[patient_name])])
print(pat.json())