"""Builds the completed IJMEDI checklist and TRIPOD+AI checklist as PDFs (LaTeX longtable).
Answers are the author's self-assessment; locations refer to the manuscript sections/tables."""
import subprocess, os
HERE = os.path.dirname(os.path.abspath(__file__))
TITLE = "Attribution is not mitigation: a paired-label counterfactual audit of hypertension classification models"

IJMEDI = [
 ("Problem understanding", None, None, None),
 ("1", "Study population, inclusion/exclusion criteria", "Yes", "Sec. 2.1: non-pregnant adults $\\geq$20 y, valid BP readings, answer to BPQ020, known treatment status; n per period."),
 ("2", "Study design", "Yes", "Sec. 2.1, 4.4: retrospective secondary analysis of cross-sectional survey data; development period 2011--2014, application period 2015--2018."),
 ("3", "Study setting", "Yes", "Sec. 2.1: US general population, NHANES household interview and mobile examination center."),
 ("4", "Source of data", "Yes", "Sec. 2.1; Data availability: public NHANES files (NCHS)."),
 ("5", "Medical task", "Yes", "Sec. 1, 2.3: binary classification of hypertension status under two label definitions; the study audits counterfactual explanations of these classifiers, not a clinical prediction task."),
 ("6", "Data collection process and data quality", "Yes", "Sec. 2.1--2.2: self-report vs examination (BP measured in the survey), questionnaire skip patterns (BPQ060 excluded, 57.8\\% vs 26.0\\% missing); Table A.8 note."),
 ("Data understanding", None, None, None),
 ("7", "Subject demographics (age, sex, comorbidities, ethnicity, SES)", "Yes", "Table 2 and Table A.6 (age mean/SD, sex, race/ethnicity, education, income, BMI, BP medication); Table A.8 (diabetes, high cholesterol, all features, both periods)."),
 ("8", "Gold standard / ground truthing", "Yes", "Sec. 2.1: labels are rule-based (self-reported diagnosis; measured BP $\\geq$140/90 mmHg or medication); no human annotation, so sub-items 8.1--8.5 are not applicable. Neither label is treated as ground truth (Sec. 2.1, 4.4)."),
 ("9", "Feature description (name, type, unit, distribution, encoding)", "Yes", "Sec. 2.2; Table A.8 (NHANES source, coding/unit, median [IQR] or \\%, missingness; race one-hot, ordinal codes). Min/max per feature in results\\_posthoc/performance/*/DATA\\_distribution.csv."),
 ("Data preparation", None, None, None),
 ("10", "Outlier detection and handling", "No", "No outlier detection was performed; refused/don't-know codes were set to missing and values were otherwise used as released (Table A.8 note)."),
 ("11", "Missing-value management", "Yes", "Sec. 2.2; Table A.8: missing rate per feature and split; training-split median imputation for CF models, XGBoost native handling for E1. Two features exceed 10\\% missing (drinks per drinking day, income); alternative imputation methods were not compared."),
 ("12", "Feature pre-processing", "Yes", "Sec. 2.2; Table A.8: no scaling or discretization (tree models); race one-hot; ordinal codes kept as numbers."),
 ("13", "Data imbalance analysis and adjustment", "Yes", "Table A.8 note: positive class 37--40\\% for both labels; Table 2 shows sex and race/ethnicity distribution; no resampling or class weighting."),
 ("Modeling", None, None, None),
 ("14", "Model task", "Yes", "Sec. 2.3: binary classification."),
 ("15", "Model output", "Yes", "Sec. 2.4: predicted probability; CF validity at threshold 0.5; percentile scores for evaluation models."),
 ("16", "Model architecture/type", "Yes", "Sec. 2.3: XGBoost; logistic regression as sensitivity analysis (Table 5)."),
 ("Validation", None, None, None),
 ("17", "Data splitting, split before pre-processing", "Yes", "Sec. 2.2--2.3: 70/30 split stratified by Y\\_clin; data were split before any preprocessing; imputation medians from the training split only."),
 ("18", "Model training and selection, hyperparameters", "Yes", "Sec. 2.3: hyperparameters fixed in advance (300 trees, depth 4, learning rate 0.05, subsampling 0.8), no tuning or model selection; depth and subsampling limit overfitting."),
 ("19", "Calibration (Brier score, calibration plot)", "Yes", "Sec. 3.1; Table A.7 (Brier, calibration intercept and slope with 95\\% CI); Fig. A.1 (calibration plot). Post hoc reporting analysis."),
 ("20", "Internal validation procedure", "Yes", "Sec. 2.3, 2.6: hold-out test set (30\\%); two-level bootstrap for E1; participant bootstrap for CF endpoints. Test set chosen at random (stratified), not for maximal diversity; sample-size adequacy not formally assessed."),
 ("21", "External validation", "No", "Sec. 4.4: the two NHANES periods test whether the procedure can be repeated with retrained models; they are not an external validation of the classifiers."),
 ("22", "Error-based metrics with CIs", "Yes", "Table A.7: accuracy, balanced accuracy, sensitivity, specificity, AUC, AUPRC, PPV, NPV, prevalence, with test-set bootstrap 95\\% CI (conditional on the fitted model). Differences between models tested via CIs (Sec. 2.3, Table 3)."),
 ("23", "Relevant errors described", "No", "No error analysis of individual misclassifications."),
 ("Deployment", None, None, None),
 ("24", "Target user", "Yes", "Sec. 4.2; Appendix (roadmap): model developers and AI governance teams before release of a CF-based decision support tool; no patient-facing use."),
 ("25", "Utility of the model, baseline model", "No", "The classifiers are objects of the audit, not proposed clinical tools; logistic regression is reported only as a sensitivity analysis (Table 5); no net-benefit or decision-curve analysis."),
 ("26", "Interpretability and explainability", "Yes", "The study is an audit of explanations: grouped permutation importance (Sec. 2.3) and counterfactuals (Sec. 2.4--2.5). No claim of adequate interpretability is made; no user study (Sec. 4.4)."),
 ("27", "Fairness, ethics, risk of bias", "Yes", "Sec. 1, 4.4: label (measurement) bias from access to diagnosis and its possible effect on groups with less access to care; CFs are not treatment advice (Sec. 5). Performance stratified by sex or race/ethnicity was not evaluated."),
 ("28", "Environmental sustainability / carbon footprint", "No", "Not estimated. All analyses ran on one laptop CPU (Appendix A)."),
 ("29", "Code and data sharing", "Yes", "Data availability: public NHANES data; code, configuration, dependency list (pip\\_freeze.txt) and results in a public GitHub repository; endpoint and post hoc scripts are separate. No web-accessible system."),
 ("30", "Adoption in practice; workflow position, TRL, monitoring", "No", "Not adopted in practice. Sec. 4.2 and Appendix (roadmap) state the intended workflow position (after model development, before release), self-assessed technology readiness level 3--4 (machine learning TRL framework, Lavin et al., 2022) and proposed re-audit after model or data changes; no BPMN diagram."),
]

