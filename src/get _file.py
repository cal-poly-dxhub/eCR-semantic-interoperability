

import sys
import os

def get_file(filename: str):
    if (filename == ""):
        dir = '../assets/florida/'
        files = os.listdir(dir)

        if (len(files) == 0):
            print("no files found in " + dir)
            sys.exit()

        return dir + files[0]

    return '../assets/florida/' + filename + '.xml'


def parse_xml(file: str):
    return


def main():
    argv = sys.argv
    file = get_file("") # defults to first file in ../assets/florida
    
    if len(argv) >= 2:
        file = get_file(argv[1])

    parse_xml(file)

if __name__ == "__main__":
    main()