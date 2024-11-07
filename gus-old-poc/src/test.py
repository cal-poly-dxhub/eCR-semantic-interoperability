# import xml.etree.ElementTree as ET

from fhir.resources.patient import Patient
from fhir.resources.humanname import HumanName
from fhir.resources.fhirtypes import Date
from fhir.resources.fhirtypes import ContactPointType
from fhir.resources.extension import Extension

from fhir_core.types import CodeType

import difflib

import boto3
from botocore.exceptions import ClientError

from bs4 import BeautifulSoup

import json

fill_in_patient_cot_prompt: str = """<prompt>
You are a medical data analyst specializing in HL7 V3 CDA, FHIR data, LOINC, and SNOMED codes.

You will be provided with:
1. A JSON object representing a FHIR Patient data type.
2. JSON objects of the HL7 V3 CDA data extracted from the original document.

**HL7 V3 CDA JSON Structure:**
- **Children Elements:** Contain text along with LOINC and SNOMED codes that provide context to the text.

**Your Task:**
1. **Update FHIR Patient JSON:**
   - **Cross-Reference Data:** Compare the HL7 V3 CDA JSON with the provided FHIR Patient JSON.
   - **Fill Missing Data:** Populate any missing fields in the FHIR Patient JSON based on the HL7 V3 CDA JSON content.
   - **Adhere to FHIR Standards:** Ensure the outputted JSON strictly follows FHIR standards.
   - **Exclude Reasoning:** Do **not** include your reasoning process or any unnecessary preamble in the output.

2. **Provide Chain of Thought for Each Field:**
   - For every field populated in both the Patient and Observation JSON objects, include a corresponding reasoning statement explaining **how** and **from where** the information was derived.
   - Ensure that the chain of thought is mapped directly to each field, maintaining a clear association.
   -For each field you are providing output for, also include the direct JSON object you looked at to infer from. Literally show where you got this information from. Also include you chain of thought as well, not just where you got your info from.

**Output Requirements:**
- **Structured JSON Response:** Provide a single JSON object with two main sections:
  - `"data"`: Contains the updated FHIR Patient JSON object
  - `"chain_of_thought"`: Contains reasoning for each field within the Patient JSON object.
- **No Additional Text:** Do not include any explanations, comments, or additional text outside the JSON structure.
- ** I ***MUST*** be able to do JSON.loads(<your response>) without editing your response at all in python without it breaking, so the module can easily parse your JSON response into a dictionary

**Patient JSON Object Fields:**
Ensure the main fields of the Patient JSON include only the following:
- `active`
- `address`
- `birthDate`
- `communication` (Languages used to communicate with the patient about their health)
- `contact` (Contact parties such as guardian, partner, or friend)
- `deceasedBoolean`
- `deceasedDateTime`
- `gender`
- `generalPractitioner`
- `identifier`
- `link`
- `managingOrganization`
- `maritalStatus`
- `extension`
- `multipleBirthBoolean`
- `multipleBirthInteger`
- `name`
- `photo`
- `telecom` (Contact details for the individual)

**Extension Field Guidelines:**
- **Additional Information:** Include details such as Sexual Orientation, Race, Ethnicity, etc., in the `extension` field following standard FHIR practices.
- **Excluding Unknown Values:** 
  - If a field is marked as unknown, uses a null flavor, or indicates that the value is unknown or not applicable, **exclude** it from the JSON entirely.
  - Do **not** input it as "unknown," "null flavor," or any other placeholder.
  - It is acceptable for the `extension` field to remain empty if no extensions are necessary.

**Other Notes:**
- **Excluding Unknowns in Main Fields:** In addition to the `extension` field, if any value in the main part of the JSON object is unknown or uses a null flavor, **exclude** it from the JSON entirely.
  - Do **not** include it as "unknown," "null flavor," or any other placeholder.

**Provided Data Sections:**
- **Patient JSON Object:**
  --PATIENT--

- **Patient Role Information:**
  --PR--

- **Social History Section:**
  --SH--

**Output Format Example:**
```json
{
  "data": {
    "patient": {
      "active": true,
      "address": [ /* Address objects */ ],
      "birthDate": "1980-01-01",
      // ... other patient fields
    },
  "chain_of_thought": {
    "patient": {
      "active": "Determined from the Patient Role Information section where the patient's status is marked as active.",
      "address": "Extracted from the Patient Role Information section, which provides the patient's residential address.",
      "birthDate": "Derived from the main Patient JSON Object's birthDate field.",
      // ... reasoning for other patient fields
    },
  }
}
</prompt>"""