TRIPOD = [
 ("Title", None, None, None),
 ("1", "Identify the study as developing or evaluating a prediction model, target population and outcome", "Partly", "Title names hypertension classification models; the study is an audit of model explanations rather than a prediction model study."),
 ("Abstract", None, None, None),
 ("2", "See TRIPOD+AI for Abstracts", "Partly", "Structured abstract with objective, data source, models, endpoints and results; model performance metrics are in Table A.7, not in the abstract."),
 ("Introduction", None, None, None),
 ("3a", "Healthcare context and rationale", "Yes", "Sec. 1."),
 ("3b", "Target population, intended purpose, intended users", "Yes", "Sec. 1, 4.2 (developers and governance teams; pre-deployment audit)."),
 ("3c", "Known health inequalities between sociodemographic groups", "Yes", "Sec. 1 (undiagnosed hypertension, access to care); Table 2."),
 ("4", "Study objectives", "Yes", "Sec. 1 (three questions); Sec. 2.3--2.5 (endpoints E1--E5)."),
 ("Methods", None, None, None),
 ("5a", "Sources of data, separately for development and evaluation", "Yes", "Sec. 2.1: NHANES 2011--2014 (development of the procedure) and 2015--2018 (application, models retrained)."),
 ("5b", "Dates of participant data", "Yes", "Sec. 2.1: survey cycles 2011--2012 to 2017--2018."),
 ("6a", "Study setting", "Yes", "Sec. 2.1: US general population survey."),
 ("6b", "Eligibility criteria", "Yes", "Sec. 2.1."),
 ("6c", "Treatments and how handled", "Yes", "Sec. 2.1, 2.4: BP medication is part of Y\\_clin; counterfactuals only for untreated people."),
 ("7", "Data pre-processing and quality checking", "Yes", "Sec. 2.2; Table A.8."),
 ("8a", "Outcome definition, how and when assessed", "Yes", "Sec. 2.1: two labels, assessed at the survey visit (cross-sectional)."),
 ("8b", "Qualifications of outcome assessors (if subjective)", "NA", "Outcomes are self-report and standardized BP measurement."),
 ("8c", "Blinding of outcome assessment", "NA", "Survey data collected independently of this study."),
 ("9a", "Choice of initial predictors", "Yes", "Sec. 2.2: six predefined feature groups; BP measurements and BP questions excluded."),
 ("9b", "Definition of all predictors", "Yes", "Table A.8."),
 ("9c", "Qualifications of predictor assessors (if subjective)", "NA", ""),
 ("10", "Study size", "Partly", "All eligible participants used; minimum analysis-set sizes pre-specified (Sec. 2.6); no formal sample-size calculation."),
 ("11", "Missing data", "Yes", "Sec. 2.2; Table A.8."),
 ("12a", "How the data were used (development, evaluation)", "Yes", "Sec. 2.3--2.4: 70/30 split; evaluation models on bootstrap samples of the training set."),
 ("12b", "Handling of predictors", "Yes", "Sec. 2.2; Table A.8."),
 ("12c", "Model type, rationale, building steps, hyperparameters", "Yes", "Sec. 2.3."),
 ("12d", "Heterogeneity across clusters/periods", "Yes", "Sec. 2.7, Table 5 (per cycle), Table A.5 (both periods)."),
 ("12e", "Performance measures and plots", "Yes", "Sec. 2.6; Table A.7; Fig. A.1."),
 ("12f", "Model updating", "NA", "No updating or recalibration."),
 ("12g", "How predictions were calculated in evaluation", "Yes", "Code repository (Data availability)."),
 ("13", "Class imbalance methods", "Yes", "None used (Table A.8 note)."),
 ("14", "Approaches to address model fairness", "No", "None; stated as a limitation (Sec. 4.4)."),
 ("15", "Model output", "Yes", "Sec. 2.4."),
 ("16", "Differences between development and evaluation data", "Yes", "Sec. 2.1; Table A.8 (both periods); Table A.5."),
 ("17", "Ethics committee and consent", "Yes", "Ethics statement (NCHS ERB protocols; written informed consent)."),
 ("Open science", None, None, None),
 ("18a", "Funding", "Yes", "Funding statement."),
 ("18b", "Conflicts of interest", "Yes", "Declaration of competing interest."),
 ("18c", "Protocol", "Yes", "Data availability statement: no protocol was published."),
 ("18d", "Registration", "Yes", "Sec. 2.6 and Data availability statement: not registered."),
 ("18e", "Data availability", "Yes", "Data availability statement."),
 ("18f", "Code availability", "Yes", "Data availability statement (public GitHub repository)."),
 ("Patient and public involvement", None, None, None),
 ("19", "Patient and public involvement", "Yes", "Statement: none."),
 ("Results", None, None, None),
 ("20a", "Participant flow, numbers with and without outcome", "Partly", "Sec. 2.1, Table 2, Table A.8 (n and positives per split); no flow diagram of exclusions."),
 ("20b", "Characteristics overall and per data source", "Yes", "Table 2, Table A.6, Table A.8."),
 ("20c", "Comparison of predictor distributions, development vs evaluation", "Yes", "Table A.8 (both periods)."),
 ("21", "Number of participants and outcome events per analysis", "Yes", "Table 3 (n per analysis set); Table A.8 note (positives)."),
 ("22", "Full prediction model details", "Yes", "Code and fixed configuration in the repository; models refit deterministically (Appendix A)."),
 ("23a", "Performance with CIs, including key subgroups", "Partly", "Table A.7 with 95\\% CI; subgroup performance not reported (Sec. 4.4)."),
 ("23b", "Heterogeneity in performance across clusters", "Yes", "Table A.7 (two periods)."),
 ("24", "Results of model updating", "NA", ""),
 ("Discussion", None, None, None),
 ("25", "Overall interpretation, including fairness", "Yes", "Sec. 4.1, 4.4."),
 ("26", "Limitations", "Yes", "Sec. 4.4."),
 ("27a", "Handling of poor quality or unavailable input data in use", "NA", "No deployment; missing-data handling in Sec. 2.2."),
 ("27b", "User interaction with input data or the model", "Yes", "Sec. 4.2 (audit run by developers; no patient interaction)."),
 ("27c", "Next steps for future research", "Yes", "Sec. 4.2; Appendix (roadmap)."),
]

