from fhir.resources.patient import Patient
from fhir.resources.patient import PatientContact
from fhir.resources.humanname import HumanName
from fhir.resources.fhirtypes import Date
from fhir.resources.fhirtypes import ContactPointType
from fhir.resources.extension import Extension
from fhir.resources.address import Address
from fhir.resources.condition import Condition
from fhir.resources import fhirtypes


from fhir_core.types import CodeType


import difflib

import boto3
from botocore.exceptions import ClientError

from bs4 import BeautifulSoup

import json

objects = {'encounters': [], 'observations' : [], 'conditions' : []}
encounter_ids = ['2.16.840.1.113883.10.20.22.2.22.1', '2.16.840.1.113883.10.20.22.4.49', '2.16.840.1.113883.10.20.22.4.41']
encounter_loincs = ['46240-8']
condition_ids = ['2.16.840.1.113883.10.20.22.2.5.1']
condition_loincs = ['11450-4']
observation_ids = ['2.16.840.1.113883.10.20.22.2.3.1', '2.16.840.1.113883.10.20.22.2.17', '2.16.840.1.113883.10.20.22.4.27', '1.3.6.1.4.1.19376.1.5.3.1.3.4']
observation_loincs = ['30954-2', '29762-2', '141-2', '627-0', '18855-7']

def get_subject(cda_header: dict) -> dict:
  patient_role = cda_header.get("recordTarget", {}).get("patientRole", {})
  patient_id = "unknown-patient"
  given_name = "Unknown"
  family_name = "Unknown"

  pid = patient_role.get("id")
  if isinstance(pid, list) and len(pid) > 0:
    patient_id = pid[0].get("root", "unknown-patient")
  elif isinstance(pid, dict):
    patient_id = pid.get("root", "unknown-patient")

  patient_data = patient_role.get("patient", {})
  name_data = patient_data.get("name")
  if isinstance(name_data, list) and len(name_data) > 0:
    given_name = name_data[0].get("given", "Unknown")
    family_name = name_data[0].get("family", "Unknown")
  elif isinstance(name_data, dict):
    given_name = name_data.get("given", "Unknown")
    family_name = name_data.get("family", "Unknown")

  display_name = f"{given_name} {family_name}"
  return {
    "reference": f"Patient/{patient_id}",
    "display": display_name
  }



def create_encounter(encounter: dict):
  ...

def traverse_condition(condition: dict) -> dict:
  ...
  
def traverse_prob_list(condition: dict) -> dict:
  info = None
  if 'entry' in condition.keys():
    info = condition['entry'].get('act',{})
  if info is None:
    return {}
  return info

# def extract_single_entryrelationship(relation: dict) -> dict:
#     info = {}
    
#     value_dict = relation.get('value', {})
#     if isinstance(value_dict, dict) and value_dict != {}:
#       info['code'] = value_dict.get('code', '')
#       info['systemName'] = value_dict.get('codeSystemName', '')
#       info['systemOid'] = value_dict.get('codeSystem', '')
#       info['display'] = value_dict.get('displayName', '')
      
#       translation_data = value_dict.get('translation')
#       if translation_data:
#         if isinstance(translation_data, list):
#           info['translations'] = []
#           for t in translation_data:
#               info['translations'].append({
#               'code': t.get('code', ''),
#               'display': t.get('displayName', ''),
#               'systemName': t.get('codeSystemName', ''),
#               'systemOid': t.get('codeSystem', '')
#               })
#         else:
#           info['translation'] = {
#             'code': translation_data.get('code', ''),
#             'display': translation_data.get('displayName', ''),
#             'systemName': translation_data.get('codeSystemName', ''),
#             'systemOid': translation_data.get('codeSystem', '')
#           }

#     status_code = relation.get('statusCode', {})
#     if isinstance(status_code, dict):
#       info['verificationStatus'] = status_code.get('code', '')
    
#     if relation.get('negationInd') == 'true':
#       info['verificationStatus'] = 'refuted'
    
#     return info

def extract_single_entryrelationship(relation: dict) -> dict:
  """
  A flexible parser that can handle nested statements (observation, procedure, etc.)
  or fallback to top-level <value>. Produces a list of codings under info["parsedCodings"].
  """
  info = {}
  statement_types = ["observation", "procedure", "substanceAdministration", "act", "organizer"]
  statement_node = None

  # Find the first known statement type in the relation
  for stype in statement_types:
    node = relation.get(stype)
    if node is not None and isinstance(node, dict):
      statement_node = node
      break

  # Initialize a list for codings
  info["parsedCodings"] = []

  if statement_node:
    # statusCode -> verificationStatus
    _extract_status_and_negation(statement_node, info)

    # Extract codings from <code> and <value>
    _append_codings_from_block(statement_node.get("code", {}), info["parsedCodings"])
    _append_codings_from_block(statement_node.get("value", {}), info["parsedCodings"])

  else:
    # Fallback: top-level usage if there's no recognized statement node
    _extract_status_and_negation(relation, info)
    top_value = relation.get("value", {})
    if isinstance(top_value, dict):
      _append_codings_from_block(top_value, info["parsedCodings"])

  return info


def _extract_status_and_negation(node: dict, info: dict) -> None:
  """Extract 'verificationStatus' from statusCode, set to 'refuted' if negationInd='true'."""
  status_code = node.get("statusCode", {})
  if isinstance(status_code, dict):
    info["verificationStatus"] = status_code.get("code", "")

  if node.get("negationInd") == "true":
    info["verificationStatus"] = "refuted"


