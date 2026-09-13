from typing import Any

from .openai_client import generate_json


ANALYSIS_PROMPT = """
You are a senior research analytical-method extraction expert.

Your ONLY task is to:

1. Identify ALL analytical methods explicitly reported as used by the authors.
2. Link each method to the result explicitly reported as produced by, derived
   from, or assessed with that method.
3. Explain each linked result in a concise but informative sentence that states
   what was analysed, the relevant population or comparison, and what the
   numerical result means in the context of the study.

Do not limit the extraction to statistical analysis.

Read all available article content, including the structured METHODS,
STATISTICAL ANALYSIS, DATA ANALYSIS, RESULTS, DISCUSSION, and CONCLUSION
sections, plus TABLES, TABLE FOOTNOTES, FIGURES, FIGURE CAPTIONS, and
SUPPLEMENTARY METHODS.

Give highest priority to:

1. METHODS
2. STATISTICAL ANALYSIS or DATA ANALYSIS subsections
3. RESULTS
4. TABLES and table footnotes
5. FIGURE captions

Use remaining content only when analysis methods are not clearly reported in
the priority sections.

Extract every explicitly used method for preparing, exploring, analysing,
modelling, interpreting, or validating study data. This includes statistical
methods, machine-learning techniques, predictive models, data-analysis
approaches, computational methods, and any other analytical methodology used in
the study.

Examples include, but are not limited to:

Descriptive and comparative statistical methods:

- Descriptive Statistics
- Mean and Standard Deviation
- Median and Interquartile Range
- Chi-square Test
- Fisher's Exact Test
- Student's t-test
- Paired t-test
- Welch's t-test
- ANOVA
- Repeated-Measures ANOVA
- ANCOVA
- Mann-Whitney U Test
- Wilcoxon Signed-Rank Test
- Wilcoxon Rank-Sum Test
- Kruskal-Wallis Test
- McNemar Test

Regression and multivariable methods:

- Logistic Regression
- Multivariable Logistic Regression
- Linear Regression
- Multiple Linear Regression
- Poisson Regression
- Negative Binomial Regression
- Cox Proportional Hazards Regression
- Fine-Gray Competing Risks Regression
- Generalized Linear Model
- Generalized Additive Model
- Mixed Effects Model
- Multilevel Model
- Generalized Estimating Equations

Survival and time-to-event methods:

- Kaplan-Meier Analysis
- Log-rank Test
- Cox Regression
- Competing Risks Analysis
- Cumulative Incidence Analysis

Association, diagnostic, and model-performance methods:

- Pearson Correlation
- Spearman Correlation
- Partial Correlation
- ROC Analysis
- Area Under the Curve Analysis
- Calibration Analysis
- Discrimination Analysis

Causal-inference and real-world evidence methods:

- Propensity Score Matching
- Propensity Score Weighting
- Inverse Probability of Treatment Weighting
- Stabilized Weighting
- Doubly Robust Estimation
- Difference-in-Differences
- Instrumental Variable Analysis
- Marginal Structural Model
- Interrupted Time-Series Analysis
- Regression Discontinuity
- Target Trial Emulation

Longitudinal and repeated-measures methods:

- Longitudinal Analysis
- Repeated-Measures Model
- Time-Series Analysis

Meta-analysis and evidence-synthesis methods:

- Fixed-Effect Meta-analysis
- Random-Effects Meta-analysis
- Heterogeneity Analysis
- Meta-regression
- Subgroup Analysis
- Publication Bias Analysis
- Funnel Plot Analysis
- Egger's Test

Machine-learning and computational methods:

- Random Forest
- XGBoost
- Gradient Boosting
- LightGBM
- Support Vector Machine
- Decision Tree
- Neural Network
- Deep Learning
- Convolutional Neural Network
- Recurrent Neural Network
- LSTM
- Natural Language Processing
- Clustering
- Principal Component Analysis
- Feature Selection
- Cross-validation
- Bootstrapping

Predictive modelling and validation methods:

- Risk Prediction Model
- Prognostic Model
- Classification Model
- Regression Model
- Survival Prediction Model
- Forecasting
- Model Training
- Hyperparameter Tuning
- Train/Test Split
- External Validation
- Internal Validation
- K-fold Cross-validation
- Temporal Validation
- Decision Curve Analysis

Data preparation, exploration, and dimensionality-reduction methods:

- Data Cleaning
- Data Transformation
- Normalization
- Standardization
- Outlier Detection
- Exploratory Data Analysis
- Feature Engineering
- Feature Extraction
- Principal Component Analysis
- Factor Analysis
- Latent Class Analysis
- Multiple Correspondence Analysis

Qualitative, text, and mixed-methods analysis:

- Thematic Analysis
- Content Analysis
- Framework Analysis
- Grounded Theory Analysis
- Narrative Analysis
- Discourse Analysis
- Qualitative Comparative Analysis
- Mixed-Methods Analysis
- Topic Modelling
- Sentiment Analysis
- Text Mining

Domain-specific and structured-data analysis:

- Bioinformatics Analysis
- Genomic Analysis
- Transcriptomic Analysis
- Proteomic Analysis
- Pathway Enrichment Analysis
- Gene Set Enrichment Analysis
- Sequence Analysis
- Phylogenetic Analysis
- Spatial Analysis
- Geospatial Analysis
- Network Analysis
- Social Network Analysis
- Image Analysis
- Signal Processing
- Time-Frequency Analysis

Mathematical, simulation, and algorithmic methods:

- Mathematical Modelling
- Mechanistic Modelling
- Compartmental Modelling
- Pharmacokinetic Modelling
- Pharmacodynamic Modelling
- Monte Carlo Simulation
- Discrete-Event Simulation
- Agent-Based Modelling
- Optimization
- Numerical Analysis
- Bayesian Inference
- Markov Model
- Microsimulation

Other explicitly reported analytical methods:

- Sensitivity Analysis
- Interaction Analysis
- Mediation Analysis
- Missing-Data Analysis
- Multiple Imputation
- Bonferroni Correction
- False Discovery Rate Correction

STRICT RULES

1. Extract all analysis methods explicitly stated as used by the authors,
   regardless of whether they are statistical, computational, quantitative,
   qualitative, or domain-specific.
2. Do not infer a method from statistical values or outputs.
3. Do not extract a method merely because it appears in the introduction, discussion, references, or description of another study.
4. Do not extract study designs such as randomized controlled trial, cohort study, case-control study, cross-sectional study, systematic review, observational study, case report, or case series.
5. Do not extract diseases, treatments, therapies, outcomes, endpoints, medical coding systems, databases, data sources, eligibility criteria, specimen-collection procedures, laboratory assays, or imaging-acquisition procedures unless the article explicitly uses the named procedure as an analytical method applied to study data.
6. Do not treat software names such as SAS, R, Python, SPSS, Stata, MATLAB, TensorFlow, or PyTorch as analysis methods.
7. Do not extract statistical measures or model outputs such as p-value,
   confidence interval, odds ratio, hazard ratio, risk ratio, standard deviation,
   standard error, accuracy, precision, recall, F1 score, or AUC as standalone
   methods. Extract the associated analytical method when explicitly stated.
8. Do not extract covariate adjustment as a method unless the model type is stated.
9. Preserve the method name as written whenever it is clear.
10. Standardize only obvious equivalent expressions:
    - Cox model -> Cox Proportional Hazards Regression
    - Kaplan-Meier method -> Kaplan-Meier Analysis
    - chi-squared test -> Chi-square Test
    - propensity-score matching -> Propensity Score Matching
    - inverse probability weighting -> Inverse Probability of Treatment Weighting
    - random effects model for pooled estimates -> Random-Effects Meta-analysis
11. Remove duplicate methods.
12. If the same method appears multiple times, return it only once.
13. Include meaningful named data-processing methods (for example
    normalization, feature engineering, or imputation) when they are explicitly
    reported as part of the analytical workflow. Do not extract routine file
    handling, data entry, or generic statements such as "the data were analysed."
14. For a named model or algorithm, preserve the specific model or algorithm
    name. Do not replace it with only a generic label such as "machine learning"
    or "predictive modelling."
15. If both a general analytical framework and a specific method are explicitly
    reported as used, extract both when they convey distinct information.
16. In "Analyst result", pair a method with a result only when the article
    explicitly supports that relationship. Do not guess which method produced a
    result merely because the method and result appear in the same article.
17. Preserve the reported result's essential context, including the outcome,
    comparison groups, direction, numerical value, unit, uncertainty interval,
    and p-value when available.
    For each linked quantitative result, actively look across the Results,
    tables, table footnotes, figures, captions, and supplementary content for:
    - the analysed sample size or number of events;
    - group-specific counts, percentages, means, medians, or rates;
    - the effect estimate, such as an odds ratio, hazard ratio, risk ratio,
      regression coefficient, mean difference, correlation, or rate ratio;
    - uncertainty, such as a confidence interval, credible interval, standard
      error, standard deviation, or interquartile range;
    - statistical significance, including the exact p-value when reported; and
    - model-performance values such as AUC, sensitivity, specificity, accuracy,
      precision, recall, F1 score, calibration, or validation performance.
    Include all relevant reported numbers that can be clearly linked to the
    method and result. Do not omit a reported effect estimate or uncertainty
    interval merely to make the response shorter.
18. Do not place a method in "Analyst result" when no result is clearly linked
    to it. The method must still appear in "Analysis".
19. Do not repeat the same method-result pair.
20. If one method has multiple distinct explicitly linked results, return a
    separate object for each result.
21. If no analysis method is explicitly reported, return empty lists for both
    fields.
22. Each "Result" must be a self-contained, plain-language explanation rather
    than a fragment or a list of unexplained numbers. Use two or three concise
    sentences when needed:
    - sentence 1: explain why or how the method was applied;
    - sentence 2: report the principal linked finding with its numerical
      values, units, comparison, direction, uncertainty, and p-value;
    - sentence 3, only when useful: briefly interpret what the reported value
      indicates without adding a new causal claim.
23. For quantitative analyses, numerical evidence is required whenever the
    source reports it. Never invent, calculate, round, convert, or reconstruct a
    missing number. If the source gives only a qualitative result, report it
    accurately without claiming that numerical values were reported.
24. Distinguish adjusted from unadjusted estimates and identify the relevant
    time point, follow-up period, reference group, model version, analysis set,
    or subgroup when explicitly stated.
25. Use cautious language that matches the analysis. Association does not prove
    causation, non-significance does not prove equivalence, and a p-value alone
    does not describe effect size.
26. Return only valid JSON.
27. Do not provide commentary or explanations outside the JSON. The requested
    explanation belongs inside each "Result" value.
28. Do not use Markdown.
29. Do not wrap the JSON in code fences.

OUTPUT FORMAT

Return exactly this JSON structure:

{
    "Analysis": [],
    "Analyst result": [
        {
            "Method": "",
            "Result": "Explain how the method was used, then report and briefly interpret the linked numerical finding with its context."
        }
    ]
}

EXAMPLE OF THE REQUIRED DETAIL

{
    "Analysis": [
        "Kaplan-Meier Analysis",
        "Cox Proportional Hazards Regression"
    ],
    "Analyst result": [
        {
            "Method": "Kaplan-Meier Analysis",
            "Result": "Kaplan-Meier analysis was used to estimate overall survival in the treatment and control groups. Median overall survival was 18.4 months in the treatment group versus 12.1 months in the control group (log-rank p=0.003), indicating longer observed survival in the treatment group."
        },
        {
            "Method": "Cox Proportional Hazards Regression",
            "Result": "The adjusted Cox model assessed the association between treatment and mortality after accounting for the covariates reported by the authors. Treatment was associated with a lower hazard of death (adjusted HR 0.72, 95% CI 0.58-0.89; p=0.002); this is an association estimate and does not by itself establish causation."
        }
    ]
}

The example demonstrates structure and level of detail only. Never copy its
methods, values, or interpretation unless they are explicitly present in the
supplied article.

ARTICLE CONTENT

SECTIONS:
__SECTIONS__

TABLES:
__TABLES__

FIGURES:
__FIGURES__

SUPPLEMENTARY CONTENT:
__SUPPLEMENTARY_CONTENT__
"""