fill_in_patient_prompt: str = """<prompt>
You are a medical data analyst specializing in HL7 V3 CDA, FHIR data, LOINC, and SNOMED codes.

You will be provided with:
1. A JSON object representing a FHIR Patient data type.
2. JSON objects of the HL7 V3 CDA data extracted from the original document.

**HL7 V3 CDA JSON Structure:**
- **Children Elements:** Contain text along with LOINC and SNOMED codes that provide context to the text.

**Your Task:**
- **Cross-Reference Data:** Compare the HL7 V3 CDA JSON with the provided FHIR Patient JSON.
- **Fill Missing Data:** Populate any missing fields in the FHIR Patient JSON based on the HL7 V3 CDA JSON content.
- **Adhere to FHIR Standards:** Ensure the outputted JSON strictly follows FHIR standards.
- **Exclude Reasoning:** Do **not** include your reasoning process or any unnecessary preamble in the output.

**Output Requirements:**
- **Single JSON Object:** Only output the updated FHIR Patient JSON object.
- **No Additional Text:** Do not include any explanations, comments, or additional text outside the JSON.

**Patient JSON Object Fields:**
Ensure the main fields of the Patient JSON include only the following:
- `active`
- `address`
- `birthDate`
- `communication` (Languages used to communicate with the patient about their health)
- `contact` (Contact parties such as guardian, partner, or friend)
- `deceasedBoolean`
- `deceasedDateTime`
- `gender`
- `generalPractitioner`
- `identifier`
- `link`
- `managingOrganization`
- `maritalStatus`
- `extension`
- `multipleBirthBoolean`
- `multipleBirthInteger`
- `name`
- `photo`
- `telecom` (Contact details for the individual)

**Extension Field Guidelines:**
- **Additional Information:** Include details such as Sexual Orientation, Race, Ethnicity, etc., in the `extension` field following standard FHIR practices.
- **Excluding Unknown Values:** 
  - If a field is marked as unknown, uses a null flavor, or indicates that the value is unknown or not applicable, **exclude** it from the JSON entirely.
  - Do **not** input it as "unknown," "null flavor," or any other placeholder.
  - It is acceptable for the `extension` field to remain empty if no extensions are necessary.

**Other Notes:**
- **Excluding Unknowns in Main Fields:** In addition to the `extension` field, if any value in the main part of the JSON object is unknown or uses a null flavor, **exclude** it from the JSON entirely.
  - Do **not** include it as "unknown," "null flavor," or any other placeholder.

**Provided Data Sections:**
- **Patient JSON Object:**
  --PATIENT--

- **Patient Role Information:**
  --PR--

- **Social History Section:**
  --SH--
</prompt>"""

