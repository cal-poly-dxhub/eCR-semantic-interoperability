import difflib  # type: ignore
import json
import xml.etree.ElementTree as ET

import boto3  # type: ignore
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
from fhir.resources.extension import Extension
from fhir.resources.fhirtypes import ContactPointType, Date
from fhir.resources.humanname import HumanName
from fhir.resources.patient import Patient
from fhir_core.types import CodeType

fill_in_patient_prompt: str = """<prompt>
You are a medical data analysist specializing in HL7 V3 CDA and FHIR Data along with LOINC and SNOWMED Codes.
You will be given a json object of a FHIR patient data type and abridged XML of a HL7 V3 CDA file. 
In the HL7 V3 CDA XML, there will be PARENT START, PARENT END, CHILD START, CHILD END delimiters. These were not part of the original XML and are there to purely act as delimetters between different elements. 
Everything inbetween START PARENT and END PARENT are Children of that parent. The children have text inside of them along with LOINC and Snowmed codes giving context to what the text is referring to. 
Take the abridged XML, and cross reference it with the provided JSON of the patient data, and fill in any missing inputs or data. DO NOT indicate your thinking process or provide any uncessary preabmle
soley output what the new JSON object of the patient object looks like and nothing else. The Patient's main fields should only consist of active, address, birthDate, communication (A language which may be used to communicate with the patient about his or her health"), contact (A contact party (e.g. guardian, partner, friend) for the patient), deceasedBoolean, deceasedDateTime, gender, generalPractitioner, identifier, link, managingOrganization, maritalStatus, extension, multipleBirthBoolean, multipleBirthInteger, name, photo, and telecom (A contact detail for the individual)
Anything else like Sexual Orientation, Race, Ethnicity, etc. Should be placed in the Extension field following standrd FHIR practices.


Here is the Patient JSON Object:
--PATIENT--

Here is the abridged XML:
--XML--

</prompt>"""

tree = ET.parse("./input_xml.xml")
root = tree.getroot()

ET.register_namespace("", "urn:hl7-org:v3")
namespace = {"cda": "urn:hl7-org:v3"}
objects = {}

# def remove_namespace(child: ET.Element)->str:
#   if '}' in child.tag:
#     clean = child.tag.split('}')
#     return clean[1]
#   return child.tag


def create_patient(given_name, gender_code, date, marital_status, mobile_phone):
    # could prob make this more flexible
    if given_name is None:
        given_name = "NULL"
    if gender_code is None:
        gender_code = "NULL"
    if date is None:
        date = Date(0, 0, 0)
    if marital_status is None:
        marital_status = "NULL"
    if mobile_phone is None:
        mobile_phone = "NULL"

    return Patient(
        extension=[],
        telecom=[ContactPointType(use=CodeType("mobile"), value=mobile_phone)],
        birthDate=date,
        gender=gender_code,
        name=[HumanName(given=[given_name])],
    )


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


# https://build.fhir.org/ig/HL7/cdmh/CodeSystem-pcornet-sexual-orientation.html
# https://loinc.org/LL3323-4/
def add_patient_extension(type: str, SO: str):
    if type == "SO":
        if objects["Patient"] is not None:
            # probably want to make an LLM call to see what orientation they are with S-O text
            # right now this is not formatted right
            objects["Patient"].extension.append(
                Extension(
                    url="http://hl7.org/fhir/us/cdmh/StructureDefinition/cdmh-patient-sexualOrientation",
                    valueCode=CodeType(SO),
                )
            )


# def process_record_target(record: ET.Element):
#   for child in record:
#     tag = remove_namespace(child)
#     if tag == "patientRole":
#       process_patient(child)


# def process_tr_tag(tr: ET.Element):
# #NOTE: this info will always be in LOINC section Social History - 29762-2. this is kinda hacky
# if "ID" in tr.attrib and ("sexualorientation" in tr.attrib["ID"].lower()):
#   for td in tr:
#     if "ID" in td.attrib and difflib.SequenceMatcher(None, "sexualorientationvalue", td.attrib["ID"].lower()).ratio() > 0.8:
#       add_patient_extension("SO", td.text)


# probably want to store all .text's, so we can make LLM calls to fill in missing data.
# maybe do this after built all objects and filled in what we can, so then it can edit what we already have?
# def process_child(child: ET.Element):
#   tag = remove_namespace(child)
#   if tag == "recordTarget":
#     process_record_target(child)
#   if tag == "tr":
#     process_tr_tag(child)


def get_bedrock_response(prompt: str) -> str:
    client = boto3.client("bedrock-runtime", region_name="us-west-2")  # type: ignore
    model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    conversation = [{"role": "user", "content": [{"text": prompt}]}]

    try:
        response = client.converse(  # type: ignore
            modelId=model_id,
            messages=conversation,
            inferenceConfig={"maxTokens": 1024, "temperature": 1.0, "topP": 0.9},
        )
        response_text = response["output"]["message"]["content"][0]["text"]
        return response_text

    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
        exit(1)


def fill_in_patient(XML):
    prompt = fill_in_patient_prompt.replace("--XML--", XML).replace(
        "--PATIENT--", objects["Patient"].json()
    )
    response = get_bedrock_response(prompt)
    print(response)


# def create_json(root: ET):
#   if root is None:
#     return
#   for child in root:
#     process_child(child)
#     create_json(child)  # DFS through elements


def cda_patient_create(file: dict):
    given_name = None
    gender_code = None
    date = None
    marital_status = None
    mobile_phone = None

    patient = file.get("recordTarget", {}).get("patientRole", {}).get("patient")
    telecom = file.get("recordTarget", {}).get("patientRole", {})
    components = (
        file.get("component", {}).get("structuredBody", {}).get("component", {})
    )
    if patient:
        if "name" in patient:
            given_name = patient["name"]["given"]["content"]
        if "administrativeGenderCode" in patient:
            gender_code = patient["administrativeGenderCode"]["code"]
        if "birthTime" in patient:
            date = patient["birthTime"]["value"]
            date = Date(int(date[0:4]), int(date[4:6]), int(date[6:]))
    if telecom:
        for comm in telecom["telecom"]:
            if "use" in comm and comm["use"] == "MC":
                mobile_phone = comm["value"]
    if components:  # look for social history
        for component in components:
            if component["section"]["code"]["code"] == "29762-2":
                socialHistory = component
                break

    objects["Patient"] = create_patient(
        given_name, gender_code, date, marital_status, mobile_phone
    )


def get_direct_text(element):
    return "".join([t for t in element.contents if isinstance(t, str)]).strip()


# if multiple of same children, makes array with objects of each child
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
            child_content = xml_to_dict(child)  # DFS through children
            if child.name in data:
                if not isinstance(data[child.name], list):
                    data[child.name] = [data[child.name]]
                data[child.name].append(child_content)
            else:
                data[child.name] = child_content

    return data


if __name__ == "__main__":
    # create_json(root)

    with open("input_xml.xml", "r") as f:
        soup = BeautifulSoup(f.read(), "xml")
        d = xml_to_dict(soup.ClinicalDocument)
    cda_patient_create(d)
    with open("out.json", "w") as outfile:
        json.dump(d, outfile)
    # print(objects['Patient'].json())
    # print("***MANUAL PATIENT:*** \n\n ", objects['Patient'].json())
    # print("\n\n****MODEL FILL:****\n\n")
    # fill_in_patient(str(d["recordTarget"]["patientRole"]["patient"]))