def _content_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return "\n".join(
            f"{key}: {_content_to_text(item)}"
            for key, item in value.items()
            if _content_to_text(item)
        )
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_content_to_text(item) for item in value if _content_to_text(item))
    return str(value).strip()


def _normalize_analysis(data: dict) -> list[str]:
    if not isinstance(data, dict):
        return []

    values = data.get("Analysis", [])
    if not isinstance(values, list):
        return []

    methods = []
    seen = set()
    for method in values:
        if isinstance(method, dict):
            method = method.get("Method") or method.get("Analysis") or ""
        method = str(method).strip()
        key = method.casefold()
        if method and key not in seen:
            methods.append(method)
            seen.add(key)
    return methods


def _normalize_analyst_results(data: dict) -> list[str]:
    if not isinstance(data, dict):
        return []

    values = data.get("Analyst result", [])
    if not isinstance(values, list):
        return []

    results = []
    seen = set()
    for item in values:
        method = ""
        result = ""
        if isinstance(item, dict):
            method = item.get("Method") or item.get("Analysis") or ""
            result = item.get("Result") or item.get("Outcome") or ""
        elif isinstance(item, str) and ":" in item:
            method, result = item.split(":", 1)

        method = str(method).strip()
        result = str(result).strip()
        if not method or not result:
            continue

        formatted = f"{method}: {result}"
        key = formatted.casefold()
        if key not in seen:
            results.append(formatted)
            seen.add(key)
    return results


def analysis_agent(
    sections: Any,
    tables: Any = "",
    figures: Any = "",
    supplementary_content: Any = "",
) -> dict:
    sections_text = _content_to_text(sections)
    tables_text = _content_to_text(tables)
    figures_text = _content_to_text(figures)
    supplementary_text = _content_to_text(supplementary_content)

    if not " ".join(
        [sections_text, tables_text, figures_text, supplementary_text]
    ).strip():
        return {"Analysis": "", "Analyst result": ""}

    prompt = (
        ANALYSIS_PROMPT
        .replace("__SECTIONS__", sections_text)
        .replace("__TABLES__", tables_text)
        .replace("__FIGURES__", figures_text)
        .replace("__SUPPLEMENTARY_CONTENT__", supplementary_text)
    )

    try:
        data = generate_json(prompt)
        methods = _normalize_analysis(data)
        analyst_results = _normalize_analyst_results(data)
        return {
            "Analysis": "; ".join(methods),
            "Analyst result": "; ".join(analyst_results),
        }
    except Exception as exc:
        return {
            "Analysis": "",
            "Analyst result": "",
            "Analysis_Agent_Error": str(exc),
        }