fill_in_patient_and_observations_prompt: str = """<prompt>
You are a medical data analyst specializing in HL7 V3 CDA, FHIR data, LOINC, and SNOMED codes.

You will be provided with:
1. A JSON object representing a FHIR Patient data type.
2. JSON objects of the HL7 V3 CDA data extracted from the original document.

**HL7 V3 CDA JSON Structure:**
- **Children Elements:** Contain text along with LOINC and SNOMED codes that provide context to the text.

**Your Task:**
1. **Update FHIR Patient JSON:**
   - **Cross-Reference Data:** Compare the HL7 V3 CDA JSON with the provided FHIR Patient JSON.
   - **Fill Missing Data:** Populate any missing fields in the FHIR Patient JSON based on the HL7 V3 CDA JSON content.
   - **Adhere to FHIR Standards:** Ensure the outputted JSON strictly follows FHIR standards.
   - **Exclude Reasoning:** Do **not** include your reasoning process or any unnecessary preamble in the output.

2. **Create FHIR Observation JSON Objects:**
   - **Extract Social History:** From the Social History section (`--SH--`), create corresponding FHIR Observation JSON objects.
   - **Populate Values:** Use appropriate values from the Social History, mapping them correctly to FHIR Observation fields using LOINC and SNOMED codes.
    - **Adhere to FHIR Standards:** Ensure the outputted JSON strictly follows FHIR standards.
   - **Exclude Unknown Values:** If any value in the Social History is unknown, not applicable, or uses a null flavor, **exclude** that observation entirely.

**Output Requirements:**
- **Structured JSON Response:** Provide a JSON object containing two keys:
  - `"patient"`: The updated FHIR Patient JSON object.
  - `"observations"`: An array of FHIR Observation JSON objects derived from the Social History.
- **No Additional Text:** Do not include any explanations, comments, or additional text outside the JSON.
- ** I ***MUST*** be able to do JSON.loads() without editing your response at all in python without it breaking, so the module can easily parse your JSON response into a dictionary

**Patient JSON Object Fields:**
Ensure the main fields of the Patient JSON include only the following:
- `active`
- `address`
- `birthDate`
- `communication` (Languages used to communicate with the patient about their health)
- `contact` (Contact parties such as guardian, partner, or friend)
- `deceasedBoolean`
- `deceasedDateTime`
- `gender`
- `generalPractitioner`
- `identifier`
- `link`
- `managingOrganization`
- `maritalStatus`
- `extension`
- `multipleBirthBoolean`
- `multipleBirthInteger`
- `name`
- `photo`
- `telecom` (Contact details for the individual)

**Extension Field Guidelines:**
- **Additional Information:** Include details such as Sexual Orientation, Race, Ethnicity, etc., in the `extension` field following standard FHIR practices.
- **Excluding Unknown Values:** 
  - If a field is marked as unknown, uses a null flavor, or indicates that the value is unknown or not applicable, **exclude** it from the JSON entirely.
  - Do **not** input it as "unknown," "null flavor," or any other placeholder.
  - It is acceptable for the `extension` field to remain empty if no extensions are necessary.

**Other Notes:**
- **Excluding Unknowns in Main Fields:** In addition to the `extension` field, if any value in the main part of the JSON object is unknown or uses a null flavor, **exclude** it from the JSON entirely.
  - Do **not** include it as "unknown," "null flavor," or any other placeholder.

**Provided Data Sections:**
- **Patient JSON Object:**
  --PATIENT--

- **Patient Role Information:**
  --PR--

- **Social History Section:**
  --SH--

**Output Format Example:**
```json
{
  "patient": { /* Updated FHIR Patient JSON */ },
  "observations": [
    { /* FHIR Observation JSON Object 1 */ },
    { /* FHIR Observation JSON Object 2 */ },
    // ... more observations
  ]
}
"""

