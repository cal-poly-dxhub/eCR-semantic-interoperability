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

# def get_subject(cda_header: dict) -> dict:
#   patient_role = cda_header.get("recordTarget", {}).get("patientRole", {})
#   patient_id = "unknown-patient"
#   given_name = "Unknown"
#   family_name = "Unknown"

#   pid = patient_role.get("id")
#   if isinstance(pid, list) and len(pid) > 0:
#     patient_id = pid[0].get("root", "unknown-patient")
#   elif isinstance(pid, dict):
#     patient_id = pid.get("root", "unknown-patient")

#   patient_data = patient_role.get("patient", {})
#   name_data = patient_data.get("name")
#   if isinstance(name_data, list) and len(name_data) > 0:
#     given_name = name_data[0].get("given", "Unknown")
#     family_name = name_data[0].get("family", "Unknown")
#   elif isinstance(name_data, dict):
#     given_name = name_data.get("given", "Unknown")
#     family_name = name_data.get("family", "Unknown")

#   display_name = f"{given_name} {family_name}"
#   return {
#     "reference": f"Patient/{patient_id}",
#     "display": display_name
#   }

def get_subject(cda_header: dict) -> dict:
    """
    Extract a subject (patient) reference and display from a parsed CDA header structure.
    Returns a dict like:
      {
        "reference": "Patient/{some_id}",
        "display": "GivenName FamilyName"
      }
    """

    # Safely get the recordTarget element (could be dict or list).
    record_target = cda_header.get("recordTarget", {})
    if isinstance(record_target, list):
        record_target = record_target[0] if record_target else {}

    # Get the patientRole element (could also be dict or list).
    patient_role = record_target.get("patientRole", {})
    if isinstance(patient_role, list):
        patient_role = patient_role[0] if patient_role else {}

    #
    # 1) Get the patient ID
    #
    patient_id = "unknown-patient"
    pid_data = patient_role.get("id")

    if isinstance(pid_data, list) and pid_data:
        # If there's more than one <id>, just pick the first
        first_id = pid_data[0]
        patient_id = (
            first_id.get("root") or 
            first_id.get("extension") or 
            "unknown-patient"
        )
    elif isinstance(pid_data, dict):
        patient_id = (
            pid_data.get("root") or 
            pid_data.get("extension") or 
            "unknown-patient"
        )

    #
    # 2) Extract name information (Given and Family).
    #
    given_name = "Unknown"
    family_name = "Unknown"

    patient_data = patient_role.get("patient", {})
    name_data = patient_data.get("name")

    # Helper to unify how we extract the "string" from name fields.
    def get_text_field(val):
        """
        Returns a string from either:
          - a plain string
          - a dict with {"content": "..."}
          - a list of such
        Defaults to "Unknown" if we can't parse it.
        """
        if isinstance(val, dict):
            # e.g. { "content": "Mickey" }
            return val.get("content", "Unknown")
        elif isinstance(val, list):
            # If it's a list of dicts or strings, join them
            # e.g. [{"content": "Mickey"}, {"content": "Michael"}] => "Mickey Michael"
            parts = []
            for item in val:
                if isinstance(item, dict):
                    parts.append(item.get("content", "Unknown"))
                else:
                    # item might be a plain string
                    parts.append(str(item))
            # Filter out "Unknown" if possible, or just join them all
            return " ".join(x for x in parts if x)
        elif isinstance(val, str):
            return val
        # If none of the above, fallback
        return "Unknown"

    def parse_name_dict(name_dict: dict):
        # e.g. name_dict = {
        #   "use": "L",
        #   "given": {"content": "Mickey"},
        #   "family": {"content": "Mouse"}
        # }
        g = get_text_field(name_dict.get("given"))
        f = get_text_field(name_dict.get("family"))
        return g, f

    if isinstance(name_data, list) and name_data:
        # Take the first <name> block
        given_name, family_name = parse_name_dict(name_data[0])
    elif isinstance(name_data, dict):
        given_name, family_name = parse_name_dict(name_data)

    #
    # 3) Construct the final result
    #
    display_name = f"{given_name} {family_name}".strip()
    return {
        "reference": f"Patient/{patient_id}",
        "display": display_name
    }



def create_encounter(encounter: dict):
  ...

def traverse_condition(condition: dict) -> dict:
  ...


