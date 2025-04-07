# eCR Freeform Information Extraction and Classification

# Collaboration

Thanks for your interest in our solution. Having specific examples of replication and cloning allows us to continue to grow and scale our work. If you clone or download this repository, kindly shoot us a quick email to let us know you are interested in this work!

[wwps-cic@amazon.com]

# Disclaimers

**Customers are responsible for making their own independent assessment of the information in this document.**

**This document:**

(a) is for informational purposes only,

(b) represents current AWS product offerings and practices, which are subject to change without notice, and

(c) does not create any commitments or assurances from AWS and its affiliates, suppliers or licensors. AWS products or services are provided "as is" without warranties, representations, or conditions of any kind, whether express or implied. The responsibilities and liabilities of AWS to its customers are controlled by AWS agreements, and this document is not part of, nor does it modify, any agreement between AWS and its customers.

(d) is not to be considered a recommendation or viewpoint of AWS

**Additionally, all prototype code and associated assets should be considered:**

(a) as-is and without warranties

(b) not suitable for production environments

(d) to include shortcuts in order to support rapid prototyping such as, but not limitted to, relaxed authentication and authorization and a lack of strict adherence to security best practices

**All work produced is open source. More information can be found in the GitHub repo.**

## Authors

- Gus Flusser - gflusser@calpoly.edu
- Ryan Gertz - rgertz@calpoly.edu
- Nick Osterbur - nosterb@amazon.com
- Swayam Chidrawar - schidraw@calpoly.edu

## Table of Contents