fill_in_patient_and_observations_with_cot_prompt: str = """<prompt>
You are a medical data analyst specializing in HL7 V3 CDA, FHIR data, LOINC, and SNOMED codes.

You will be provided with:
1. A JSON object representing a FHIR Patient data type.
2. JSON objects of the HL7 V3 CDA data extracted from the original document.

**HL7 V3 CDA JSON Structure:**
- **Children Elements:** Contain text along with LOINC and SNOMED codes that provide context to the text.

**Your Task:**
1. **Update FHIR Patient JSON:**
   - **Cross-Reference Data:** Compare the HL7 V3 CDA JSON with the provided FHIR Patient JSON.
   - **Fill Missing Data:** Populate any missing fields in the FHIR Patient JSON based on the HL7 V3 CDA JSON content.
   - **Adhere to FHIR Standards:** Ensure the outputted JSON strictly follows FHIR standards.
   - **Exclude Reasoning:** Do **not** include your reasoning process or any unnecessary preamble in the output.

2. **Create FHIR Observation JSON Objects:**
   - **Extract Social History:** From the Social History section, create corresponding FHIR Observation JSON objects.
   - **Populate Values:** Use appropriate values from the Social History, mapping them correctly to FHIR Observation fields using LOINC and SNOMED codes.
   - **Exclude Unknown Values:** If any value in the Social History is unknown, not applicable, or uses a null flavor, **exclude** that observation entirely.

3. **Provide Chain of Thought for Each Field:**
   - For every field populated in both the Patient and Observation JSON objects, include a corresponding reasoning statement explaining **how** and **from where** the information was derived.
   - Ensure that the chain of thought is mapped directly to each field, maintaining a clear association.

**Output Requirements:**
- **Structured JSON Response:** Provide a single JSON object with two main sections:
  - `"data"`: Contains the updated FHIR Patient JSON object and an array of FHIR Observation JSON objects.
  - `"chain_of_thought"`: Contains reasoning for each field within the Patient and Observation JSON objects.
- **No Additional Text:** Do not include any explanations, comments, or additional text outside the JSON structure.
- ** I ***MUST*** be able to do JSON.loads(<your response>) without editing your response at all in python without it breaking, so the module can easily parse your JSON response into a dictionary

**Provided Data Sections:**
- **Patient JSON Object:**
  --PATIENT--

- **Patient Role Information:**
  --PR--

- **Social History Section:**
  --SH--

**Output Format Example:**
```json
{
  "data": {
    "patient": {
      "active": true,
      "address": [ /* Address objects */ ],
      "birthDate": "1980-01-01",
      // ... other patient fields
    },
    "observations": [
      {
        "resourceType": "Observation",
        "status": "final",
        "code": { /* LOINC and SNOMED codes */ },
        "valueQuantity": { /* Value details */ },
        // ... other observation fields
      },
      // ... more observations
    ]
  },
  "chain_of_thought": {
    "patient": {
      "active": "Determined from the Patient Role Information section where the patient's status is marked as active.",
      "address": "Extracted from the Patient Role Information section, which provides the patient's residential address.",
      "birthDate": "Derived from the main Patient JSON Object's birthDate field.",
      // ... reasoning for other patient fields
    },
    "observations": [
      {
        "resourceType": "Observation": "Identified as an observation related to social history from the Social History section.",
        "status": "final": "Status set to 'final' as the information is confirmed and complete.",
        "code": { 
          "system": "http://loinc.org",
          "code": "XYZ",
          "display": "Smoking Status"
        }: "Mapped from the LOINC code associated with smoking status in the Social History section.",
        "valueQuantity": {
          "value": 0,
          "unit": "pack/year",
          "system": "http://unitsofmeasure.org",
          "code": "pack/year"
        }: "Extracted the smoking history value indicating 0 pack-years from the Social History section.",
        // ... reasoning for other observation fields
      },
      // ... reasoning for more observations
    ]
  }
}
"""

