## nick notes

#### show that any provider sample can be tested with (test with nevada and florida)

### frontend

- nevada doesnt care about frontend for now
<!-- - **_beautiful frontend report_**
- **_display reconstructed entire document (all chunks)_**
- **_citation links back to original xml documents_** -->

### backend

- grab ecrs from an s3 bucket
- demonstrate llm inference on xml text segment
  - ex: pregnancy, travel history, occupation (make up data if need be) ask llm for value (haiku 3.5 on every open ended text field for the questions too)
  - is patient pregnant
  - does patient have recent travel history (yes/no, where, when)
  - does patient have occupation
- underlying thing is the reconstructed json
- throw in snomed/loinc if applicable
- update underlying json (pregnant: true (gotten from llm inference) (citable))

### vaidation

- groud truth data
- take known fake patient data
- get synthetic data from s3

### security

- validation
- application used
- ports used
- aws services used

#### new idea

- use embedding pipeline to get category of data
- use llm inference to get answers to 4 questions
- create new xml document with
  - category of data (category)
  - original xml section chunk (source)
  - llm inference answers (inference)