- [Collaboration](#collaboration)
- [Disclaimers](#disclaimers)
- [Authors](#authors)
- [Overview](#overview)
- [High Level Description of Workflow](#high-level-description-of-workflow)
  - [Step 1: Generate Reference Embeddings](#step-1-generate-reference-embeddings)
  - [Step 2: Classify and Extract Information](#step-2-classify-and-extract-information)
  - [Final Output Details](#final-output-details)
- [Steps to Deploy and Configure the System](#steps-to-deploy-and-configure-the-system)
  - [Before We Get Started](#before-we-get-started)
  - [1. Deploy an EC2 Instance](#1-deploy-an-ec2-instance)
  - [2. Pull the Git Repository onto the EC2 Instance](#2-pull-the-git-repository-onto-the-ec2-instance)
  - [3. Create Bedrock Guardrail](#3-create-bedrock-guardrail)
  - [4. Create a Virtual Environment](#4-create-a-virtual-environment)
  - [5. Activate the Virtual Environment](#5-activate-the-virtual-environment)
  - [6. Install the Required Packages](#6-install-the-required-packages)
  - [7. Run the Embeddings Pipeline](#7-run-the-embeddings-pipeline)
  - [8. Classify and Extract Information from an eCR](#8-classify-and-extract-information-from-an-ecr)
- [Recommended Customer Workflow](#recommended-customer-workflow)
  - [Concept Classification Workflow](#concept-classification-workflow)
  - [Soft Attribute Inference Workflow](#soft-attribute-inference-workflow)
- [Known Bugs/Concerns](#known-bugsconcerns)
- [Support](#support)

## Overview

- The [DxHub](https://dxhub.calpoly.edu/challenges/) developed a Python script leveraging AWS Bedrock to semantically analyze and identify patterns within eCR documents, allowing for the accurate extraction and classification of patient information through the use of advanced embeddings and large language models.

## High Level Description of Workflow

[Feel free to skip to the deployment section](#steps-to-deploy-and-configure-the-system) if you just want to get started. This is just a look on what this process is doing and the "theory" behind it.

### Step 1: Generate Reference Embeddings

Run the following command to process an HL7 XML eCR document:

```bash
python src/embed.py <path_to_hl7_xml_ecr>
```

**This process performs the following actions:**

- **Chunking:** Splits XML healthcare documents into logical sections.
- **Embedding:** Creates vector embeddings for each chunk using AWS Bedrock's Titan embedding model.
- **Categorization:** Classifies each chunk (e.g., "eICR Composition", "eICR Encounter") using the categories defined in `<SCHEMA_TYPE>_schema.json`.
- **Storage:** Saves the generated embeddings in the `embeddings/` directory.

### Step 2: Classify and Extract Information

Run the command below to analyze a new HL7 XML eCR document:

```bash
python src/test.py <path_to_new_hl7_xml_ecr>
```

**This process includes:**

- **Document Chunking:** Splits the new document and creates embeddings.
- **Similarity Matching:** For each chunk, finds the most similar reference chunk.
- **Additive Scoring:** Calculates additional similarity scores across multiple categories to provide a more comprehensive view of the document's content classification.
- **Information Extraction:** Uses Claude AI to extract key clinical details from each section.
- **Output Generation:** Produces a structured XML file with the findings, primary and additive similarity scores.

### Terminal Output Example

When running the script, the terminal output for each chunk in `<path_to_new_hl7_xml_ecr>` may resemble the following:

```bash
------------------------------------------------------------
Top match: embeddings/file1.json
to assets/file1.xml
category: eICR Composition (similarity: 0.1190)
Highest additive category: eICR Encounter (score: 0.2016)
  Top matches:
    - embeddings/file1.json (similarity: 0.0701)
      Path: root.component.structuredBody.3.section.text
    - embeddings/file1.json (similarity: 0.0585)
      Path: root.component.structuredBody.6.section.text
    - embeddings/file1.json (similarity: 0.0380)
      Path: root.component.structuredBody.8.section.text.table
------------------------------------------------------------
```

The output indicates that:

- The current chunk's **top category match** is **eICR Composition** with a similarity score of **0.1190**.
- The **highest additive category** is **eICR Encounter** with a score of **0.2016**.
- It also shows the **top matching paths** from reference documents that contributed to this additive score.
- The matches come from `file1.xml` which is located in `assets/file1.xml` with embeddings in `embeddings/file1.json`.

- **Note** that the files shown in the matches are not the file you are running `test.py` on, but rather the files that have close matches via embeddings to the current file you are testing.

- **Note** that for `<table>` attributes, LLM's are not being used to infer soft attributes about the patient like pregnancy, etc.

- **Note** this script will remove duplicate chunks from the input file. So if multiple chunks have the same `<text>` attribute, all but one will be skipped.

### Final Output Details

The final output is saved as `out/xml_source_inference.xml` and contains the following for each document section:

- The matched reference document and primary similarity score.
- Additive category and score attributes showing secondary matches.
- The original text from your input document.
- The corresponding matching text from the reference document.
- Detailed additive similarity scores showing additional category matches and their relevance.
- Claude's inference of key clinical information, including:
  - **Pregnancy status** with reasoning.
  - **Travel history** with locations, dates, and reasoning.
  - **Occupation information** with job details and reasoning.

#### Example Output Structure

```xml
<eICR_Encounter similarity="0.94" additive_top_category="Patient_History" additive_top_score="0.91">
  <testSource filePath="..." elementPath="...">
    <!-- Your input text -->
  </testSource>
  <embeddedSource filePath="..." elementPath="...">
    <!-- Matching reference text -->
  </embeddedSource>
  <additiveScores>
    <category name="Travel_History" score="0.85">
      <match file="file3.xml" path="/eCR/section[3]" similarity="0.85">
        <preview>Patient traveled to Mexico...</preview>
      </match>
    </category>
    <!-- Additional category matches -->
  </additiveScores>
  <inference>
    <pregnancy pregnant="false">
      <reasoning>No indication of pregnancy in this section</reasoning>
    </pregnancy>
    <!-- Additional inferences -->
  </inference>
</eICR_Encounter>
```

## Steps to Deploy and Configure the System

### Before We Get Started

- Request and ensure model access within AWS Bedrock, specifically:
  - Claude 3.5 Sonnet V2
  - Claude 3 Haiku
  - Titan Embeddings V2

The corresponding model IDs are:

```
anthropic.claude-3-5-sonnet-20241022-v2:0
anthropic.claude-3-haiku-20240307-v1:0
amazon.titan-embed-text-v2:0
```

### Schema Configuration (Required)

Before running any of the scripts you **must** have a file named `<SCHEMA_TYPE>_schema.json` located in the `assets` directory within the `src` directory. Replace `<SCHEMA_TYPE>` with your schema type identifier (e.g. `hl7`, `ecr`). This schema defines the categories (e.g., "eICR Composition," "eICR Patient," "Pregnancy Status," etc.) used by the embedding pipeline to classify document chunks. As it stands right now, if your schema is not named `hl7_schema.json`, within `vectoring.py`, you will have to edit `SCHEMA_TYPE` to reflect your schema name.

A **minimal** example looks like:

```json
{
  "type": "object",
  "properties": {
    "eICR Composition": {
      "additionalProperties": false,
      "description": "Description of eICR Composition"
    },
    "eICR Patient": {
      "additionalProperties": false,
      "description": "Description of eICR Patient"
    },
    "Pregnancy Status": {
      "additionalProperties": false,
      "description": "Description of Pregnancy Status"
    },
    "eICR Travel History": {
      "additionalProperties": false,
      "description": "Description of eICR Travel History"
    },
    "eICR Occupation History": {
      "additionalProperties": false,
      "description": "Description of eICR Occupation History"
    }
  },
  "required": [],
  "additionalProperties": false
}
```

- A starter file named `hl7_schema.json`, used in our initial testing, is provided in the repository. You may extend or replace this schema at any time; however, note that **changing the schema requires re-embedding all documents** to ensure embeddings align with your updated categories.

### 1. Deploy an EC2 Instance (Optional)

- If you prefer local development on your own device feel free to do so. An EC2 is **not required.**

- Deploy an EC2 instance in your desired region and configure it as required (i.e grant a role with required managed polices).

- CDK will require Administrator Permissions

- Normal operation will require AmazonBedrockFullAccess and AmazonS3FullAccess

- Additional settings: **t2.medium** (or larger) and security group to allow SSH traffic. We also reccomend having **at least 15 GB** of storage to account for large files.

### 2. Pull the Git Repository

- Ensure you have git [installed](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

- Clone the necessary repository to the EC2 instance:
  ```bash
  git clone https://github.com/cal-poly-dxhub/eCR-semantic-interoperability.git
  ```

### 3. Create a virtual environment:

```bash
python3.9 -m venv .venv
```

### 4. Activate the virtual environment:

- **note: this step will need to be repeated each time you log in**

```bash
source .venv/bin/activate
```

### 5. Install the required packages:

```bash
pip install -r requirements.txt
```

### 6. Set environment variables:

- Create a .env file to store your environment variables

```bash
cp .env.example .env
```

- Add your AWS credentials to the .env file under the appropriate variable names

### 7. Run the embeddings pipeline on eCRs to create a dataset (required):

- This step generates a mathematical representation (embedding) of an eCR document, which can be used for future classification of similar documents.
- Repeat this process for all eCR documents you want to include in the comparison dataset. You can add more documents at any time.

```bash
python src/embed.py <path_to_hl7_xml_ecr>
```

- After running this command, the generated embedding will be saved in the embeddings/ directory under the corresponding file path.

### 8. Run the following command to classify and extract information from an eCR:

- This step classifies an eCR document based on the existing embeddings dataset and extracts relevant information, including pregnancy status, recent travel history, and occupation history, from both text and table sections.
- Ensure that the file used here is different from those processed in step 7.

```bash
python src/test.py <path_to_new_hl7_xml_ecr>
```

- The final classified XML output file, xml_source_inference.xml, will be saved in the out/ directory.

## Recommended Customer Workflow

For optimal results, we recommend following a structured approach to implementing and fine-tuning the system. The workflow consists of two primary phases: Concept Classification and Soft Attribute Inference.

### Concept Classification Workflow

This phase focuses on setting up and validating the system's ability to correctly classify different sections of eCR documents.

#### Steps:

1. **Create a Golden Template**

   a. **Manually Label Data Elements Using Known, High-Quality Examples**

   - Use 5+ example data elements from 5 different ECR's (e.g., patient encounter, lab results, pregnancy information, etc.)
   - Run them through the embeddings script (`python src/embed.py`) to populate the classification database

   b. **Use 1 High-Quality ECR and Manually Pre-Label/Annotate Each Relevant Data Element**

   - Run the ECR through the classification script (`python src/test.py`)
   - Manually verify the classification results against the pre-labeled/annotated ECR
   - Markup where classifications are correct/incorrect
   - Add new labeled data element examples from 5 new ECR's to improve accuracy

   c. **Test with 5 New/Unseen ECR's**

   - Run them through the classification script
   - Markup where classifications are correct/incorrect

   d. **Create an Aggregated Report of Classification Performance**

   - Define acceptance criteria (e.g., what error rate per data element is acceptable?)
   - Identify which data elements are being confused and at what rates
   - Review primary and additive category matches to understand full classification context

### Soft Attribute Inference Workflow

This phase focuses on fine-tuning the system's ability to infer soft attributes (pregnancy status, occupation, travel history) from free-form text.

#### Steps:

1. **Create a Golden Template**

   a. **Draft Business Rules for Interpreting Soft Attributes**

   - Define when a person is considered currently pregnant
   - Specify when to use 'Null' or other default values
   - Establish criteria for valid occupation and travel history entries

   b. **Test Known/Annotated ECR's**

   - Use 5+ example data elements containing free-form text describing soft attributes
   - Run them through the inference script as it currently stands
   - Markup where inferences are correct/incorrect per business rules

   c. **Adjust LLM Prompts and Hard-Coded Outputs**

   - Modify prompts in the script based on defined business rules
   - Adjust any hard-coded outputs to align with business requirements

   d. **Validate with Real, Unseen ECR's**

   - Use 10+ real, unseen ECR's and run through the inference script
   - Manually verify the inference results against the business rules
   - Markup where inferences are correct/incorrect
   - Make additional adjustments as needed

   e. **Consider Multi-Category Content**

   - Pay special attention to sections with strong additive scores
   - Determine if content with significant secondary matches requires special processing
   - Adjust inference rules for content that spans multiple categories

### Customizing LLM Soft Attribute Prompt

The logic used to infer soft attributes (e.g., pregnancy status, travel history, occupation) from free-form clinical text is defined within the `llm_inference()` function in `bedrock.py`.

This function sends a prompt to the selected LLM that looks like:

```python
"You are analyzing the following text from a patient's record:\n\n"
f"{text}\n\n"
"Answer these questions in XML format with the following keys and structure:\n\n"
...
```

#### How to Customize the Prompt

You may want to tailor the prompt if:

- You are interested in **other soft attributes** that are not defined already
- Your organization has **different inference fields or business logic**
- You want to **reword reasoning instructions** for insight on how the LLM came to its conclusion

#### Where to Modify

Open `src/bedrock.py` and locate the `llm_inference` function. You can modify the string assigned to the `prompt` variable.

#### Example: Adding a Field for Symptoms

If you'd like to extract a new category such as symptoms, you'll need to update the `prompt` string in the `llm_inference` function to include the new XML block. Here's an example of what you might add:

```python
"<symptoms present=\"true\" or \"false\">\n"
"  <reasoning>explanation of your chain of thought</reasoning>\n"
"  <description>string</description>\n"
"</symptoms>\n"
```

You would append this snippet inside the prompt string in `bedrock.py` alongside the other sections.

#### Prompt Design Best Practices

- **Use explicit structure**: Use consistent XML tags and attributes as the LLM output is parsed downstream.
- **Provide chain-of-thought reasoning** prompts to improve interpretability and accuracy.
- **Be strict about `"false"` / `""` default values** to avoid noise in the output when no evidence is found.
- **Avoid vague questions**—be clear and specific about what you want the model to look for.

#### Required Updates When Changing Prompts

If you modify the prompt's structure:

- **(Possibly Optional) Review and update any Python XML parsing logic if necessary** (e.g., in `test.py`) — If your downstream code relies on a specific XML structure, ensure it is compatible with your updated prompt. In many cases, minor additions to the prompt won't break parsing logic, but significant structural changes might require updates.
- **Communicate the updated fields to your validation team** so they can adjust the golden template and business rules

## Known Bugs/Concerns

- Comments in eCRs can cause issues with traversal
- Currently only works on HL7v3 eCRs
- Large language models and embeddings models can be incorrect
- Sections with high scores across multiple categories may require special handling

## Support

For any queries or issues, please contact:

- Darren Kraker - Sr Solutions Architect - dkraker@amazon.com
- Nick Osterbur - Digital Innovation Lead - nosterb@amazon.com
- Gus Flusser - Software Developer Intern - gflusser@calpoly.edu
- Ryan Gertz - Software Developer Intern - rgertz@calpoly.edu
- Swayam Chidrawar - Software Developer Intern - schidraw@calpoly.edu
