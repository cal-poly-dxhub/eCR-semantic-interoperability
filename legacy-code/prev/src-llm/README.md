# current llm-only approach

### ironically currently does not even use an llm

## process:

- run the main.py file with the path to the xml ecr file as an argument

```bash
python src-llm/main.py <path-to-xml-ecr>
```

- _*i suggest using a xml with <10k lines otherwise opening the json documents can stall vsc*_

- the program exports json documents to out/

## exported documents:

#### step1_bs4.json:

- the raw bs4 soup object

#### step2_flat.json:

- the flat dictionary of the ecr
- converts all nested tags to a single path string
- e.g. '{a: {b: {c: 1}}}' -> {'path: 'a.b.c', 'value': '1'}

#### step3_deduplication.json:

- the flat dictionary with duplicates removed
- e.g. {'a.b.c': '1', 'a.b.c': '2'} -> {'a.b.c': '1'}
- also {'a.1.c': '1', 'a.2.c': '1', 'a.4.c': '2'} -> {'a.1.c': '1', 'a.4.c': '2'}

#### step4_filtered.json:

- ignores certain things in certain paths
- not fully implemented

### cli outputs:

- prints number of duplicate elements removed
