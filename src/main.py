import json
import os
import sys

import lxml  # type: ignore # parser for bs4
from bs4 import BeautifulSoup

from flatten import flatten_json
from parse_hl7 import xml_to_dict


def cleanup():
    if os.path.exists("assets/out"):
        for file in os.listdir("assets/out"):
            os.remove(os.path.join("assets/out", file))
    else:
        os.mkdir("assets/out")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ssage: python parse_xml.py <xml_file>")
        sys.exit(1)
    cleanup()
    pathext = "assets/out/"

    file = sys.argv[1]
    with open(file, "r") as f:
        soup = BeautifulSoup(f.read(), "xml")
        bs4d = xml_to_dict(soup.ClinicalDocument)
    with open(pathext + "step1_bs4.json", "w") as outfile:
        json.dump(bs4d, outfile)
    flatd = flatten_json(bs4d)
    with open(pathext + "step2_flat.json", "w") as outfile:
        json.dump(flatd, outfile)
