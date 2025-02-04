from flair.data import Sentence
from flair.nn import Classifier
import json
from tqdm import tqdm

filename = "/Users/swayamchidrawar/repos/eCR-semantic-interoperability/semantic_matching/out/step4_filtered.json"
with open(filename, 'r') as f:
    data = json.load(f)
# make a sentence 
# sentence = Sentence("Behavioral abnormalities in the Fmr1 KO2 Mouse Model of Fragile X Syndrome")
# sentence = Sentence(data[0]["value"])
# print(sentence)
# for item in data:
#     val = item["value"]
#     sentence = Sentence(val)
    
# load biomedical NER tagger
tagger = Classifier.load("hunflair2")
for item in tqdm(data):
    val = item["value"]
    sentence = Sentence(val)
    tagger.predict(sentence)
    for entity in sentence.get_labels():
        if "Disease" in entity.value:
            print(entity)
            if "tumor" in str(entity).lower():
                print("--------------------")
                print(val)
        # print(entity)
# tag sentence
# tagger.predict(sentence)

# for entity in sentence.get_labels():
#     print(entity)