def traverse_prob_list(condition: dict) -> list[dict]:
  acts = []
  entry = condition.get("entry")

  if isinstance(entry, dict):
    act = entry.get("act")
    if isinstance(act, dict):
      acts.append(act)

  elif isinstance(entry, list):
    for e in entry:
      if isinstance(e, dict):
        act = e.get("act")
        if isinstance(act, dict):
          acts.append(act)

  return acts




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
  

# def create_problem_list(file: dict, condition_data: dict):
#   info = traverse_prob_list(condition_data)
#   status = ""
#   subject_data = get_subject(file)
#   relations = None

#   if "statusCode" in info:
#     status = info["statusCode"].get("code", "")

#   if "entryRelationship" in info:
#     relations = prob_list_entryrelationship(info["entryRelationship"])

#   condition_dict = {}
#   patient_id = subject_data.get("id", "unknown-patient")
#   patient_name = subject_data.get("name", "Unknown")
#   condition_dict["subject"] = {
#       "reference": f"Patient/{patient_id}",
#       "display": patient_name
#   }
#   condition_dict["clinicalStatus"] = {
#       "coding": [
#         {
          
#         }
#       ]
#     }

#   condition_dict['category'] = [
#       {
#         "coding": [
#           {
#             "system": "http://terminology.hl7.org/CodeSystem/condition-category",
#             "code": "problem-list-item",
#             "display": "Problem List Item"
#           }
#         ]
#       }
#     ]

#   allowed_statuses = [
#     "active", "recurrence", "relapse", "inactive",
#     "remission", "resolved", "unknown"
#   ]
#   if status and status.lower() in allowed_statuses:
#     condition_dict["clinicalStatus"] = {
#       "coding": [
#         {
#           "code": status.lower(),
#           "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
#           "display": status.capitalize()
#         }
#       ]
#     }

#   if relations:
#     condition_dict["code"] = {"coding": []}
#     seen_codes = set()

#     for relation in relations[0]['parsedCodings']:
#       code = relation.get("code", "")
#       display = relation.get("display", "")
#       system = relation.get("systemName", "")

#       if code and display and system and code not in seen_codes:
#         condition_dict["code"]["coding"].append({
#           "code": code,
#           "display": display,
#           "system": system
#         })
#         seen_codes.add(code)

#       translation = relation.get("translation")
#       if translation:
#         t_code = translation.get("code", "")
#         t_display = translation.get("display", "")
#         t_system = translation.get("systemName", "")

#         if t_code and t_display and t_system and t_code not in seen_codes:
#           condition_dict["code"]["coding"].append({
#             "code": t_code,
#             "display": t_display,
#             "system": t_system
#           })
#           seen_codes.add(t_code)

#   condition_dict["resourceType"] = "Condition"
#   condition = Condition.parse_obj(condition_dict)
#   print(condition.json())

    
def create_problem_list(file: dict, condition_data: dict):
  all_acts = traverse_prob_list(condition_data)
  all_codings = []
  seen_codes = set()
  status = ""

  for act in all_acts:
    maybe_status = act.get("statusCode", {}).get("code", "")
    if not status and maybe_status:
      status = maybe_status

    if "entryRelationship" in act:
      relations = prob_list_entryrelationship(act["entryRelationship"])
      for relation in relations:
        for coding in relation["parsedCodings"]:
          code = coding.get("code", "")
          display = coding.get("display", "")
          system = coding.get("systemName", "")
          if code and display and system and code not in seen_codes:
            all_codings.append({
              "code": code,
              "display": display,
              "system": system
            })
            seen_codes.add(code)

          translation = coding.get("translation")
          if translation:
            t_code = translation.get("code", "")
            t_display = translation.get("display", "")
            t_system = translation.get("systemName", "")
            if t_code and t_display and t_system and t_code not in seen_codes:
              all_codings.append({
                "code": t_code,
                "display": t_display,
                "system": t_system
              })
              seen_codes.add(t_code)

  subject_data = get_subject(file)
  patient_id = subject_data.get("reference", "unknown-patient")
  patient_name = subject_data.get("display", "Unknown")

  condition_dict = {
    "resourceType": "Condition",
    "subject": {
      "reference": f"Patient/{patient_id}",
      "display": patient_name
    },
    "clinicalStatus": {
      "coding": []
    },
    "category": [
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
  }

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

  if all_codings:
    condition_dict["code"] = {"coding": all_codings}

  condition = Condition.parse_obj(condition_dict)
  print(condition.json(indent=2))

  
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
  with open ('input_xml3.xml', 'r') as f:
    soup = BeautifulSoup(f.read(), 'xml')
    d = xml_to_dict(soup.ClinicalDocument)

  traverse(d)