from fhir.resources.patient import Patient
from fhir.resources.patient import PatientContact
from fhir.resources.humanname import HumanName
from fhir.resources.fhirtypes import Date
from fhir.resources.fhirtypes import ContactPointType
from fhir.resources.extension import Extension
from fhir.resources.address import Address
from fhir.resources.condition import Condition

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


def create_encounter(encounter: dict):
  ...

def traverse_condition(condition: dict) -> dict:
  ...
  
def traverse_prob_list(condition: dict) -> dict:
  info = None
  if 'entry' in condition.keys():
    info = condition['keys']
  if info is None:
    return {}
  return info

def extract_single_entryrelationship(relation: dict) -> dict:
  info = {}
  


#extract info from either the list or single dict of entry relationship
def prob_list_entryrelationship(entryrelationship):
  entry_info = []
  if isinstance(entryrelationship, list):
    coding = []
    for relation in entryrelationship:
      coding.append(extract_single_entryrelationship(relation))

  elif isinstance(entryrelationship, dict):
    extract_single_entryrelationship(entryrelationship)

def create_problem_list(condition: dict):
  info = traverse_prob_list(condition)
  status = None
  #cant rely on this
  if 'statusCode' in info.keys():
    status = info['statusCode']['code']
  if 'entryRelationship' in info.keys():
    prob_list_entryrelationship(info['entryRelationship'])
    

  
def create_condition(condition: dict):
  if condition['code']['code'] == '11450-4':
    create_problem_list(condition)
  
  

  


def create_observation(observation: dict):
  ...


def traverse_components(components: list[dict]):
  for component in components:
    #cant rely on this
    if 'code' in component.keys() and isinstance(component['code'], dict):
      if component['code']['code'] in encounter_loincs:
        create_encounter(component)
      elif component['code']['code'] in condition_loincs:
        create_condition(component)
      elif component['code']['code'] in observation_loincs:
        create_observation(component)

def traverse (file: dict):
  for element in file:
    #cant rely on this
    if element == 'component':
      traverse_components(file[element]['structuredBody']['component'])


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