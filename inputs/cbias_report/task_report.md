# Symposium Attendee Analysis - Exploratory Task

## Objective

Analyse data consisting of a series of CSV and TXT files, describing lists of attendees, abstract submissions,
and attendee feedback for a series of symposia. The aim is to explore the data and answer key questions about
year-to-year trends. Generate metrics and visualisations that provide insight and would be informative to key
stakeholders, such as the organising committee, life scientists, industry partners, funders, developers of bioimage
analysis software, and other stakeholders.

## Input

A parent directory, containing subdirectories, each with data for one of four specific years (2022-2025 inclusive). The
data consists of:

- **Attendees**: one CSV per year (`CBIAS_YYYY_Attendees.csv`), one row per registration, including a ticket
  type/category (e.g. Academic, Industry, Online Only, Sponsors).
- **Feedback**: one CSV per year, one row per respondent, columns are the survey questions asked that year.
- **Abstracts**: one subfolder per year (`YYYY_Abstracts`), each containing one plain-text file per submission
  (`NN_Abstract.txt`) with `Label: value` fields (title, abstract text, keywords, etc.).
- **Programs**: two CSV files per year (one for each day), listing all speakers, their affiliations, and talk titles

Note: file formats, column names, and field labels are not perfectly consistent across all four years – handle
missing/renamed fields gracefully rather than assuming an identical schema every year.

## Guiding Questions for Analysis

Your analysis should help answer these exploratory questions:

1. **Attendee Demographics**: Does the demographic description of attendees change over time? If so, how?
2. **Abstract Content**: Does the language used in abstract submissions change over time? If so, how?
3. **Feedback**: Do common themes emerge in attendee feedback? Do they change over time?
4. **Programs**: Review the symposia programs to identify key topics and trends and correlations with abstract content and attendee demographics. Does this change over time?
5. **Stakeholders**: Do attendees fall into distinct stakeholder groups (life scientist, software developer, funder, etc.) or is there evidence of these boundaries being blurred?

## Analysis Requirements

### 1. Suggest Key metrics

Analyse the input data and suggest **key metrics** that help answer the guiding questions above. Choose
metrics that are:

- Computable from the available data
- Relevant to at least one of the guiding questions

### Already Explored — Do Not Repeat

The analyses below have already been done on this data (see https://github.com/djpbarry/cbias-survey). Proposed metrics 
must be materially different in kind - not a refinement, re-implementation, or alternative-library version of anything 
here.

**Abstract text**
- Keyword-field parsing, exploded to one row per keyword, counted by year; top-N keywords plotted as a trend over time
- Per-year word clouds (with domain stopwords: image, analysis, imaging)
- TF-IDF over year-aggregated documents (unigrams + bigrams), top terms per year
- TF-IDF over individual abstracts, averaged per year, top terms per year
- "Distinctive terms" per year: that year's mean TF-IDF minus the mean of all other years
- Lemmatised word-frequency counts with custom stopword lists
- Bigram frequency overall, and bigram counts by year plotted as trends
- Collapsing "deep learning" / "machine learning" / "neural network" into a single ML category and tracking it over time
- Document-frequency variants (each abstract counted once per term)

**Attendees**
- Attendance mode (online vs in-person) counted per year as a trend
- In-person attendees by country per year, limited to the top ~10 countries
- UK vs non-UK in-person attendance over time
- First-time vs returning attendees, identified by each attendee's earliest year, split by a UK/non-UK region
- Institution inferred from email domain

In short: per-year frequency counts of terms, keywords, countries, regions, and attendance modes - plotted as trends - 
are exhausted. So is a year-to-year comparison of aggregated abstract text via TF-IDF or word frequency.

### 2. Create Visualisations (PNG files)

Create visualisations that illustrate the metrics chosen in section 1. Pick visualisations that help answer the guiding 
questions and would be easily interpretable by all stakeholders.

### 3. Identify Data Gaps

After analysis, make specific suggestions for additional data/fields that would improve future analysis:

- Focus on what data would help answer the guiding questions more clearly
- Format: Bulleted list with a brief explanation of why each would be useful

## Output Requirements

The analysis should be independently implementable and:
- Load and parse the input data (auto-detect filename in the data directory)
- Compute metrics suggested in section 1
- Generate the visualisations suggested in section 2
- Save visualisations to the current working directory
- Handle missing or empty data gracefully

## Success Criteria

✅ Suggested metrics are genuinely novel and insightful and will help guide future symposia
✅ Script runs without errors on the provided input data  
✅ Visualisations are properly labelled (titles, axis labels, legends)   
✅ Code is clean and minimal (no unnecessary utilities or visualisations)  