def tex(rows, head, cols, note):
    body = []
    for it, req, ans, loc in rows:
        if req is None:
            body.append(r"\multicolumn{4}{l}{\textbf{%s}}\\ \midrule" % it); continue
        body.append(f"{it} & {req} & \\textbf{{{ans}}} & {loc}\\\\ \\midrule")
    return r"""\documentclass[9pt]{extarticle}
\usepackage[a4paper,margin=1.6cm,landscape]{geometry}
\usepackage[T1]{fontenc}\usepackage{lmodern}\usepackage{longtable,booktabs,array}
\renewcommand{\arraystretch}{1.15}\setlength{\parindent}{0pt}
\begin{document}
{\large\textbf{%s}}\\[3pt]
Manuscript: \emph{%s}\\
Article type: Original research article, International Journal of Medical Informatics. Completed by the author (Cong-Danh Tran). %s\\[6pt]
\begin{longtable}{>{\raggedright\arraybackslash}p{1.0cm}>{\raggedright\arraybackslash}p{7.2cm}>{\centering\arraybackslash}p{1.4cm}>{\raggedright\arraybackslash}p{14.6cm}}
\toprule \textbf{Item} & \textbf{%s} & \textbf{Authors} & \textbf{Where reported / comment}\\ \midrule \endhead
%s
\end{longtable}
\end{document}
""" % (head, TITLE, note, cols, "\n".join(body))

docs = {
 "IJMEDI_ML_Checklist": tex(IJMEDI, "IJMEDI checklist for assessment of medical AI (Cabitza \\& Campagner, 2021): author self-assessment",
     "Requirement (abridged)",
     "Answers: NA / No / Yes as in the checklist; reviewer columns left blank."),
 "TRIPOD_AI_Checklist": tex(TRIPOD, "TRIPOD+AI checklist (Collins et al., BMJ 2024;385:e078378): author self-assessment",
     "Checklist item (abridged)",
     "Answers: Yes / Partly / No / NA. The study audits explanations of classifiers developed on NHANES 2011--2014 and retrained on 2015--2018; items are interpreted accordingly."),
}
for name, src in docs.items():
    open(os.path.join(HERE, name + ".tex"), "w").write(src)
    for _ in range(2):
        subprocess.run(["pdflatex", "-interaction=nonstopmode", name + ".tex"], cwd=HERE, stdout=subprocess.DEVNULL, check=True)
    for ext in (".aux", ".log"):
        os.remove(os.path.join(HERE, name + ext))
    print("built", name)
