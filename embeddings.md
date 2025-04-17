# Understanding Text Embeddings and Similarity Comparison

## What are Embeddings?

Think of embeddings as turning words into numbers in a way that captures their meaning. When we "embed" text:

1. Each word or phrase gets converted into a long list of numbers (called a vector)
2. Similar words end up with similar number patterns
3. This allows computers to understand and compare text mathematically

## How Do We Compare Embeddings?

We use something called "cosine similarity" to compare these number patterns. Here's how it works:

1. Take two pieces of text that have been converted to embeddings
2. Calculate how similar their number patterns are
3. Get a score between -1 and 1:
   - 1 = perfectly similar
   - 0 = completely different
   - -1 = opposite meaning

## Why This Works: Hypothesis

### For Regular Text

When we convert regular text to embeddings, the process works well because:

1. Natural language has inherent patterns and relationships
2. Similar concepts are often described with similar words
3. Modern embedding models are trained on vast amounts of text, helping them understand context and meaning

### For Tabular Data

Tables present a special case where we expect this approach to be particularly effective because:

1. **Structural Similarity**

   - Tables with similar purposes often share common patterns
   - Column headers often use standardized terminology
   - Data within similar columns follows similar formats

2. **Content Relationships**
   - Related items tend to use consistent vocabulary

### Example

#### Figure 1

![image](/public/Laboratory%20Test%20Results.png)

**<p style="text-align: center;">Figure 1: A generated lab test table.</p>**
<br>

#### Figure 2

![image](</public/Laboratory%20Test%20Results%20(1).png>)

**<p style="text-align: center;">Figure 2: The same formatted lab test table with different values and consistent subheadings.</p>**
<br>

#### Figure 3

![image](</public/Laboratory%20Test%20Results%20(2).png>)

**<p style="text-align: center;">Figure 3: A lab test table with the same general format (headings) but different test types (subheadings)</p>**
<br>

#### Figure 4

![image](/public/patient_lab_investigation_report.png)

**<p style="text-align: center;">Figure 4: A lab test table with different headings and different data.</p>**
<br>

#### Figure 5

![image](/public/text_similarity_results.png)

**<p style="text-align: center;">Figure 5: Multiple chunks being compared using Amazon Titan V2 embeddings model and cosine similarity. The chunks are figures 1-4 as well as chunks from previous data samples provided. A 100% Similarity score represents a 1.0 cosine similarity score. A 1.0 represents an exact match between 2 chunk embeddings. Not shown here are other data types (not lab tests) with thresholds lower than 0.40.</p>**

## Why This Matters

This technique allows us to:

- Find similar tables even when names, data, and/or headers are slightly different
- Find similar text blocks

The beauty of embeddings is that they capture the actual meaning of text, not just exact character matches. This means we can find related items even when the wording isn't exactly the same.
