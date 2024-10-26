import xml.etree.ElementTree as ET

from fhir.resources.patient import Patient
from fhir.resources.humanname import HumanName
from fhir.resources.fhirtypes import Date
from fhir.resources.fhirtypes import ContactPointType

from fhir_core.types import CodeType


tree = ET.parse('./input_xml.xml')
root = tree.getroot()

ET.register_namespace('', 'urn:hl7-org:v3')
namespace = {'cda': 'urn:hl7-org:v3'}

def remove_namespace(child: ET.Element):
  if '}' in child.tag:
    clean = child.tag.split('}')
    return clean[1]
  return child.tag

def create_patient(given_name, gender_code, date, marital_status, mobile_phone):
  if given_name is None:
    given_name = "NULL"
  if gender_code is None:
    gender_code = "NULL"
  if date is None:
    date = Date(0,0,0)
  if marital_status is None:
    marital_status = 'NULL'
  if mobile_phone is None:
    mobile_phone = 'NULL'
  
  return(Patient( telecom=[ContactPointType( use=CodeType('mobile'), value=mobile_phone)],birthDate=date, gender=gender_code, name=[HumanName(given=[given_name])]))


def process_patient(child: ET.Element):
  administrative_gender = child.find('.//cda:patient/cda:administrativeGenderCode', namespaces=namespace)
  name_entity = child.find('.//cda:patient/cda:name/cda:given', namespaces=namespace)
  patient_birth_entity = child.find(".//cda:patient/cda:birthTime", namespaces=namespace)
  marital_entity = child.find('.//cda:patient/cda:maritalStatusCode', namespaces=namespace)
  telecom_entites = child.findall('.//cda:telecom', namespaces=namespace)

  given_name = None
  gender_code = None
  date = None
  marital_status = None
  mobile_phone = None

  if name_entity is not None:
    given_name = name_entity.text

  if administrative_gender is not None and 'code' in administrative_gender.attrib:
    gender_code = administrative_gender.attrib['code']

  if patient_birth_entity is not None and 'value' in patient_birth_entity.attrib:
    birthdate = patient_birth_entity.attrib['value']
    date = Date(int(birthdate[0:4]),int(birthdate[4:6]), int(birthdate[6:]))

  if marital_entity is not None and 'value' in marital_entity.attrib:
    marital_status = marital_entity.attrib['value']

  if telecom_entites is not None:
    for telecom in telecom_entites:
      if 'use' in telecom.attrib and telecom.attrib['use'] == 'MC':
        mobile_phone = telecom.attrib['value']
  
  #TODO: add language communication
  patient = create_patient(given_name, gender_code, date, marital_status, mobile_phone)
  print(patient.json())



  
  

  
  

def process_record_target(record: ET.Element):
  for child in record:
    tag = remove_namespace(child)
    if tag == "patientRole":
      process_patient(child)
    


def process_child(child: ET.Element):
  tag = remove_namespace(child)
  if tag == "recordTarget":
    process_record_target(child)


def create_json(root: ET):
  if root is None:
    return
  for child in root: 
    process_child(child)

create_json(root)