def _append_codings_from_block(block: dict, codings_list: list) -> None:
  """
  Appends a 'primary' coding (code/systemName/display) plus any translations from <translation>.
  Each is added to codings_list as a dict with keys:
    'code', 'display', 'systemName', and optionally 'translation' or 'translations'.
  """
  if not isinstance(block, dict) or not block:
    return

  # Primary coding
  primary_coding = {
    "code": block.get("code", ""),
    "display": block.get("displayName", ""),
    "systemName": block.get("codeSystemName", ""),
    "systemOid": block.get("codeSystem", "")
  }
  codings_list.append(primary_coding)

  # Handle <translation> as list or single object
  translation_data = block.get("translation")
  if translation_data:
    if isinstance(translation_data, list):
      for t in translation_data:
        codings_list.append({
          "code": t.get("code", ""),
          "display": t.get("displayName", ""),
          "systemName": t.get("codeSystemName", ""),
          "systemOid": t.get("codeSystem", "")
        })
    else:
      codings_list.append({
        "code": translation_data.get("code", ""),
        "display": translation_data.get("displayName", ""),
        "systemName": translation_data.get("codeSystemName", ""),
        "systemOid": translation_data.get("codeSystem", "")
      })




#extract info from either the list or single dict of entry relationship
def prob_list_entryrelationship(entryrelationship):
  if isinstance(entryrelationship, list):
    relations = []
    for relation in entryrelationship:
      relations.append(extract_single_entryrelationship(relation.get('observation',{})))
    return relations

  elif isinstance(entryrelationship, dict):
    return [extract_single_entryrelationship(entryrelationship)]
  

def create_problem_list(file: dict, condition_data: dict):
  info = traverse_prob_list(condition_data)
  status = ""
  subject_data = get_subject(file)

  if "statusCode" in info:
    status = info["statusCode"].get("code", "")

  if "entryRelationship" in info:
    relations = prob_list_entryrelationship(info["entryRelationship"])

  condition_dict = {}
  patient_id = subject_data.get("id", "unknown-patient")
  patient_name = subject_data.get("name", "Unknown")
  condition_dict["subject"] = {
      "reference": f"Patient/{patient_id}",
      "display": patient_name
  }

  condition_dict['category'] = [
      {
        "coding": [
          {
            "system": "http://terminology.hl7.org/CodeSystem/condition-category",
            "code": "problem-list-item",
            "display": "Problem List Item"
          }
        ]
      }
    ]

  allowed_statuses = [
    "active", "recurrence", "relapse", "inactive",
    "remission", "resolved", "unknown"
  ]
  if status and status.lower() in allowed_statuses:
    condition_dict["clinicalStatus"] = {
      "coding": [
        {
          "code": status.lower(),
          "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
          "display": status.capitalize()
        }
      ]
    }

  if relations:
    condition_dict["code"] = {"coding": []}
    seen_codes = set()

    for relation in relations[0]['parsedCodings']:
      code = relation.get("code", "")
      display = relation.get("display", "")
      system = relation.get("systemName", "")

      if code and display and system and code not in seen_codes:
        condition_dict["code"]["coding"].append({
          "code": code,
          "display": display,
          "system": system
        })
        seen_codes.add(code)

      translation = relation.get("translation")
      if translation:
        t_code = translation.get("code", "")
        t_display = translation.get("display", "")
        t_system = translation.get("systemName", "")

        if t_code and t_display and t_system and t_code not in seen_codes:
          condition_dict["code"]["coding"].append({
            "code": t_code,
            "display": t_display,
            "system": t_system
          })
          seen_codes.add(t_code)

  condition_dict["resourceType"] = "Condition"
  condition = Condition.parse_obj(condition_dict)
  print(condition.json())

    

  
def create_condition(file:dict, condition: dict):
  if condition['code']['code'] == '11450-4':
    create_problem_list(file, condition)
  
  

  


def create_observation(observation: dict):
  ...


def traverse_components(file: dict, components: list[dict]):
  for component in components:
    #cant rely on this
    if 'code' in component.get('section',{}).keys() and isinstance(component['section']['code'], dict):
      if component['section']['code']['code'] in encounter_loincs:
        create_encounter(component['section'])
      elif component['section']['code']['code'] in condition_loincs:
        create_condition(file, component['section'])
      elif component['section']['code']['code'] in observation_loincs:
        create_observation(component['section'])

def traverse (file: dict):
  for element in file:
    #cant rely on this
    if element == 'component':
      traverse_components(file, file[element]['structuredBody']['component'])


def get_direct_text(element):
  return ''.join([t for t in element.contents if isinstance(t, str)]).strip()


#if multiple of same children, makes array with objects of each child
def xml_to_dict(element):
    data = {}

    if element.attrs:
      data.update(element.attrs)

    text = get_direct_text(element)
    if text:
      data["content"] = text

    children = [child for child in element.children if child.name]
    if children:
      for child in children:
        child_content = xml_to_dict(child) #DFS through children
        if child.name in data:
          if not isinstance(data[child.name], list):
            data[child.name] = [data[child.name]]
          data[child.name].append(child_content)
        else:
          data[child.name] = child_content

    return data

if __name__ == "__main__":
  with open ('input_xml.xml', 'r') as f:
    soup = BeautifulSoup(f.read(), 'xml')
    d = xml_to_dict(soup.ClinicalDocument)
  traverse(d)