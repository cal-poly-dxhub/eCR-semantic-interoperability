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

import re

objects = {'encounters': [], 'observations' : [], 'conditions' : []}
encounter_ids = ['2.16.840.1.113883.10.20.22.2.22.1', '2.16.840.1.113883.10.20.22.4.49', '2.16.840.1.113883.10.20.22.4.41']
encounter_loincs = ['46240-8']
condition_ids = ['2.16.840.1.113883.10.20.22.2.5.1']
condition_loincs = ['11450-4']
observation_ids = ['2.16.840.1.113883.10.20.22.2.3.1', '2.16.840.1.113883.10.20.22.2.17', '2.16.840.1.113883.10.20.22.4.27', '1.3.6.1.4.1.19376.1.5.3.1.3.4']
observation_loincs = ['30954-2', '29762-2', '141-2', '627-0', '18855-7']

system_urls = {
  "snomed ct": "http://snomed.info/sct",
  "icd10": "http://hl7.org/fhir/sid/icd-10",
  "icd9": "http://hl7.org/fhir/sid/icd-9",
  "loinc": "http://loinc.org",
  "intelligent medical objects problemit": "http://imohealth.com/codesystem/problemit",
  "ucum (unified code for units of measure)": "http://unitsofmeasure.org",
  "cvx (vaccine administered codes)": "http://hl7.org/fhir/sid/cvx",
  "rxnorm": "http://www.nlm.nih.gov/research/umls/rxnorm",
  "national drug codes (ndc)": "http://hl7.org/fhir/sid/ndc",
  "current procedural terminology (cpt)": "http://hl7.org/fhir/sid/cpt",
  "unified code for units of measure (ucum)": "http://hl7.org/fhir/sid/ucum",
  "laboratory observation identifiers": "http://hl7.org/fhir/sid/lab",
  "dcm (dicom codes)": "http://hl7.org/fhir/sid/dcm",
  "national cancer institute thesaurus (nci)": "http://hl7.org/fhir/sid/nci",
  "us social security number": "http://hl7.org/fhir/sid/us-ssn",
  "activity codes": "http://hl7.org/fhir/sid/act",
  "hl7 version 2 code system for acknowledgment codes": "http://terminology.hl7.org/CodeSystem/v2-0008",
  "insurance plan codes": "http://hl7.org/fhir/sid/plan",
  "iso country codes (iso3166-1)": "http://hl7.org/fhir/sid/iso3166-1",
  "iso language codes (iso639-2)": "http://hl7.org/fhir/sid/iso639-2",
  "iso currency codes (iso4217)": "http://hl7.org/fhir/sid/iso4217"
}