create_ecr_bundle_prompt: str = """<prompt>
You are a medical data analyst specializing in FHIR resources and standards.

**Your Task:**

- **Input:**
  - A FHIR Patient JSON object.
  - An array of FHIR Observation JSON objects.

- **Output:**
  - A FHIR Bundle resource of type "document" that includes:
    - A FHIR Composition as the first entry.
    - The Patient resource.
    - Any Practitioner or related resources (if applicable).
    - The Observation resources.
  - The Bundle and all contained resources must be correctly linked using `fullUrl` and `reference` fields.
  - Ensure that the Composition correctly references all included resources in its `section` entries.

**Instructions:**

1. **Create the FHIR Composition:**

   - **Resource Type:** `Composition`
   - **Mandatory Fields:**
     - `id`: A unique identifier (e.g., `"composition-1"`).
     - `status`: Set to `"final"`.
     - `type`: A `CodeableConcept` representing the kind of composition (e.g., ECR report type).
     - `subject`: Reference to the Patient resource.
     - `date`: The composition date (use the current date or extract from input if available).
     - `author`: Reference(s) to the author(s) of the composition (e.g., Practitioner).
     - `title`: A human-readable title for the composition (e.g., `"Electronic Case Report"`).
     - `section`: An array of sections, each containing a `title` and `entry` referencing included resources.

2. **Assemble the FHIR Bundle:**

   - **Resource Type:** `Bundle`
   - **Type:** `"document"`
   - **Entries:**
     - **First Entry:** The Composition resource.
     - **Subsequent Entries:** The Patient resource, Practitioner resource(s) if available, and all Observation resources.
   - **fullUrl:** Use `urn:uuid:` prefixes with unique identifiers for each resource (e.g., `"urn:uuid:patient-123"`).
   - **Link References:** Ensure that all references within resources (e.g., in `subject`, `author`, `entry`) correctly point to the corresponding `fullUrl` identifiers.

3. **Ensure FHIR Compliance:**

   - **Validity:** The output JSON must conform to FHIR standards for Bundle and Composition resources.
   - **Required Fields:** Include all mandatory fields for each resource type.
   - **Referencing:** Properly reference resources within the Bundle using `Reference` objects.

4. **Formatting:**

   - **JSON Structure:** Ensure the JSON is correctly formatted with proper nesting, commas, and brackets.
   - **No Additional Text:** Do not include any explanations, comments, or text outside the JSON output.

**Provided Data:**

- **Patient JSON Object:**
  --PATIENT--

- **Observations Array:**
  --OBSERVATIONS--

**Output Example:**

```json
{
  "resourceType": "Bundle",
  "type": "document",
  "entry": [
    {
      "fullUrl": "urn:uuid:composition-1",
      "resource": {
        "resourceType": "Composition",
        "id": "composition-1",
        "status": "final",
        "type": {
          "coding": [
            {
              "system": "http://loinc.org",
              "code": "60591-5",
              "display": "Public Health Case Report"
            }
          ],
          "text": "Electronic Case Report"
        },
        "subject": {
          "reference": "urn:uuid:patient-123"
        },
        "date": "2024-11-06",
        "author": [
          {
            "reference": "urn:uuid:practitioner-456"
          }
        ],
        "title": "Electronic Case Report",
        "section": [
          {
            "title": "Patient Information",
            "entry": [
              {
                "reference": "urn:uuid:patient-123"
              }
            ]
          },
          {
            "title": "Observations",
            "entry": [
              {
                "reference": "urn:uuid:observation-789"
              }
              // Add references to other observations here
            ]
          }
        ]
      }
    },
    {
      "fullUrl": "urn:uuid:patient-123",
      "resource": --PATIENT--
    },
    // Include Practitioner resource if available
    {
      "fullUrl": "urn:uuid:practitioner-456",
      "resource": {
        "resourceType": "Practitioner",
        "id": "456",
        "name": [
          {
            "given": ["FirstName"],
            "family": "LastName"
          }
        ]
      }
    },
    // Include all Observation resources
    {
      "fullUrl": "urn:uuid:observation-789",
      "resource": --OBSERVATION-1--
    }
    // Add additional Observation entries here
  ]
}
"""


# tree = ET.parse('./input_xml.xml')
# root = tree.getroot()

# ET.register_namespace('', 'urn:hl7-org:v3')
# namespace = {'cda': 'urn:hl7-org:v3'}
objects = {}


