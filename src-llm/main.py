import json
import os
import sys

import lxml  # type: ignore # parser for bs4
from bs4 import BeautifulSoup
from build_fhir import build_fhir_object
from filter import filter_flattened_json
from flatten import flatten_json
from parse_hl7 import xml_to_dict

pathext = "../assets/out/"


def cleanup():
    if os.path.exists(pathext):
        for file in os.listdir(pathext):
            os.remove(os.path.join(pathext, file))
    else:
        os.mkdir(pathext)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python parse_xml.py <xml_file>")
        sys.exit(1)
    cleanup()

    file = sys.argv[1]
    with open(file, "r") as f:
        soup = BeautifulSoup(f.read(), "xml")
        bs4d = xml_to_dict(soup.ClinicalDocument)
    with open(pathext + "step1_bs4.json", "w") as outfile:
        json.dump(bs4d, outfile)
    flatd = flatten_json(bs4d)
    with open(pathext + "step2_flat.json", "w") as outfile:
        json.dump(flatd, outfile)
    filteredd = filter_flattened_json(flatd)
    with open(pathext + "step3_filtered.json", "w") as outfile:
        json.dump(filteredd, outfile)
    fhird = build_fhir_object(filteredd)
    with open(pathext + "step4_fhir_object.json", "w") as f:
        json.dump(fhird, f)
