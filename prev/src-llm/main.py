import json
import os
import sys

import lxml  # type: ignore # parser for bs4
from bs4 import BeautifulSoup

# from build_fhir import build_fhir_object
from deduplicate import deduplicate_json
from filter import filter_flattened_json
from flatten import flatten_json
from parse_hl7 import xml_to_dict

pathext = "out/"


def cleanup():
    if os.path.exists(pathext):
        for file in os.listdir(pathext):
            os.remove(os.path.join(pathext, file))
    else:
        os.mkdir(pathext)


if __name__ == "__main__":
    # file = "./assets/dup_sample.json"
    # if not os.path.exists(file):
    #     print("no file found")

    # with open(file, "r") as f:
    #     data = json.load(f)
    #     deduplicated = deduplicate_json(data)
    #     for d in deduplicated:
    #         print(d)
    # exit(0)

    if len(sys.argv) < 2:
        print("usage: python parse_xml.py <xml_file>")
        sys.exit(1)
    cleanup()

    file = sys.argv[1]
    if "assets" not in file:
        file = "./assets/" + file
    # beautiful soup
    with open(file, "r") as f:
        soup = BeautifulSoup(f.read(), "xml")
        bs4d = xml_to_dict(soup.ClinicalDocument)
    with open(pathext + "step1_bs4.json", "w") as outfile:
        json.dump(bs4d, outfile)

    # flatten
    flatd = flatten_json(bs4d)
    with open(pathext + "step2_flat.json", "w") as outfile:
        json.dump(flatd, outfile)

    # deduplicate
    deduplciated = deduplicate_json(flatd)
    with open(pathext + "step3_deduplicated.json", "w") as f:
        json.dump(deduplciated, f)

    # filter
    filteredd = filter_flattened_json(deduplciated)
    with open(pathext + "step4_filtered.json", "w") as outfile:
        json.dump(filteredd, outfile)

    # build fhir object
    # fhird = build_fhir_object(filteredd)
    # with open(pathext + "step5_fhir_object.json", "w") as f:
    #     json.dump(fhird, f)