def create_patient(given_name, gender_code, date, marital_status, mobile_phone, info: dict):
  #could prob make this more flexible
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
  
  return Patient(
    extension=[],
    telecom=[ContactPointType(use=CodeType('mobile'), value=mobile_phone)],
    birthDate=info['birthdate'],
    gender=info['gender'],
    name=[HumanName(given=[info['name']['given']], family=info['name']['family'])]
)

def get_bedrock_response(prompt: str) -> str:
  client = boto3.client("bedrock-runtime", region_name="us-west-2")  # type: ignore
  model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
  conversation = [{"role": "user", "content": [{"text": prompt}]}]

  try:
    response = client.converse(  # type: ignore
      modelId=model_id,
      messages=conversation,
      inferenceConfig={"maxTokens": 4096, "temperature": 1.0, "topP": 0.9},
      )
    response_text = response["output"]["message"]["content"][0]["text"]
    return response_text

  except (ClientError, Exception) as e:
    print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
    exit(1)

def fill_in_patient(patient_role, social_history):
  prompt = fill_in_patient_cot_prompt.replace('--PR--',patient_role).replace('--PATIENT--',objects['Patient'].json()).replace('--SH--',social_history)
  response = get_bedrock_response(prompt)
  print(response)
  return json.loads(response)
  

def create_bundle(ecr_info: dict):
  prompt = create_ecr_bundle_prompt.replace('--PATIENT--',json.dumps(ecr_info['patient'])).replace('--OBSERVATIONS--', json.dumps(ecr_info['observations']))
  response = get_bedrock_response(prompt)
  print(response)

def cda_patient_create(file: dict) -> dict:
  given_name = None
  gender_code = None
  date = None
  marital_status = None
  mobile_phone = None
  
  patient: dict = file.get("recordTarget", {}).get("patientRole", {}).get("patient")
  patientrole: dict = file.get("recordTarget", {}).get("patientRole", {})
  telecom: dict = file.get("recordTarget", {}).get("patientRole", {}).get("telecom", {})
  components: dict = file.get("component", {}).get("structuredBody", {}).get("component", {})

  info = {}

  if patient:
    if "name" in patient:
      given_name = patient["name"]["given"]["content"]
      info['name'] = {}
      info['name']['given'] = given_name
      info['name']['family'] = patient['name']['family']['content']
    if "administrativeGenderCode" in patient:
      gender_code = patient["administrativeGenderCode"]["code"]
      if gender_code.lower() == "m":
        info['gender'] = 'Male'
      elif gender_code.lower() == 'f':
        info['gender'] = 'Female'
    if "birthTime" in patient:
      date = patient["birthTime"]["value"]
      date = Date(int(date[0:4]),int(date[4:6]), int(date[6:]))
      info['birthdate'] = date

  if telecom:
    info['telecom'] = []
    for comm in telecom:
      if "use" in comm and comm["use"] == "MC":
        info['telecom'].append({'system': "phone", 'value' : comm['value'], 'use' : 'mobile'})
        mobile_phone = comm["value"]

  socialHistory = None
  if components: # look for social history
    for component in components:
      if component["section"]["code"]["code"] == "29762-2":
        socialHistory = component
        break
  
  
  

  objects["Patient"] = create_patient(given_name, gender_code, date, marital_status, mobile_phone, info)
  return {"patientrole" : patientrole, "socialhistory" : socialHistory}


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
  # create_json(root)
  
  with open ('input_xml.xml', 'r') as f:
    soup = BeautifulSoup(f.read(), 'xml')
    d = xml_to_dict(soup.ClinicalDocument)
  patient_fields_dict = cda_patient_create(d)
  print(objects['Patient'].json())
  # print(patient_fields_dict['socialhistory'])
  # print("***MANUAL PATIENT:*** \n\n ", objects['Patient'].json())
  # print("\n\n****MODEL FILL:****\n\n")
  # case_data = fill_in_patient(str(patient_fields_dict ["patientrole"]), str(patient_fields_dict ["socialhistory"]))
  # print("\n\n***BUNDLE:****\n\n\n")
  # create_bundle(case_data)

  #https://www.hl7.org/fhir/us/ecr/2018Sep/StructureDefinition-eicr-composition-definitions.html\