def collect_code_strings(data):
    """
    Recursively look for 'code' keys with string values, but only include
    those strings that contain at least one numeric character.
    """
    results = []

    def recurse(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "author":
                    # Skip recursion if the key is 'author'
                    continue
                if k == "code":
                    # If the 'code' key is directly a string, check for numbers.
                    if isinstance(v, str) and re.search(r'\d', v):  # Contains at least one digit
                        results.append(v)
                    elif isinstance(v, dict) or isinstance(v, list):
                        recurse(v)
                elif isinstance(v, (dict, list)):
                    recurse(v)

        elif isinstance(obj, list):
            for item in obj:
                recurse(item)

    # Start the recursion
    recurse(data)
    return results

def collect_cond_codes(cond):
  r = []
  codes = cond['code']['coding']
  for code in codes:
    r.append(code.get('code'))
  return r

def tester(file, cond):
  cond = json.loads(cond)
  file_codes= collect_code_strings(file)
  cond_codes = collect_cond_codes(cond)

  file_codes = list(set(file_codes))
  cond_codes = list(set(cond_codes))
  for fc in file_codes:
    if fc not in cond_codes:
      print(fc)


def get_subject(cda_header: dict) -> dict:
  record_target = cda_header.get("recordTarget", {})
  if isinstance(record_target, list):
    record_target = record_target[0] if record_target else {}

  patient_role = record_target.get("patientRole", {})
  if isinstance(patient_role, list):
    patient_role = patient_role[0] if patient_role else {}

  patient_id = "unknown-patient"
  pid_data = patient_role.get("id")

  if isinstance(pid_data, list) and pid_data:
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

  given_name = "Unknown"
  family_name = "Unknown"

  patient_data = patient_role.get("patient", {})
  name_data = patient_data.get("name")

  def get_text_field(val):
    if isinstance(val, dict):
      return val.get("content", "Unknown")
    elif isinstance(val, list):
      parts = []
      for item in val:
        if isinstance(item, dict):
          parts.append(item.get("content", "Unknown"))
        else:
          parts.append(str(item))
      return " ".join(x for x in parts if x)
    elif isinstance(val, str):
      return val
    return "Unknown"

  def parse_name_dict(name_dict: dict):
    g = get_text_field(name_dict.get("given"))
    f = get_text_field(name_dict.get("family"))
    return g, f

  if isinstance(name_data, list) and name_data:
    given_name, family_name = parse_name_dict(name_data[0])
  elif isinstance(name_data, dict):
    given_name, family_name = parse_name_dict(name_data)

  display_name = f"{given_name} {family_name}".strip()
  return {
    "reference": f"Patient/{patient_id}",
    "display": display_name
  }

def create_encounter(encounter: dict):
  ...

def traverse_condition(condition: dict) -> dict:
  ...

def traverse_prob_list(section: dict, path="ClinicalDocument.component.structuredBody.component.section"):
  acts = []
  entry = section.get("entry")
  if isinstance(entry, dict):
    act = entry.get("act")
    if isinstance(act, dict):
      acts.append((act, path + ".entry.act"))
  elif isinstance(entry, list):
    for i, e in enumerate(entry):
      if isinstance(e, dict):
        act = e.get("act")
        if isinstance(act, dict):
          acts.append((act, f"{path}.entry[{i}].act"))
  return acts



def extract_single_entryrelationship(relation: dict, path: str) -> dict:
  """
  Parses a single <observation>, <procedure>, <substanceAdministration>, <act>, or <organizer>.
  Returns a dict containing a list of codings under ["parsedCodings"], plus any status/negation info.
  """
  info = {}
  statement_types = ["observation", "procedure", "substanceAdministration", "act", "organizer"]
  statement_node = None
  for stype in statement_types:
    node = relation.get(stype)
    if node is not None and isinstance(node, dict):
      statement_node = (node, stype)
      break

  info["parsedCodings"] = []
  if statement_node:
    node, stype = statement_node
    _extract_status_and_negation(node, info)
    _append_codings_from_block(node.get("code", {}), info["parsedCodings"], path + f".{stype}.code")
    _append_codings_from_block(node.get("value", {}), info["parsedCodings"], path + f".{stype}.value")
  else:
    _extract_status_and_negation(relation, info)
    top_value = relation.get("value", {})
    if isinstance(top_value, dict):
      _append_codings_from_block(top_value, info["parsedCodings"], path + ".value")

  return info

def _extract_status_and_negation(node: dict, info: dict) -> None:
  """
  Extracts 'statusCode' and 'negationInd' from the node and stores them in info.
  """
  status_code = node.get("statusCode", {})
  if isinstance(status_code, dict):
    info["statusCode"] = status_code.get("code", "")
  if node.get("negationInd") == "true":
    info["negationInd"] = True

def _append_codings_from_block(block: dict, codings_list: list, path: str) -> None:
  """
  Pulls codes, displayName, translations, etc. from <code> or <value> blocks and
  appends them into codings_list. Also stores the 'xmlPath'.
  """
  if not isinstance(block, dict) or not block:
    return

  primary_coding = {
    "code": block.get("code", ""),
    "display": block.get("displayName", ""),  # Changed from "displayName" to "display"
    "codeSystem": block.get("codeSystem", ""),
    "codeSystemName": block.get("codeSystemName", ""),
    "xmlPath": path
  }
  codings_list.append(primary_coding)

  translation_data = block.get("translation")
  if translation_data:
    if isinstance(translation_data, list):
      for t in translation_data:
        codings_list.append({
          "code": t.get("code", ""),
          "display": t.get("displayName", ""),  # Changed from "displayName" to "display"
          "codeSystem": t.get("codeSystem", ""),
          "codeSystemName": t.get("codeSystemName", ""),
          "xmlPath": path + ".translation"
        })
    else:
      codings_list.append({
        "code": translation_data.get("code", ""),
        "display": translation_data.get("displayName", ""),  # Changed from "displayName" to "display"
        "codeSystem": translation_data.get("codeSystem", ""),
        "codeSystemName": translation_data.get("codeSystemName", ""),
        "xmlPath": path + ".translation"
      })

def prob_list_entryrelationship(entryrelationship, path):
  """
  Collects data from <entryRelationship> blocks.
  Returns a list of dicts, each containing "parsedCodings" and any other extracted info.
  """
  if isinstance(entryrelationship, list):
    relations = []
    for i, relation in enumerate(entryrelationship):
      obs = relation.get("observation", {})
      subpath = f"{path}[{i}].observation"
      relations.append(extract_single_entryrelationship(obs, subpath))
    return relations
  elif isinstance(entryrelationship, dict):
    obs = entryrelationship.get("observation", {})
    return [extract_single_entryrelationship(obs, path + ".observation")]

def create_problem_list(file: dict, condition_data: dict):
  all_acts = traverse_prob_list(condition_data)
  all_codings = []
  seen_codes = set()
  status = ""
  for act, act_path in all_acts:
    maybe_status = act.get("statusCode", {}).get("code", "")
    if not status and maybe_status:
      status = maybe_status
    if "entryRelationship" in act:
      relations = prob_list_entryrelationship(act["entryRelationship"], act_path + ".entryRelationship")
      for relation in relations:
        for coding in relation["parsedCodings"]:
          code = coding.get("code", "")
          display = coding.get("display", "")
          system = coding.get("codeSystemName", "")  # Changed from "systemName" to "codeSystemName"
          system = system_urls.get(system.lower(), system)
          if code and code not in seen_codes:
            # Ensure 'display' is not empty
            if not display:
              display = "Unknown"
            all_codings.append({
              "code": code,
              "display": display,
              "system": system
            })
            seen_codes.add(code)

  subject_data = get_subject(file)
  patient_id = subject_data.get("reference", "unknown-patient")
  patient_name = subject_data.get("display", "Unknown")

  condition_dict = {
    "resourceType": "Condition",
    "subject": {
      "reference": f"Patient/{patient_id}",
      "display": patient_name
    },
    "clinicalStatus": {"coding": []},
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
    "active","recurrence","relapse","inactive","remission","resolved","unknown"
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

  try:
    c_obj = Condition.parse_obj(condition_dict)
    output = json.loads(c_obj.json())
    # Now re-add the path info
    path_list = []
    for act, act_path in all_acts:
      if "entryRelationship" in act:
        relations = prob_list_entryrelationship(act["entryRelationship"], act_path + ".entryRelationship")
        for relation in relations:
          for coding in relation["parsedCodings"]:
            path_list.append(coding.get("xmlPath"))

    # Re-add path to output codes if lengths match
    if "code" in output and "coding" in output["code"]:
      codings_in_output = output["code"]["coding"]
      for i, c in enumerate(codings_in_output):
        if i < len(path_list):
          c["path"] = path_list[i]
    print(json.dumps(output))

    # print(tester(condition_data, json.dumps(output)))
  except Exception as e:
    print(json.dumps({"error": str(e)}))

def create_condition(file: dict, condition: dict):
  if condition['code']['code'] == '11450-4':
    create_problem_list(file, condition)

def create_observation(observation: dict):
  ...

def traverse_components(file: dict, components: list[dict]):
  for component in components:
    if 'code' in component.get('section',{}).keys() and isinstance(component['section']['code'], dict):
      if component['section']['code']['code'] in encounter_loincs:
        create_encounter(component['section'])
      elif component['section']['code']['code'] in condition_loincs:
        create_condition(file, component['section'])
      elif component['section']['code']['code'] in observation_loincs:
        create_observation(component['section'])

def traverse(file: dict):
  for element in file:
    if element == 'component':
      traverse_components(file, file[element]['structuredBody']['component'])

def get_direct_text(element):
  return ''.join([t for t in element.contents if isinstance(t, str)]).strip()

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
      child_content = xml_to_dict(child)
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


  # -- DELIM this code does notdiscriminate

# def extract_single_entryrelationship(relation: dict) -> dict:
#   """
#   Parses a single entryRelationship block for known statement types,
#   or falls back to top-level <value>.
#   """
#   info = {}
#   statement_types = ["observation", "procedure", "substanceAdministration", "act", "organizer"]
#   statement_node = None

#   for stype in statement_types:
#     node = relation.get(stype)
#     if node and isinstance(node, dict):
#       statement_node = node
#       break

#   info["parsedCodings"] = []

#   if statement_node:
#     _extract_status_and_negation(statement_node, info)
#     _append_codings_from_block(statement_node.get("code", {}), info["parsedCodings"])
#     _append_codings_from_block(statement_node.get("value", {}), info["parsedCodings"])
#   else:
#     _extract_status_and_negation(relation, info)
#     top_value = relation.get("value", {})
#     if isinstance(top_value, dict):
#       _append_codings_from_block(top_value, info["parsedCodings"])

#   return info

# def _extract_status_and_negation(node: dict, info: dict) -> None:
#   """Extracts 'verificationStatus' from statusCode, sets to 'refuted' if negationInd='true'."""
#   status_code = node.get("statusCode", {})
#   if isinstance(status_code, dict):
#     info["verificationStatus"] = status_code.get("code", "")
#   if node.get("negationInd") == "true":
#     info["verificationStatus"] = "refuted"

# def _append_codings_from_block(block: dict, codings_list: list) -> None:
#   """Appends primary coding plus translations from <translation>."""
#   if not isinstance(block, dict) or not block:
#     return
#   primary_coding = {
#     "code": block.get("code", ""),
#     "display": block.get("displayName", ""),
#     "systemName": block.get("codeSystemName", ""),
#     "systemOid": block.get("codeSystem", "")
#   }
#   codings_list.append(primary_coding)
#   translation_data = block.get("translation")
#   if translation_data:
#     if isinstance(translation_data, list):
#       for t in translation_data:
#         codings_list.append({
#           "code": t.get("code", ""),
#           "display": t.get("displayName", ""),
#           "systemName": t.get("codeSystemName", ""),
#           "systemOid": t.get("codeSystem", "")
#         })
#     else:
#       codings_list.append({
#         "code": translation_data.get("code", ""),
#         "display": translation_data.get("displayName", ""),
#         "systemName": translation_data.get("codeSystemName", ""),
#         "systemOid": translation_data.get("codeSystem", "")
#       })

# def prob_list_entryrelationship(entryrelationship):
#   if isinstance(entryrelationship, list):
#     relations = []
#     for relation in entryrelationship:
#       relations.append(extract_single_entryrelationship(relation))
#     return relations
#   elif isinstance(entryrelationship, dict):
#     return [extract_single_entryrelationship(entryrelationship)]

# def create_problem_list(file: dict, condition_data: dict):
  # all_acts = traverse_prob_list(condition_data)
  # all_codings = []
  # seen_codes = set()
  # status = ""

  # for act in all_acts:
  #   maybe_status = act.get("statusCode", {}).get("code", "")
  #   if not status and maybe_status:
  #     status = maybe_status
  #   if "entryRelationship" in act:
  #     relations = prob_list_entryrelationship(act["entryRelationship"])
  #     for relation in relations:
  #       for coding in relation["parsedCodings"]:
  #         code = coding.get("code", "")
  #         display = coding.get("display", "")
  #         system = coding.get("systemName", "")
  #         system = system_urls.get(system.lower(), system)
  #         if code and display and system and code not in seen_codes:
  #           all_codings.append({
  #             "code": code,
  #             "display": display,
  #             "system": system
  #           })
  #           seen_codes.add(code)
  #         elif code and system and code not in seen_codes:
  #           all_codings.append({
  #             "code": code,
  #             "system": system
  #           })
  #           seen_codes.add(code)
  #         translation = coding.get("translation")
  #         if translation:
  #           t_code = translation.get("code", "")
  #           t_display = translation.get("display", "")
  #           t_system = translation.get("systemName", "")
  #           if t_code and t_display and t_system and t_code not in seen_codes:
  #             all_codings.append({
  #               "code": t_code,
  #               "display": t_display,
  #               "system": t_system
  #             })
  #             seen_codes.add(t_code)

  # subject_data = get_subject(file)
  # patient_id = subject_data.get("reference", "unknown-patient")
  # patient_name = subject_data.get("display", "Unknown")

  # condition_dict = {
  #   "resourceType": "Condition",
  #   "subject": {
  #     "reference": f"Patient/{patient_id}",
  #     "display": patient_name
  #   },
  #   "clinicalStatus": {"coding": []},
  #   "category": [
  #     {
  #       "coding": [
  #         {
  #           "system": "http://terminology.hl7.org/CodeSystem/condition-category",
  #           "code": "problem-list-item",
  #           "display": "Problem List Item"
  #         }
  #       ]
  #     }
  #   ]
  # }

  # allowed_statuses = [
  #   "active", "recurrence", "relapse", "inactive",
  #   "remission", "resolved", "unknown"
  # ]
  # if status and status.lower() in allowed_statuses:
  #   condition_dict["clinicalStatus"] = {
  #     "coding": [
  #       {
  #         "code": status.lower(),
  #         "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
  #         "display": status.capitalize()
  #       }
  #     ]
  #   }

  # if all_codings:
  #   condition_dict["code"] = {"coding": all_codings}

  # try:
  #   condition = Condition.parse_obj(condition_dict)
  #   # print(condition.json(indent=2))
  #   print(tester(condition_data, condition.json()))
  # except Exception as e:
  #   print(json.dumps({"error": str(e)}))

#-- NEW DELIM