#RAG to get guidelines?


#https://build.fhir.org/ig/HL7/cdmh/CodeSystem-pcornet-sexual-orientation.html
#https://loinc.org/LL3323-4/
# def add_patient_extension(type: str, SO: str):
#   if type == "SO":
#     if objects['Patient'] is not None:
#       #probably want to make an LLM call to see what orientation they are with S-O text
#       #right now this is not formatted right 
#       objects['Patient'].extension.append(Extension(url="http://hl7.org/fhir/us/cdmh/StructureDefinition/cdmh-patient-sexualOrientation", valueCode=CodeType(SO)))

# def process_record_target(record: ET.Element):
#   for child in record:
#     tag = remove_namespace(child)
#     if tag == "patientRole":
#       process_patient(child)

# def process_patient(child: ET.Element):
#   administrative_gender = child.find('.//cda:patient/cda:administrativeGenderCode', namespaces=namespace)
#   name_entity = child.find('.//cda:patient/cda:name/cda:given', namespaces=namespace)
#   patient_birth_entity = child.find(".//cda:patient/cda:birthTime", namespaces=namespace)
#   marital_entity = child.find('.//cda:patient/cda:maritalStatusCode', namespaces=namespace)
#   telecom_entites = child.findall('.//cda:telecom', namespaces=namespace)

#   given_name = None
#   gender_code = None
#   date = None
#   marital_status = None
#   mobile_phone = None

#   if name_entity is not None:
#     given_name = name_entity.text

#   if administrative_gender is not None and 'code' in administrative_gender.attrib:
#     gender_code = administrative_gender.attrib['code']

#   if patient_birth_entity is not None and 'value' in patient_birth_entity.attrib:
#     birthdate = patient_birth_entity.attrib['value']
#     date = Date(int(birthdate[0:4]),int(birthdate[4:6]), int(birthdate[6:]))

#   if marital_entity is not None and 'value' in marital_entity.attrib:
#     marital_status = marital_entity.attrib['value']

#   if telecom_entites is not None:
#     for telecom in telecom_entites:
#       if 'use' in telecom.attrib and telecom.attrib['use'] == 'MC':
#         mobile_phone = telecom.attrib['value']
  
#   #TODO: add language communication
#   objects["Patient"] = create_patient(given_name, gender_code, date, marital_status, mobile_phone)


# def process_tr_tag(tr: ET.Element):
  # #NOTE: this info will always be in LOINC section Social History - 29762-2. this is kinda hacky
  # if "ID" in tr.attrib and ("sexualorientation" in tr.attrib["ID"].lower()):
  #   for td in tr:
  #     if "ID" in td.attrib and difflib.SequenceMatcher(None, "sexualorientationvalue", td.attrib["ID"].lower()).ratio() > 0.8:
  #       add_patient_extension("SO", td.text)


#probably want to store all .text's, so we can make LLM calls to fill in missing data. 
#maybe do this after built all objects and filled in what we can, so then it can edit what we already have?
# def process_child(child: ET.Element):
#   tag = remove_namespace(child)
#   if tag == "recordTarget":
#     process_record_target(child)
#   if tag == "tr":
#     process_tr_tag(child)


# def create_json(root: ET):
#   if root is None:
#     return
#   for child in root: 
#     process_child(child)
#     create_json(child)  # DFS through elements

# def remove_namespace(child: ET.Element)->str:
#   if '}' in child.tag:
#     clean = child.tag.split('}')
#     return clean[1]
#   return child.tag
