input_config.json:
```json
{
  "objectives": "This systematic review and meta-analysis synthesized available evidence on the association between germline genetic variants and breast cancer outcomes, with a focus on pathway-level effects, and aimed to systematically synthesize germline variant-prognosis associations across multiple biological pathways and clinical outcomes using a pathway-based meta-analytic framework.",
  "inclusion_criteria": "Studies published from January 2000 to June 2024 were eligible, with no language restrictions, and searches were limited to studies involving adult women with breast cancer. Studies were included if they: i) investigated women with a confirmed diagnosis of breast cancer; ii) evaluated germline genetic variants, including single-nucleotide polymorphisms (SNPs) or pathogenic/likely pathogenic germline mutations; iii) reported at least one time-to-event outcome related to prognosis, such as DFS, OS, BCSS, PFS, or MFS; and iv) provided an adjusted effect estimate.",
  "exclusion_criteria": "Studies were excluded if they did not assess germline genetic variation, failed to report survival or recurrence outcomes, were conference abstracts or review articles, lacked full-text availability, or presented duplicated data."
}
```

query_laws.txt:
```
# SECTION_00_NON_NEGOTIABLE_RULES
- Query architecture: Query = (PRIMARY_CONCEPT) [AND (STUDY_FILTER)].
- PRIMARY_CONCEPT is recall-oriented and must contain domain concepts only.
- STUDY_FILTER is precision-oriented and must contain design/filter constraints only.
- Do not mix concept roles across the two layers.

- STUDY_FILTER IS OPTIONAL. Decision rule (apply before building the query):
  Step 1: Read the inclusion criteria and count how many distinct study design types are acceptable.
  Step 2: If 2 or more design types are acceptable, OMIT STUDY_FILTER entirely.
          This includes conjunctive listings: 'RCT and observational study' counts as 2 types -> OMIT.
          Examples that count as 2+ types: 'RCTs and cohort studies', 'observational or experimental',
          'RCT and observational study', any list with AND/OR between two or more design names.
          Query = (PRIMARY_CONCEPT) only.
  Step 3: If exactly 1 design type is mandatory (e.g., 'RCTs only', 'only randomized trials')
          AND observational/other designs are explicitly excluded, include a minimal STUDY_FILTER.
          STUDY_FILTER TEMPLATE (use all three components together):
            ("Randomized Controlled Trial"[pt] OR "Controlled Clinical Trial"[pt]
             OR randomized[tiab] OR randomised[tiab] OR randomly[tiab] OR trial[ti])
          Rationale: [pt] tags only miss pre-indexed or non-indexed trials; text-based
          terms (randomized[tiab], trial[ti]) are required for full coverage.
  Default when in doubt: OMIT STUDY_FILTER to protect recall.

- Deterministic concept assignment from Objectives/Inclusion terms:
  1. CONDITION_OUTCOME: disease entity / pathological state / diagnosis / clinical condition terms.
     CONDITION_OUTCOME encodes WHAT the study is ABOUT (the disease/condition being studied).
     Do NOT encode study-level outcome measures (e.g., mortality rate, complication rate,
     bone formation amount) here — these are screened at full-text, not searched in PubMed.
  2. POPULATION: age/sex/population subgroup/setting-human descriptors.
  3. EXPOSURE_INTERVENTION: treatment/exposure/behavior/activity/procedure terms.
  4. STUDY_DESIGN: design/method/publication-type terms (RCT, cohort, etc.).

- OUTCOME_MEASURE RULE (SECTION_00 NON-NEGOTIABLE):
  Study-level outcome measures (e.g., 'mortality', 'complication rate', 'bone formation',
  'oxidative stress level', 'quality of life score') describe what is MEASURED IN the study,
  not what the study is ABOUT. These terms:
    a) Must NOT be encoded as standalone AND blocks in PRIMARY_CONCEPT.
    b) Are left for full-text screening — do not add them to the Boolean query.
    c) Exception 1 — outcome IS the topic: if the outcome term IS also the study topic
       (e.g., a meta-analysis specifically on QoL using PANQOL, or on mortality prediction
       models), it may be included as CONDITION_OUTCOME.
    d) Exception 2 — outcome is a required inclusion criterion: if the inclusion criteria
       explicitly state that studies MUST report a specific outcome type (e.g., 'must report
       a specific outcome type (e.g., 'must report imaging findings', 'must provide survival data'),
       that required outcome type may be included as CONDITION_OUTCOME to retrieve only
       studies that measured it. Apply only when the criteria use mandatory language
       ('must', 'required', 'only studies reporting X').
  When in doubt: ask 'Is this a condition/disease, or a measurement made on patients?' —
  only conditions/diseases belong in AND blocks of PRIMARY_CONCEPT.

- POPULATION BLOCK GUARDRAIL:
  1. Ethnicity/geography/cultural-minority descriptors should be added by OR
     within an existing population/context block.
  2. Avoid creating a new mandatory AND block only for those descriptors unless
     the review objective explicitly requires that subgroup.
  3. Exception: age/developmental-stage criteria (child/adolescent/adult/older adult)
     may be an independent AND population block when definitional in eligibility.
  4. FLAT OR STRUCTURE RULE: Within any population/ethnicity block, use a FLAT OR
     structure. Do NOT nest AND inside the block. For example, requiring
     (nationality terms) AND (diaspora/immigrant terms) is forbidden — some papers
     describe a minority community using only an ethnicity name without migration terms.
     All ethnicity, nationality, migration-status, and host-country terms must be
     flat OR within one block:
       Correct:   (Ethnicity_A OR Ethnicity_B OR diaspora OR immigrant OR Country_X OR Country_Y)
       Incorrect: (Ethnicity_A OR Ethnicity_B) AND (diaspora OR immigrant OR Country_X)

- AND BLOCK BUDGET RULE (SECTION_00 NON-NEGOTIABLE):
  Mandatory AND blocks must be limited to core searchable domain concepts.
  Core blocks (always mandatory if present in objectives): CONDITION, INTERVENTION/EXPOSURE.
  Non-core elements (make optional / OR-extend, not mandatory AND):
    - Delivery mode / platform (e.g., digital, telemedicine, mobile app)
    - Context / modality (e.g., multimodal, intraperitoneal, stereotactic)
    - Provider / setting (e.g., primary care, hospital)
    - Diagnostic context (e.g., differential diagnosis, stroke mimic)
      EXCEPTION: if the diagnostic context IS the distinguishing topic of the review
      (e.g., 'biomarkers FOR differential diagnosis of stroke mimics'), include it.
  Budget guideline: aim for 2-3 AND blocks maximum. If you have 4+ AND blocks,
  re-evaluate whether each non-core block is truly mandatory or can be folded into
  an OR extension of an existing block.

- SCOPE-DEFINING CONTEXT RULE (SECTION_00 NON-NEGOTIABLE):
  When the review objective specifies a clinical context using 'in [context]' or 'for [context]'
  (e.g., 'SBRT in metastatic disease', 'exercise training in COPD patients',
  'probiotics in critically ill patients'), that context is part of the CONDITION block,
  NOT an outcome measure. Encode it in the relevant CONDITION or POPULATION block.
  Do NOT apply the OUTCOME_MEASURE RULE to scope-defining clinical contexts.
  Test: Ask 'Is this describing the patient/disease state being studied, or a number
  measured inside a study?' If it describes a patient/disease state -> CONDITION.
  Distinction: a scope-defining context describes WHAT the patient/disease state IS
  (e.g., 'metastatic', 'critically ill', 'pediatric'). It does NOT include how the
  study is conducted or delivered (e.g., 'incidentally detected', 'digitally delivered',
  'multimodal'). The latter remain non-core under the AND BLOCK BUDGET RULE regardless
  of whether they appear in the objectives.

- BROAD FALLBACK FLOOR RULE (SECTION_00 NON-NEGOTIABLE):
  Every block that uses SPECIFIC-INSTANCES enumeration must retain at least one broad
  class term (broad MeSH heading or broad tiab class word) alongside the specific names.
  Do NOT replace broad coverage with only a specific named list. Examples:
    Correct:   ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab])
    Incorrect: (CRP[tiab] OR ESR[tiab])   <- broad class term removed
    Correct:   ("Vaccines"[Mesh] OR vaccin*[tiab] OR "influenza vaccine"[tiab] OR "flu vaccine"[tiab])
    Incorrect: ("influenza vaccine"[tiab] OR "flu vaccine"[tiab])  <- broad class removed
  Rationale: papers may use only the broad class term or a synonym not in your specific list.

- LOW_OBSERVABILITY_GUARD (SECTION_00 NON-NEGOTIABLE):
  Every mandatory AND block must contain at least one HIGH-OBSERVABILITY term —
  a word that actually appears in primary study titles/abstracts.
  Category/umbrella labels have LOW OBSERVABILITY: primary studies use specific disease
  names rather than umbrella labels.
  Examples of low-observability umbrella labels (DO NOT use as sole mandatory AND):
    'non-communicable diseases', 'chronic conditions', 'inflammatory diseases',
    'complex chronic conditions', 'NCD', 'chronic illness'.
  Rules:
    a) Do NOT use an umbrella-only label as the sole content of a mandatory AND block.
    b) Either enumerate major constituent disease/condition examples as OR terms alongside
       the umbrella, or fold the umbrella into an adjacent block as optional OR.
    c) If no high-observability terms can be added to the umbrella block, OMIT it.
  Correct:   ("Diabetes Mellitus"[Mesh] OR "Hypertension"[Mesh] OR "Kidney Diseases"[Mesh]
               OR noncommunicable[tiab] OR "non-communicable"[tiab])
  Incorrect: ("Noncommunicable Diseases"[Mesh] OR NCD[tiab]) as standalone mandatory AND.

- MECHANISM_EXTENSION_RULE (SECTION_00 NON-NEGOTIABLE):
  When inclusion criteria EXPLICITLY include in vitro or animal-model studies on
  PATHOGENIC MECHANISMS (e.g., 'models of inflammation', 'models of oxidative stress',
  'signaling pathway studies'), the CONDITION block MUST include broad mechanism MeSH
  terms (e.g., 'Inflammation'[Mesh], 'Oxidative Stress'[Mesh]) as OR alternatives
  alongside disease-specific terms.
  Rationale: basic science papers study mechanisms WITHOUT naming the clinical disease.
  A paper titled 'Quercetin inhibits NF-kB in macrophages' is relevant to an RA
  inflammation review but will NOT contain 'arthritis' — it is caught only via
  'Inflammation'[Mesh] or 'inflammatory'[tiab] in the CONDITION block.
  WARNING: Do NOT apply OUTCOME_MEASURE RULE to 'Inflammation'[Mesh] when the review
  explicitly includes in vitro/animal studies; here it is a CONDITION/MECHANISM term.

- ALTERNATIVE_ARM_PRESERVATION_RULE (SECTION_00 NON-NEGOTIABLE):
  When inclusion criteria describe TWO DISTINCT ELIGIBLE ARMS with different
  characteristics (e.g., 'Arm A: whole-plant preparations' OR 'Arm B: isolated
  bioactive compounds'), the query must preserve the OR structure:
    (ArmA_terms) OR (ArmB_terms)
  Do NOT collapse both arms into a single AND block.
  If the two arms have different date windows, do NOT encode the date windows as
  mandatory filters — recall protection takes precedence over date precision.

- DATE_LANGUAGE_GUARD (SECTION_00 NON-NEGOTIABLE):
  Date-range and language restrictions must be applied ONLY when inclusion criteria
  explicitly mandate them for ALL included studies.
  Rules:
    a) Date restrictions from EXCLUSION criteria must NOT become mandatory date filters;
       leave for full-text screening.
    b) When two arms have DIFFERENT date windows, apply NO date filter.
    c) Language restrictions: apply only when criteria state 'only [language]' for all.
  Default: OMIT date and language filters unless unambiguously required for all studies.

- Before encoding each inclusion criterion as an AND block, assess: is it a searchable
  domain concept (disease, intervention, population) or a study-level filter?
  Only searchable domain concepts enter the Boolean query.
- For one-shot generation, prefer recall-preserving assignment when a term is ambiguous.
- If a criterion is not directly queryable in PubMed (e.g., sample size threshold),
  do not encode it in the Boolean query; leave it for screening.

- MeSH PROTECTION RULE: MeSH terms represent an independent indexing channel separate
  from [tiab]. Do NOT remove a MeSH term from a slot solely because a similar tiab
  term is present. Papers indexed under a MeSH heading may not use the corresponding
  text in their title or abstract, so removing the MeSH term silently drops those papers.
  MeSH terms and tiab terms are complementary, not interchangeable.

# SECTION_0_METRIC_DEFINITIONS
- Rep: Weighted cross-log reproducibility = sum(weight(log)) / sum(all_weights).
  weight = clamp(n_iterations / 18, min=0.4, max=1.0).
- Suc: Success rate = (RecallUp + HitsDown) / total occurrences.
- Con: Effect consistency = max(effect-direction count) / total occurrences.
- Sup: Support weight = 1 - exp(-n/3), n = total occurrences.
- Confidence_Total_Optional: Rep * Suc * Con * Sup.
- Risk_Penalty: recall_drop_rate * (1 + abs(min(mean_dr, 0))).
- Primary_Restriction_Penalty: penalty for restrictive PRIMARY operations
  (especially remove/restrict on PRIMARY.TIAB or PRIMARY.MESH).
- Deploy_Score: Confidence_Total_Optional
  - 0.8 * Risk_Penalty
  - 0.5 * Primary_Restriction_Penalty.

# SECTION_1_NORMALIZED_RULE_TABLE
| Law_ID | Law_Type | META_ACTION | META_CONCEPT | Action_Operator | Target_Block | Target_Slot | Field_Policy | Imperative_EN | Example_Placeholder | Apply_When | Do_Not_Apply_When | Expected_Effect_Recall | Expected_Effect_Hits | Risk | Evidence_n | Evidence_logs | Evidence_Grade | Rep | Suc | Con | Sup | Confidence_Total_Optional | Risk_Penalty | Primary_Restriction_Penalty | Deploy_Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LAW_001 | RECALL_PROTECTIVE | INITIAL_PRIMARY | PRIMARY.OTHER | BUILD_BASE | PRIMARY | CONDITION+POPULATION(+INTERVENTION if required) | AllFieldsOrMesh | To protect recall, apply INITIAL_PRIMARY to PRIMARY/CONDITION+POPULATION(+INTERVENTION if required) when coverage is incomplete. | Example: Build PRIMARY as (CONDITION_X OR CONDITION_Y) AND (INTERVENTION_Z OR TERM_A). AND BLOCK BUDGET: Use 2-3 AND blocks maximum. Only CONDITION and INTERVENTION/EXPOSURE are mandatory AND blocks. Delivery mode, modality, context, and provider blocks are optional. STUDY_FILTER: Add only when inclusion criteria restrict to a SINGLE mandatory design type (e.g., 'RCTs only' with observational excluded). A conjunctive listing ('RCT and observational') counts as 2+ types -> OMIT STUDY_FILTER. STUDY_FILTER TEMPLATE when needed: ("Randomized Controlled Trial"[pt] OR "Controlled Clinical Trial"[pt] OR randomized[tiab] OR randomised[tiab] OR randomly[tiab] OR trial[ti]). SPECIFIC-INSTANCES RULE: When a broad category concept contains named specific instances (e.g., specific biomarker names like CRP, ESR, TNF-alpha; specific drug names; vaccine brand names; specific gene names), enumerate those specific instances individually as tiab terms ALONGSIDE the broad MeSH. Never remove the broad class term. BROAD FALLBACK FLOOR: Every block must retain at least one broad class term (broad MeSH OR broad tiab like biomarker*, vaccin*, substance*) even when specific instances are listed. | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 5 | search_history_02_Cardiovascular_Disease_41684373_2026.jsonl, search_history_03_Psychiatry_41582599_2026.jsonl, search_history_03_Psychiatry_41694153_2026.jsonl, search_history_05_Infectious_Diseases_41781415_2026.jsonl, search_history_05_Infectious_Diseases_41789521_2026.jsonl | STRONG | 1.00 | 0.80 | 0.80 | 0.81 | 0.519 | 0.000 | 0.000 | 0.519 |
| LAW_002 | RECALL_PROTECTIVE | RESTORE_PRIMARY | FILTER.STUDY_DESIGN | RESTORE_BROAD | PRIMARY | PRIMARY.CONDITION_OR_POPULATION | RevertAllFieldsOrMesh | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION_OR_POPULATION when coverage is incomplete. | Example: If prior step over-restricted PRIMARY.CONDITION_OR_POPULATION, restore TERM_A from [tiab] to All Fields or Mesh. | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 4 | search_history_02_Cardiovascular_Disease_41684373_2026.jsonl, search_history_05_Infectious_Diseases_41781415_2026.jsonl, search_history_05_Infectious_Diseases_41789521_2026.jsonl | STRONG | 0.60 | 1.00 | 0.75 | 0.74 | 0.331 | 0.000 | 0.000 | 0.331 |
| LAW_003 | RECALL_PROTECTIVE | ADD_FIELD_TAG | PRIMARY.MESH | ADD_OR | PRIMARY | PRIMARY.MESH | MeshPlusTextBackup | To protect recall, apply ADD_FIELD_TAG to PRIMARY/PRIMARY.MESH when coverage is incomplete. | Example: Pair core term with field tag: ("TERM_A"[Mesh] OR "TERM_A"[tiab]). | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 10 | search_history_03_Psychiatry_41582599_2026.jsonl, search_history_05_Infectious_Diseases_41781415_2026.jsonl, search_history_05_Infectious_Diseases_41789521_2026.jsonl | STRONG | 0.60 | 0.50 | 0.50 | 0.96 | 0.145 | 0.000 | 0.000 | 0.145 |
| LAW_004 | RECALL_PROTECTIVE | EXPAND_FILTER | FILTER.STUDY_DESIGN | ADD_OR | FILTER | STUDY_DESIGN | PublicationTypePlusBackup | To protect recall, apply EXPAND_FILTER to FILTER/STUDY_DESIGN when coverage is incomplete. | Example: Before FILTER=(DESIGN_MESH OR DESIGN_TEXT); add DESIGN_ALT by OR; keep publication-type backup. | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 4 | search_history_02_Cardiovascular_Disease_41684373_2026.jsonl, search_history_05_Infectious_Diseases_41781415_2026.jsonl, search_history_05_Infectious_Diseases_41789521_2026.jsonl | STRONG | 0.60 | 0.50 | 0.50 | 0.74 | 0.110 | 0.000 | 0.000 | 0.110 |
| LAW_005 | RECALL_PROTECTIVE | RESTORE_PRIMARY | PRIMARY.CONDITION | RESTORE_BROAD | PRIMARY | PRIMARY.CONDITION | RevertAllFieldsOrMesh | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION when coverage is incomplete. | Example: If prior step over-restricted PRIMARY.CONDITION, restore TERM_A from [tiab] to All Fields or Mesh. | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 2 | search_history_02_Cardiovascular_Disease_41684373_2026.jsonl, search_history_05_Infectious_Diseases_41781415_2026.jsonl | MODERATE | 0.40 | 1.00 | 0.50 | 0.49 | 0.097 | 0.000 | 0.000 | 0.097 |
| LAW_006 | RECALL_PROTECTIVE | ADD_FIELD_TAG | FILTER.TIAB | ADD_OR | FILTER | FILTER.TIAB | tiab_synonym_expansion | To protect recall coverage, add tiab terms to FILTER when MeSH does not capture variant spellings, abbreviations, or emerging terminology; use wildcard [tiab] for terminological breadth. | Example: Add tiab synonym alongside MeSH: ("TERM_C"[Mesh] OR TERM_C*[tiab] OR TERM_D*[tiab]). | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 4 | search_history_05_Infectious_Diseases_41781415_2026.jsonl, search_history_05_Infectious_Diseases_41789521_2026.jsonl | STRONG | 0.40 | 0.50 | 0.50 | 0.74 | 0.074 | 0.000 | 0.000 | 0.074 |
| LAW_007 | RECALL_PROTECTIVE | REMOVE_FIELD_TAG | FILTER.MESH | REMOVE_OR | FILTER | FILTER.MESH | KeepTextBackup | To protect recall, apply REMOVE_FIELD_TAG to FILTER/FILTER.MESH when coverage is incomplete. | Example: Remove Mesh-only TERM_B but retain text backup ("TERM_B"[tiab]) to protect recall. | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 1 | search_history_05_Infectious_Diseases_41789521_2026.jsonl | WEAK | 0.20 | 1.00 | 1.00 | 0.28 | 0.057 | 0.000 | 0.000 | 0.057 |
| LAW_008 | RECALL_PROTECTIVE | EXPAND_PRIMARY | CONTEXT.OTHER | ADD_OR | PRIMARY | CONTEXT.OTHER | AllFieldsOrMeshOrTiab | To protect recall, apply EXPAND_PRIMARY to PRIMARY/CONTEXT.OTHER when coverage is incomplete. | Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); add synonym TERM_B to slot CONTEXT.OTHER; After PRIMARY includes TERM_B by OR. | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 1 | search_history_03_Psychiatry_41582599_2026.jsonl | WEAK | 0.20 | 1.00 | 1.00 | 0.28 | 0.057 | 0.000 | 0.000 | 0.057 |
| LAW_009 | RECALL_PROTECTIVE | RESTORE_PRIMARY | PRIMARY.INTERVENTION | RESTORE_BROAD | PRIMARY | PRIMARY.INTERVENTION | RevertAllFieldsOrMesh | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.INTERVENTION when coverage is incomplete. | Example: If prior step over-restricted PRIMARY.INTERVENTION, restore TERM_A from [tiab] to All Fields or Mesh. | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 1 | search_history_02_Cardiovascular_Disease_41684373_2026.jsonl | WEAK | 0.20 | 1.00 | 1.00 | 0.28 | 0.057 | 0.000 | 0.000 | 0.057 |
| LAW_010 | NOISE_REDUCTION | REMOVE_FIELD_TAG | FILTER.TIAB | REMOVE_OR | FILTER | FILTER.TIAB | AvoidRemovingCoreTiab | To reduce noise, remove peripheral tiab variants from FILTER only when MeSH fully covers the concept and total hits are excessive; never remove tiab from core CONDITION, POPULATION, or INTERVENTION slots. | Example: Remove peripheral tiab variant TERM_E[tiab] only when MeSH fully covers concept; retain core tiab. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 6 | search_history_05_Infectious_Diseases_41781415_2026.jsonl, search_history_05_Infectious_Diseases_41789521_2026.jsonl | STRONG | 0.40 | 1.00 | 1.00 | 0.86 | 0.346 | 0.000 | 0.000 | 0.346 |
| LAW_011 | NOISE_REDUCTION | RESTRICT_FIELD | FILTER.STUDY_DESIGN | RESTRICT_FIELD | FILTER | FILTER.STUDY_DESIGN | tiab_only_for_auxiliary | To reduce noise, apply RESTRICT_FIELD to FILTER/FILTER.STUDY_DESIGN when core concepts are stabilized and hits are excessive. | Example: Keep slot FILTER.STUDY_DESIGN but restrict auxiliary TERM_E to [tiab]; do not touch core CONDITION_X/INTERVENTION_Z. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 4 | search_history_05_Infectious_Diseases_41789521_2026.jsonl | STRONG | 0.20 | 1.00 | 1.00 | 0.74 | 0.147 | 0.000 | 0.000 | 0.147 |
| LAW_012 | NOISE_REDUCTION | RESTORE_PRIMARY | CONTEXT.POPULATION | RESTORE_BROAD | PRIMARY | PRIMARY.CONDITION_OR_POPULATION | RevertAllFieldsOrMesh | To reduce noise, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION_OR_POPULATION when core concepts are stabilized and hits are excessive. | Example: If prior step over-restricted PRIMARY.CONDITION_OR_POPULATION, restore TERM_A from [tiab] to All Fields or Mesh. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 1 | search_history_05_Infectious_Diseases_41781415_2026.jsonl | WEAK | 0.20 | 1.00 | 1.00 | 0.28 | 0.057 | 0.000 | 0.100 | 0.007 |
| LAW_013 | NOISE_REDUCTION | REMOVE_FIELD_TAG | PRIMARY.MESH | REMOVE_OR | PRIMARY | PRIMARY.MESH | KeepTextBackup | To reduce noise, apply REMOVE_FIELD_TAG to PRIMARY/PRIMARY.MESH when core concepts are stabilized and hits are excessive. | Example: Remove Mesh-only TERM_B but retain text backup ("TERM_B"[tiab]) to protect recall. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 5 | search_history_02_Cardiovascular_Disease_41684373_2026.jsonl, search_history_03_Psychiatry_41582599_2026.jsonl, search_history_03_Psychiatry_41694153_2026.jsonl, search_history_05_Infectious_Diseases_41781415_2026.jsonl | STRONG | 0.80 | 0.80 | 0.80 | 0.81 | 0.415 | 0.000 | 1.000 | -0.085 |
| LAW_014 | NOISE_REDUCTION | RESTRICT_FIELD | PRIMARY.OTHER | RESTRICT_FIELD | PRIMARY | PRIMARY.OTHER | tiab_only_for_auxiliary | To reduce noise, apply RESTRICT_FIELD to PRIMARY/PRIMARY.OTHER when core concepts are stabilized and hits are excessive. | Example: Keep slot PRIMARY.OTHER but restrict auxiliary TERM_E to [tiab]; do not touch core CONDITION_X/INTERVENTION_Z. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 3 | search_history_03_Psychiatry_41694153_2026.jsonl | STRONG | 0.20 | 0.67 | 0.67 | 0.63 | 0.056 | 0.000 | 0.500 | -0.194 |
| LAW_015 | NOISE_REDUCTION | RESTRICT_PRIMARY | PRIMARY.OTHER | REMOVE_OR | PRIMARY | PRIMARY.OTHER | KeepBroadCore | To reduce noise, apply RESTRICT_PRIMARY to PRIMARY/PRIMARY.OTHER when core concepts are stabilized and hits are excessive. | Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); remove low-value TERM_C from slot PRIMARY.OTHER; keep CONDITION_X and POPULATION_Y. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 3 | search_history_03_Psychiatry_41694153_2026.jsonl | STRONG | 0.20 | 0.67 | 0.67 | 0.63 | 0.056 | 0.000 | 0.700 | -0.294 |
| LAW_016 | CONDITIONAL | ADD_FIELD_TAG | PRIMARY.TIAB | ADD_OR | PRIMARY | PRIMARY.TIAB | tiab_synonym_expansion | [ONE-SHOT-GUIDANCE: ADD_TIAB] In initial query construction, include tiab synonyms in PRIMARY for variant spellings and abbreviations not covered by MeSH. Pair tiab terms with MeSH equivalents where possible: ("TERM"[Mesh] OR "TERM"[tiab]). Do not use tiab as sole coverage for core CONDITION or INTERVENTION slots. NAMED-INSTANCES RULE: When a slot contains a broad category concept (e.g., Biomarkers, Heat-Shock Proteins, Membranes, Vaccines) AND the paper involves specific named instances of that category (e.g., specific protein names, specific drug names, specific gene variants, vaccine brand/strain names), add those specific instance names as tiab terms. BROAD FALLBACK FLOOR: Always keep the broad class MeSH and at least one broad tiab alongside the specific names — never replace broad coverage with only a named list. Example: ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab]) is correct; (CRP[tiab] OR ESR[tiab]) alone is incorrect. INTERVENTION VARIANT COVERAGE: For intervention classes with many historical variants (vaccines, biologics, antiseptics), include generation names, brand names, strain names, and broad class terms. Wildcard (vaccin*, biologic*) covers unknown variants. | Example: Add tiab synonym alongside MeSH: ("TERM_C"[Mesh] OR TERM_C*[tiab] OR TERM_D*[tiab]). | recall is below target and expansion is needed | noise increases excessively or recall starts to drop | Increase | Increase | Noise Gain | 20 | search_history_02_Cardiovascular_Disease_41684373_2026.jsonl, search_history_03_Psychiatry_41582599_2026.jsonl, search_history_05_Infectious_Diseases_41781415_2026.jsonl, search_history_05_Infectious_Diseases_41789521_2026.jsonl | STRONG | 0.80 | 0.40 | 0.50 | 1.00 | 0.160 | 0.000 | 0.000 | 0.160 |
| LAW_017 | CONDITIONAL | EXPAND_PRIMARY | PRIMARY.CONDITION | ADD_OR | PRIMARY | PRIMARY.CONDITION | AllFieldsOrMesh | [ONE-SHOT-GUIDANCE] When building the initial query, applying EXPAND_PRIMARY to PRIMARY/PRIMARY.CONDITION tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. | Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); add synonym TERM_B to slot PRIMARY.CONDITION; After PRIMARY includes TERM_B by OR. | recall is below target and expansion is needed | noise increases excessively or recall starts to drop | Increase | Increase | Noise Gain | 10 | search_history_03_Psychiatry_41582599_2026.jsonl, search_history_05_Infectious_Diseases_41781415_2026.jsonl, search_history_05_Infectious_Diseases_41789521_2026.jsonl | STRONG | 0.60 | 0.30 | 0.60 | 0.96 | 0.104 | 0.000 | 0.000 | 0.104 |
| LAW_018 | CONDITIONAL | RESTRICT_FILTER | FILTER.STUDY_DESIGN | REMOVE_OR | FILTER | STUDY_DESIGN | KeepDesignBackup | [ONE-SHOT-GUIDANCE] RESTRICT_FILTER on FILTER/STUDY_DESIGN shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when inclusion criteria clearly support it, defined as: the review restricts to EXACTLY ONE specific study design type AND that restriction is explicitly stated as mandatory (not merely preferred or listed as an example). If inclusion criteria mention two or more design types, or if the restriction is ambiguous, do NOT apply this action. | Example: Before FILTER=(DESIGN_MESH OR DESIGN_TEXT); remove broad TERM_D; keep at least one design backup. | recall is below target and expansion is needed | noise increases excessively or recall starts to drop | Decrease | Decrease | Recall Loss | 15 | search_history_02_Cardiovascular_Disease_41684373_2026.jsonl, search_history_03_Psychiatry_41694153_2026.jsonl, search_history_05_Infectious_Diseases_41789521_2026.jsonl | STRONG | 0.60 | 0.67 | 0.67 | 0.99 | 0.265 | 0.204 | 0.000 | 0.101 |
| LAW_019 | CONDITIONAL | EXPAND_PRIMARY | PRIMARY.INTERVENTION | ADD_OR | PRIMARY | PRIMARY.INTERVENTION | AllFieldsOrMesh | [ONE-SHOT-GUIDANCE] When building the initial query, applying EXPAND_PRIMARY to PRIMARY/PRIMARY.INTERVENTION tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. | Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); add synonym TERM_B to slot PRIMARY.INTERVENTION; After PRIMARY includes TERM_B by OR. | recall is below target and expansion is needed | noise increases excessively or recall starts to drop | Increase | Increase | Noise Gain | 11 | search_history_03_Psychiatry_41582599_2026.jsonl, search_history_05_Infectious_Diseases_41781415_2026.jsonl, search_history_05_Infectious_Diseases_41789521_2026.jsonl | STRONG | 0.60 | 0.27 | 0.55 | 0.97 | 0.087 | 0.000 | 0.000 | 0.087 |
| LAW_020 | CONDITIONAL | RESTRICT_PRIMARY | PRIMARY.INTERVENTION | REMOVE_OR | PRIMARY | PRIMARY.INTERVENTION | KeepBroadCore | [ONE-SHOT-GUIDANCE] RESTRICT_PRIMARY on PRIMARY/PRIMARY.INTERVENTION shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when the term being removed is a LITERAL synonym or abbreviation/expansion pair — e.g., 'RA' when 'rheumatoid arthritis' is already present, or vice versa. CRITICAL: Do NOT treat a narrower (more specific) term as redundant merely because a broader category term is present. Training-data evidence: removing 'Methotrexate'[Majr] on the grounds that 'Antirheumatic Agents'[Majr] already covered it caused a measurable recall loss — papers describing Methotrexate did not always use the broader category label. The same applies to any hyponym/hypernym pair (e.g., a specific biomarker vs 'biomarker', a specific drug vs its drug class, a specific symptom vs 'symptom'). When in doubt, KEEP the specific term. | Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); remove low-value TERM_C from slot PRIMARY.INTERVENTION; keep CONDITION_X and POPULATION_Y. | recall is below target and expansion is needed | noise increases excessively or recall starts to drop | Decrease | Decrease | Recall Loss | 12 | search_history_02_Cardiovascular_Disease_41684373_2026.jsonl, search_history_03_Psychiatry_41582599_2026.jsonl, search_history_03_Psychiatry_41694153_2026.jsonl, search_history_05_Infectious_Diseases_41781415_2026.jsonl | STRONG | 0.80 | 0.83 | 0.83 | 0.98 | 0.545 | 0.084 | 0.800 | 0.079 |
| LAW_021 | CONDITIONAL | EXPAND_PRIMARY | CONTEXT.POPULATION | ADD_OR | PRIMARY | CONTEXT.POPULATION | AllFieldsOrMeshOrTiab | [ONE-SHOT-GUIDANCE] When building the initial query, applying EXPAND_PRIMARY to PRIMARY/CONTEXT.POPULATION tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. IMPORTANT: For ethnicity/geography/cultural-minority terms, add terms by OR within the existing population/context structure. Avoid an independent AND block for those terms because it often over-restricts recall. Exception: age/developmental-stage criteria (e.g., child, adolescent, adult) may be an independent AND population block when explicitly definitional in the inclusion criteria. | Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); add synonym TERM_B to slot CONTEXT.POPULATION; After PRIMARY includes TERM_B by OR. | recall is below target and expansion is needed | noise increases excessively or recall starts to drop | Increase | Increase | Noise Gain | 4 | search_history_05_Infectious_Diseases_41781415_2026.jsonl, search_history_05_Infectious_Diseases_41789521_2026.jsonl | STRONG | 0.40 | 0.25 | 0.75 | 0.74 | 0.055 | 0.000 | 0.000 | 0.055 |
| LAW_022 | CONDITIONAL | RESTRICT_PRIMARY | PRIMARY.CONDITION | REMOVE_OR | PRIMARY | PRIMARY.CONDITION | KeepBroadCore | [ONE-SHOT-GUIDANCE] RESTRICT_PRIMARY on PRIMARY/PRIMARY.CONDITION shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when the term being removed is a LITERAL synonym or abbreviation/expansion pair — e.g., 'RA' when 'rheumatoid arthritis' is already present, or vice versa. CRITICAL: Do NOT treat a narrower (more specific) term as redundant merely because a broader category term is present. Training-data evidence: removing 'Methotrexate'[Majr] on the grounds that 'Antirheumatic Agents'[Majr] already covered it caused a measurable recall loss — papers describing Methotrexate did not always use the broader category label. The same applies to any hyponym/hypernym pair (e.g., a specific biomarker vs 'biomarker', a specific drug vs its drug class, a specific symptom vs 'symptom'). When in doubt, KEEP the specific term. | Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); remove low-value TERM_C from slot PRIMARY.CONDITION; keep CONDITION_X and POPULATION_Y. | recall is below target and expansion is needed | noise increases excessively or recall starts to drop | Decrease | Decrease | Recall Loss | 18 | search_history_02_Cardiovascular_Disease_41684373_2026.jsonl, search_history_03_Psychiatry_41582599_2026.jsonl, search_history_03_Psychiatry_41694153_2026.jsonl, search_history_05_Infectious_Diseases_41781415_2026.jsonl | STRONG | 0.80 | 0.78 | 0.78 | 1.00 | 0.483 | 0.056 | 0.800 | 0.038 |
| LAW_023 | AVOID | EXPAND_DESIGN | FILTER.STUDY_DESIGN | BLOCKED | NA | NA | NA | Avoid applying EXPAND_DESIGN; this action is unsafe under always. | Example (do not execute): EXPAND_DESIGN on NA/NA; keep baseline blocks unchanged. | never | always | Increase | Increase | Noise Gain | 1 | search_history_03_Psychiatry_41582599_2026.jsonl | WEAK | 0.20 | 1.00 | 1.00 | 0.28 | 0.057 | 0.000 | 0.000 | 0.057 |
| LAW_024 | AVOID | REMOVE_FIELD_TAG | PRIMARY.TIAB | REMOVE_OR | PRIMARY | PRIMARY.TIAB | AvoidRemovingCoreTiab | [AVOID] Do not remove tiab terms from PRIMARY unless a MeSH equivalent fully covers all variant spellings of the concept. Removing tiab without MeSH backup is the primary cause of recall loss in this dataset. When in doubt, retain tiab coverage. | Example (do not execute): REMOVE_FIELD_TAG on PRIMARY/PRIMARY.TIAB; keep baseline blocks unchanged. | never | always | Decrease | Decrease | Recall Loss | 33 | search_history_02_Cardiovascular_Disease_41684373_2026.jsonl, search_history_03_Psychiatry_41582599_2026.jsonl, search_history_03_Psychiatry_41694153_2026.jsonl, search_history_05_Infectious_Diseases_41781415_2026.jsonl | STRONG | 0.80 | 0.79 | 0.79 | 1.00 | 0.497 | 0.061 | 1.000 | -0.052 |
| LAW_025 | AVOID | RESTRICT_FIELD | PRIMARY.INTERVENTION | RESTRICT_FIELD | PRIMARY | PRIMARY.INTERVENTION | tiab_only_for_auxiliary | Avoid applying RESTRICT_FIELD; this action is unsafe under always. | Example (do not execute): RESTRICT_FIELD on PRIMARY/PRIMARY.INTERVENTION; keep baseline blocks unchanged. | never | always | Neutral | Decrease | None | 1 | search_history_03_Psychiatry_41582599_2026.jsonl | WEAK | 0.20 | 1.00 | 1.00 | 0.28 | 0.057 | 0.000 | 0.800 | -0.343 |

# SECTION_2_COMPACT_DEPLOYMENT_LAWS
## GLOBAL_DO_LAWS
[01] LAW_001 | RECALL_PROTECTIVE | BUILD_BASE/PRIMARY/CONDITION+POPULATION(+INTERVENTION if required) | To protect recall, apply INITIAL_PRIMARY to PRIMARY/CONDITION+POPULATION(+INTERVENTION if required) when coverage is incomplete. | Example=Example: Build PRIMARY as (CONDITION_X OR CONDITION_Y) AND (INTERVENTION_Z OR TERM_A). AND BLOCK BUDGET: Use 2-3 AND blocks maximum. Only CONDITION and INTERVENTION/EXPOSURE are mandatory AND blocks. Delivery mode, modality, context, and provider blocks are optional. STUDY_FILTER: Add only when inclusion criteria restrict to a SINGLE mandatory design type (e.g., 'RCTs only' with observational excluded). A conjunctive listing ('RCT and observational') counts as 2+ types -> OMIT STUDY_FILTER. STUDY_FILTER TEMPLATE when needed: ("Randomized Controlled Trial"[pt] OR "Controlled Clinical Trial"[pt] OR randomized[tiab] OR randomised[tiab] OR randomly[tiab] OR trial[ti]). SPECIFIC-INSTANCES RULE: When a broad category concept contains named specific instances (e.g., specific biomarker names like CRP, ESR, TNF-alpha; specific drug names; vaccine brand names; specific gene names), enumerate those specific instances individually as tiab terms ALONGSIDE the broad MeSH. Never remove the broad class term. BROAD FALLBACK FLOOR: Every block must retain at least one broad class term (broad MeSH OR broad tiab like biomarker*, vaccin*, substance*) even when specific instances are listed. | Rep/Suc/Con/Sup=1.00/0.80/0.80/0.81 | DeployScore=0.519
[02] LAW_010 | NOISE_REDUCTION | REMOVE_OR/FILTER/FILTER.TIAB | To reduce noise, remove peripheral tiab variants from FILTER only when MeSH fully covers the concept and total hits are excessive; never remove tiab from core CONDITION, POPULATION, or INTERVENTION slots. | Example=Example: Remove peripheral tiab variant TERM_E[tiab] only when MeSH fully covers concept; retain core tiab. | Rep/Suc/Con/Sup=0.40/1.00/1.00/0.86 | DeployScore=0.346
[03] LAW_002 | RECALL_PROTECTIVE | RESTORE_BROAD/PRIMARY/PRIMARY.CONDITION_OR_POPULATION | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION_OR_POPULATION when coverage is incomplete. | Example=Example: If prior step over-restricted PRIMARY.CONDITION_OR_POPULATION, restore TERM_A from [tiab] to All Fields or Mesh. | Rep/Suc/Con/Sup=0.60/1.00/0.75/0.74 | DeployScore=0.331
[04] LAW_016 | CONDITIONAL | ADD_OR/PRIMARY/PRIMARY.TIAB | [ONE-SHOT-GUIDANCE: ADD_TIAB] In initial query construction, include tiab synonyms in PRIMARY for variant spellings and abbreviations not covered by MeSH. Pair tiab terms with MeSH equivalents where possible: ("TERM"[Mesh] OR "TERM"[tiab]). Do not use tiab as sole coverage for core CONDITION or INTERVENTION slots. NAMED-INSTANCES RULE: When a slot contains a broad category concept (e.g., Biomarkers, Heat-Shock Proteins, Membranes, Vaccines) AND the paper involves specific named instances of that category (e.g., specific protein names, specific drug names, specific gene variants, vaccine brand/strain names), add those specific instance names as tiab terms. BROAD FALLBACK FLOOR: Always keep the broad class MeSH and at least one broad tiab alongside the specific names — never replace broad coverage with only a named list. Example: ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab]) is correct; (CRP[tiab] OR ESR[tiab]) alone is incorrect. INTERVENTION VARIANT COVERAGE: For intervention classes with many historical variants (vaccines, biologics, antiseptics), include generation names, brand names, strain names, and broad class terms. Wildcard (vaccin*, biologic*) covers unknown variants. | Example=Example: Add tiab synonym alongside MeSH: ("TERM_C"[Mesh] OR TERM_C*[tiab] OR TERM_D*[tiab]). | Rep/Suc/Con/Sup=0.80/0.40/0.50/1.00 | DeployScore=0.160
[05] LAW_011 | NOISE_REDUCTION | RESTRICT_FIELD/FILTER/FILTER.STUDY_DESIGN | To reduce noise, apply RESTRICT_FIELD to FILTER/FILTER.STUDY_DESIGN when core concepts are stabilized and hits are excessive. | Example=Example: Keep slot FILTER.STUDY_DESIGN but restrict auxiliary TERM_E to [tiab]; do not touch core CONDITION_X/INTERVENTION_Z. | Rep/Suc/Con/Sup=0.20/1.00/1.00/0.74 | DeployScore=0.147
[06] LAW_003 | RECALL_PROTECTIVE | ADD_OR/PRIMARY/PRIMARY.MESH | To protect recall, apply ADD_FIELD_TAG to PRIMARY/PRIMARY.MESH when coverage is incomplete. | Example=Example: Pair core term with field tag: ("TERM_A"[Mesh] OR "TERM_A"[tiab]). | Rep/Suc/Con/Sup=0.60/0.50/0.50/0.96 | DeployScore=0.145
[07] LAW_004 | RECALL_PROTECTIVE | ADD_OR/FILTER/STUDY_DESIGN | To protect recall, apply EXPAND_FILTER to FILTER/STUDY_DESIGN when coverage is incomplete. | Example=Example: Before FILTER=(DESIGN_MESH OR DESIGN_TEXT); add DESIGN_ALT by OR; keep publication-type backup. | Rep/Suc/Con/Sup=0.60/0.50/0.50/0.74 | DeployScore=0.110
[08] LAW_017 | CONDITIONAL | ADD_OR/PRIMARY/PRIMARY.CONDITION | [ONE-SHOT-GUIDANCE] When building the initial query, applying EXPAND_PRIMARY to PRIMARY/PRIMARY.CONDITION tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. | Example=Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); add synonym TERM_B to slot PRIMARY.CONDITION; After PRIMARY includes TERM_B by OR. | Rep/Suc/Con/Sup=0.60/0.30/0.60/0.96 | DeployScore=0.104
[09] LAW_018 | CONDITIONAL | REMOVE_OR/FILTER/STUDY_DESIGN | [ONE-SHOT-GUIDANCE] RESTRICT_FILTER on FILTER/STUDY_DESIGN shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when inclusion criteria clearly support it, defined as: the review restricts to EXACTLY ONE specific study design type AND that restriction is explicitly stated as mandatory (not merely preferred or listed as an example). If inclusion criteria mention two or more design types, or if the restriction is ambiguous, do NOT apply this action. | Example=Example: Before FILTER=(DESIGN_MESH OR DESIGN_TEXT); remove broad TERM_D; keep at least one design backup. | Rep/Suc/Con/Sup=0.60/0.67/0.67/0.99 | DeployScore=0.101
[10] LAW_005 | RECALL_PROTECTIVE | RESTORE_BROAD/PRIMARY/PRIMARY.CONDITION | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION when coverage is incomplete. | Example=Example: If prior step over-restricted PRIMARY.CONDITION, restore TERM_A from [tiab] to All Fields or Mesh. | Rep/Suc/Con/Sup=0.40/1.00/0.50/0.49 | DeployScore=0.097
[11] LAW_019 | CONDITIONAL | ADD_OR/PRIMARY/PRIMARY.INTERVENTION | [ONE-SHOT-GUIDANCE] When building the initial query, applying EXPAND_PRIMARY to PRIMARY/PRIMARY.INTERVENTION tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. | Example=Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); add synonym TERM_B to slot PRIMARY.INTERVENTION; After PRIMARY includes TERM_B by OR. | Rep/Suc/Con/Sup=0.60/0.27/0.55/0.97 | DeployScore=0.087
[12] LAW_020 | CONDITIONAL | REMOVE_OR/PRIMARY/PRIMARY.INTERVENTION | [ONE-SHOT-GUIDANCE] RESTRICT_PRIMARY on PRIMARY/PRIMARY.INTERVENTION shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when the term being removed is a LITERAL synonym or abbreviation/expansion pair — e.g., 'RA' when 'rheumatoid arthritis' is already present, or vice versa. CRITICAL: Do NOT treat a narrower (more specific) term as redundant merely because a broader category term is present. Training-data evidence: removing 'Methotrexate'[Majr] on the grounds that 'Antirheumatic Agents'[Majr] already covered it caused a measurable recall loss — papers describing Methotrexate did not always use the broader category label. The same applies to any hyponym/hypernym pair (e.g., a specific biomarker vs 'biomarker', a specific drug vs its drug class, a specific symptom vs 'symptom'). When in doubt, KEEP the specific term. | Example=Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); remove low-value TERM_C from slot PRIMARY.INTERVENTION; keep CONDITION_X and POPULATION_Y. | Rep/Suc/Con/Sup=0.80/0.83/0.83/0.98 | DeployScore=0.079

## GLOBAL_AVOID_LAWS
[01] LAW_024 | AVOID | REMOVE_OR/PRIMARY/PRIMARY.TIAB | [AVOID] Do not remove tiab terms from PRIMARY unless a MeSH equivalent fully covers all variant spellings of the concept. Removing tiab without MeSH backup is the primary cause of recall loss in this dataset. When in doubt, retain tiab coverage. | Example=Example (do not execute): REMOVE_FIELD_TAG on PRIMARY/PRIMARY.TIAB; keep baseline blocks unchanged. | Risk=Recall Loss | Rep/Suc/Con/Sup=0.80/0.79/0.79/1.00
[02] LAW_023 | AVOID | BLOCKED/NA/NA | Avoid applying EXPAND_DESIGN; this action is unsafe under always. | Example=Example (do not execute): EXPAND_DESIGN on NA/NA; keep baseline blocks unchanged. | Risk=Noise Gain | Rep/Suc/Con/Sup=0.20/1.00/1.00/0.28
[03] LAW_025 | AVOID | RESTRICT_FIELD/PRIMARY/PRIMARY.INTERVENTION | Avoid applying RESTRICT_FIELD; this action is unsafe under always. | Example=Example (do not execute): RESTRICT_FIELD on PRIMARY/PRIMARY.INTERVENTION; keep baseline blocks unchanged. | Risk=None | Rep/Suc/Con/Sup=0.20/1.00/1.00/0.28
[04] LAW_022 | CONDITIONAL | REMOVE_OR/PRIMARY/PRIMARY.CONDITION | [ONE-SHOT-GUIDANCE] RESTRICT_PRIMARY on PRIMARY/PRIMARY.CONDITION shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when the term being removed is a LITERAL synonym or abbreviation/expansion pair — e.g., 'RA' when 'rheumatoid arthritis' is already present, or vice versa. CRITICAL: Do NOT treat a narrower (more specific) term as redundant merely because a broader category term is present. Training-data evidence: removing 'Methotrexate'[Majr] on the grounds that 'Antirheumatic Agents'[Majr] already covered it caused a measurable recall loss — papers describing Methotrexate did not always use the broader category label. The same applies to any hyponym/hypernym pair (e.g., a specific biomarker vs 'biomarker', a specific drug vs its drug class, a specific symptom vs 'symptom'). When in doubt, KEEP the specific term. | Example=Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); remove low-value TERM_C from slot PRIMARY.CONDITION; keep CONDITION_X and POPULATION_Y. | Risk=Recall Loss | Rep/Suc/Con/Sup=0.80/0.78/0.78/1.00
[05] LAW_020 | CONDITIONAL | REMOVE_OR/PRIMARY/PRIMARY.INTERVENTION | [ONE-SHOT-GUIDANCE] RESTRICT_PRIMARY on PRIMARY/PRIMARY.INTERVENTION shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when the term being removed is a LITERAL synonym or abbreviation/expansion pair — e.g., 'RA' when 'rheumatoid arthritis' is already present, or vice versa. CRITICAL: Do NOT treat a narrower (more specific) term as redundant merely because a broader category term is present. Training-data evidence: removing 'Methotrexate'[Majr] on the grounds that 'Antirheumatic Agents'[Majr] already covered it caused a measurable recall loss — papers describing Methotrexate did not always use the broader category label. The same applies to any hyponym/hypernym pair (e.g., a specific biomarker vs 'biomarker', a specific drug vs its drug class, a specific symptom vs 'symptom'). When in doubt, KEEP the specific term. | Example=Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); remove low-value TERM_C from slot PRIMARY.INTERVENTION; keep CONDITION_X and POPULATION_Y. | Risk=Recall Loss | Rep/Suc/Con/Sup=0.80/0.83/0.83/0.98
[06] LAW_018 | CONDITIONAL | REMOVE_OR/FILTER/STUDY_DESIGN | [ONE-SHOT-GUIDANCE] RESTRICT_FILTER on FILTER/STUDY_DESIGN shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when inclusion criteria clearly support it, defined as: the review restricts to EXACTLY ONE specific study design type AND that restriction is explicitly stated as mandatory (not merely preferred or listed as an example). If inclusion criteria mention two or more design types, or if the restriction is ambiguous, do NOT apply this action. | Example=Example: Before FILTER=(DESIGN_MESH OR DESIGN_TEXT); remove broad TERM_D; keep at least one design backup. | Risk=Recall Loss | Rep/Suc/Con/Sup=0.60/0.67/0.67/0.99

# SECTION_3_DOMAIN_SPECIFIC_LAWS
# Laws below derive from per-domain subsets. Consult these when the target domain is known.
# Domain laws override global laws when Divergence_Reason is set.
# Domain laws supplement global laws (additional context) otherwise.

## DOMAIN_02_Cardiovascular_Disease
# 2 divergent law(s) found. These supplement or override global laws.
### DOMAIN_02_Cardiovascular_Disease_DIVERGENT_LAWS
  [LAW_002] RECALL_PROTECTIVE | ADD_FIELD_TAG/PRIMARY.TIAB | To protect recall coverage, add tiab terms to PRIMARY when MeSH does not capture variant spellings, abbreviations, or emerging terminology; use wildcard [tiab] for terminological breadth. | Reason=type_mismatch:global=CONDITIONAL,domain=RECALL_PROTECTIVE | Rep/Suc=1.00/1.00
  [LAW_006] RECALL_PROTECTIVE | RESTORE_PRIMARY/PRIMARY.INTERVENTION | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.INTERVENTION when coverage is incomplete. | Reason=rep_gap:domain=1.00,global=0.20 | Rep/Suc=1.00/1.00

### DOMAIN_02_Cardiovascular_Disease_TOP_DO_LAWS
  [01] LAW_001 | RECALL_PROTECTIVE | RESTORE_BROAD/PRIMARY/PRIMARY.CONDITION_OR_POPULATION | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION_OR_POPULATION when coverage is incomplete. | Rep/Suc/Con/Sup=1.00/1.00/1.00/0.49
  [02] LAW_002 | RECALL_PROTECTIVE | ADD_OR/PRIMARY/PRIMARY.TIAB | To protect recall coverage, add tiab terms to PRIMARY when MeSH does not capture variant spellings, abbreviations, or emerging terminology; use wildcard [tiab] for terminological breadth. | Rep/Suc/Con/Sup=1.00/1.00/1.00/0.49
  [03] LAW_003 | RECALL_PROTECTIVE | BUILD_BASE/PRIMARY/CONDITION+POPULATION(+INTERVENTION if required) | To protect recall, apply INITIAL_PRIMARY to PRIMARY/CONDITION+POPULATION(+INTERVENTION if required) when coverage is incomplete. | Rep/Suc/Con/Sup=1.00/1.00/1.00/0.28
  [04] LAW_004 | RECALL_PROTECTIVE | ADD_OR/FILTER/STUDY_DESIGN | To protect recall, apply EXPAND_FILTER to FILTER/STUDY_DESIGN when coverage is incomplete. | Rep/Suc/Con/Sup=1.00/1.00/1.00/0.28
  [05] LAW_005 | RECALL_PROTECTIVE | RESTORE_BROAD/PRIMARY/PRIMARY.CONDITION | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION when coverage is incomplete. | Rep/Suc/Con/Sup=1.00/1.00/1.00/0.28
  [06] LAW_006 | RECALL_PROTECTIVE | RESTORE_BROAD/PRIMARY/PRIMARY.INTERVENTION | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.INTERVENTION when coverage is incomplete. | Rep/Suc/Con/Sup=1.00/1.00/1.00/0.28
  [07] LAW_008 | CONDITIONAL | REMOVE_OR/FILTER/STUDY_DESIGN | [ONE-SHOT-GUIDANCE] RESTRICT_FILTER on FILTER/STUDY_DESIGN shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when inclusion criteria clearly support it, defined as: the review restricts to EXACTLY ONE specific study design type AND that restriction is explicitly stated as mandatory (not merely preferred or listed as an example). If inclusion criteria mention two or more design types, or if the restriction is ambiguous, do NOT apply this action. | Rep/Suc/Con/Sup=1.00/0.71/0.71/0.90

### DOMAIN_02_Cardiovascular_Disease_TOP_AVOID_LAWS
  [01] LAW_011 | AVOID | REMOVE_OR/PRIMARY/PRIMARY.TIAB | [AVOID] Do not remove tiab terms from PRIMARY unless a MeSH equivalent fully covers all variant spellings of the concept. Removing tiab without MeSH backup is the primary cause of recall loss in this dataset. When in doubt, retain tiab coverage. | Risk=Recall Loss | Rep/Suc/Con/Sup=1.00/0.60/0.60/0.81
  [02] LAW_008 | CONDITIONAL | REMOVE_OR/FILTER/STUDY_DESIGN | [ONE-SHOT-GUIDANCE] RESTRICT_FILTER on FILTER/STUDY_DESIGN shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when inclusion criteria clearly support it, defined as: the review restricts to EXACTLY ONE specific study design type AND that restriction is explicitly stated as mandatory (not merely preferred or listed as an example). If inclusion criteria mention two or more design types, or if the restriction is ambiguous, do NOT apply this action. | Risk=Recall Loss | Rep/Suc/Con/Sup=1.00/0.71/0.71/0.90
  [03] LAW_009 | CONDITIONAL | REMOVE_OR/PRIMARY/PRIMARY.INTERVENTION | [ONE-SHOT-GUIDANCE] RESTRICT_PRIMARY on PRIMARY/PRIMARY.INTERVENTION shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when the term being removed is a LITERAL synonym or abbreviation/expansion pair — e.g., 'RA' when 'rheumatoid arthritis' is already present, or vice versa. CRITICAL: Do NOT treat a narrower (more specific) term as redundant merely because a broader category term is present. Training-data evidence: removing 'Methotrexate'[Majr] on the grounds that 'Antirheumatic Agents'[Majr] already covered it caused a measurable recall loss — papers describing Methotrexate did not always use the broader category label. The same applies to any hyponym/hypernym pair (e.g., a specific biomarker vs 'biomarker', a specific drug vs its drug class, a specific symptom vs 'symptom'). When in doubt, KEEP the specific term. | Risk=Recall Loss | Rep/Suc/Con/Sup=1.00/0.75/0.75/0.74
  [04] LAW_010 | CONDITIONAL | REMOVE_OR/PRIMARY/PRIMARY.CONDITION | [ONE-SHOT-GUIDANCE] RESTRICT_PRIMARY on PRIMARY/PRIMARY.CONDITION shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when the term being removed is a LITERAL synonym or abbreviation/expansion pair — e.g., 'RA' when 'rheumatoid arthritis' is already present, or vice versa. CRITICAL: Do NOT treat a narrower (more specific) term as redundant merely because a broader category term is present. Training-data evidence: removing 'Methotrexate'[Majr] on the grounds that 'Antirheumatic Agents'[Majr] already covered it caused a measurable recall loss — papers describing Methotrexate did not always use the broader category label. The same applies to any hyponym/hypernym pair (e.g., a specific biomarker vs 'biomarker', a specific drug vs its drug class, a specific symptom vs 'symptom'). When in doubt, KEEP the specific term. | Risk=Recall Loss | Rep/Suc/Con/Sup=1.00/0.67/0.67/0.63

## DOMAIN_03_Psychiatry
# 4 divergent law(s) found. These supplement or override global laws.
### DOMAIN_03_Psychiatry_DIVERGENT_LAWS
  [LAW_003] NOISE_REDUCTION | RESTRICT_PRIMARY/PRIMARY.INTERVENTION | To reduce noise, apply RESTRICT_PRIMARY to PRIMARY/PRIMARY.INTERVENTION when core concepts are stabilized and hits are excessive. | Reason=type_mismatch:global=CONDITIONAL,domain=NOISE_REDUCTION | Rep/Suc=1.00/0.86
  [LAW_004] NOISE_REDUCTION | REMOVE_FIELD_TAG/PRIMARY.TIAB | To reduce noise, remove peripheral tiab variants from PRIMARY only when MeSH fully covers the concept and total hits are excessive; never remove tiab from core CONDITION, POPULATION, or INTERVENTION slots. | Reason=type_mismatch:global=AVOID,domain=NOISE_REDUCTION | Rep/Suc=1.00/0.78
  [LAW_005] NOISE_REDUCTION | RESTRICT_PRIMARY/PRIMARY.CONDITION | To reduce noise, apply RESTRICT_PRIMARY to PRIMARY/PRIMARY.CONDITION when core concepts are stabilized and hits are excessive. | Reason=type_mismatch:global=CONDITIONAL,domain=NOISE_REDUCTION | Rep/Suc=1.00/0.71
  [LAW_011] CONDITIONAL | ADD_FIELD_TAG/PRIMARY.MESH | [ONE-SHOT-GUIDANCE] When building the initial query, applying ADD_FIELD_TAG to PRIMARY/PRIMARY.MESH tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. | Reason=type_mismatch:global=RECALL_PROTECTIVE,domain=CONDITIONAL | Rep/Suc=0.50/0.25

### DOMAIN_03_Psychiatry_TOP_DO_LAWS
  [01] LAW_001 | RECALL_PROTECTIVE | BUILD_BASE/PRIMARY/CONDITION+POPULATION(+INTERVENTION if required) | To protect recall, apply INITIAL_PRIMARY to PRIMARY/CONDITION+POPULATION(+INTERVENTION if required) when coverage is incomplete. | Rep/Suc/Con/Sup=1.00/1.00/1.00/0.49
  [02] LAW_003 | NOISE_REDUCTION | REMOVE_OR/PRIMARY/PRIMARY.INTERVENTION | To reduce noise, apply RESTRICT_PRIMARY to PRIMARY/PRIMARY.INTERVENTION when core concepts are stabilized and hits are excessive. | Rep/Suc/Con/Sup=1.00/0.86/0.86/0.90
  [03] LAW_002 | RECALL_PROTECTIVE | ADD_OR/PRIMARY/CONTEXT.OTHER | To protect recall, apply EXPAND_PRIMARY to PRIMARY/CONTEXT.OTHER when coverage is incomplete. | Rep/Suc/Con/Sup=0.50/1.00/1.00/0.28
  [04] LAW_004 | NOISE_REDUCTION | REMOVE_OR/PRIMARY/PRIMARY.TIAB | To reduce noise, remove peripheral tiab variants from PRIMARY only when MeSH fully covers the concept and total hits are excessive; never remove tiab from core CONDITION, POPULATION, or INTERVENTION slots. | Rep/Suc/Con/Sup=1.00/0.78/0.78/1.00
  [05] LAW_009 | CONDITIONAL | ADD_OR/PRIMARY/PRIMARY.CONDITION | [ONE-SHOT-GUIDANCE] When building the initial query, applying EXPAND_PRIMARY to PRIMARY/PRIMARY.CONDITION tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. | Rep/Suc/Con/Sup=0.50/0.25/0.75/0.74
  [06] LAW_010 | CONDITIONAL | ADD_OR/PRIMARY/PRIMARY.TIAB | [ONE-SHOT-GUIDANCE: ADD_TIAB] In initial query construction, include tiab synonyms in PRIMARY for variant spellings and abbreviations not covered by MeSH. Pair tiab terms with MeSH equivalents where possible: ("TERM"[Mesh] OR "TERM"[tiab]). Do not use tiab as sole coverage for core CONDITION or INTERVENTION slots. NAMED-INSTANCES RULE: When a slot contains a broad category concept (e.g., Biomarkers, Heat-Shock Proteins, Membranes, Vaccines) AND the paper involves specific named instances of that category (e.g., specific protein names, specific drug names, specific gene variants, vaccine brand/strain names), add those specific instance names as tiab terms. BROAD FALLBACK FLOOR: Always keep the broad class MeSH and at least one broad tiab alongside the specific names — never replace broad coverage with only a named list. Example: ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab]) is correct; (CRP[tiab] OR ESR[tiab]) alone is incorrect. INTERVENTION VARIANT COVERAGE: For intervention classes with many historical variants (vaccines, biologics, antiseptics), include generation names, brand names, strain names, and broad class terms. Wildcard (vaccin*, biologic*) covers unknown variants. | Rep/Suc/Con/Sup=0.50/0.14/0.86/0.90
  [07] LAW_011 | CONDITIONAL | ADD_OR/PRIMARY/PRIMARY.MESH | [ONE-SHOT-GUIDANCE] When building the initial query, applying ADD_FIELD_TAG to PRIMARY/PRIMARY.MESH tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. | Rep/Suc/Con/Sup=0.50/0.25/0.50/0.74
  [08] LAW_005 | NOISE_REDUCTION | REMOVE_OR/PRIMARY/PRIMARY.CONDITION | To reduce noise, apply RESTRICT_PRIMARY to PRIMARY/PRIMARY.CONDITION when core concepts are stabilized and hits are excessive. | Rep/Suc/Con/Sup=1.00/0.71/0.71/0.90

### DOMAIN_03_Psychiatry_TOP_AVOID_LAWS
  [01] LAW_014 | AVOID | BLOCKED/NA/NA | Avoid applying EXPAND_DESIGN; this action is unsafe under always. | Risk=Noise Gain | Rep/Suc/Con/Sup=0.50/1.00/1.00/0.28
  [02] LAW_015 | AVOID | RESTRICT_FIELD/PRIMARY/PRIMARY.INTERVENTION | Avoid applying RESTRICT_FIELD; this action is unsafe under always. | Risk=None | Rep/Suc/Con/Sup=0.50/1.00/1.00/0.28
  [03] LAW_013 | CONDITIONAL | REMOVE_OR/FILTER/STUDY_DESIGN | [ONE-SHOT-GUIDANCE] RESTRICT_FILTER on FILTER/STUDY_DESIGN shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when inclusion criteria clearly support it, defined as: the review restricts to EXACTLY ONE specific study design type AND that restriction is explicitly stated as mandatory (not merely preferred or listed as an example). If inclusion criteria mention two or more design types, or if the restriction is ambiguous, do NOT apply this action. | Risk=Recall Loss | Rep/Suc/Con/Sup=0.50/0.40/0.40/0.81

## DOMAIN_05_Infectious_Diseases
# 7 divergent law(s) found. These supplement or override global laws.
### DOMAIN_05_Infectious_Diseases_DIVERGENT_LAWS
  [LAW_002] RECALL_PROTECTIVE | EXPAND_PRIMARY/PRIMARY.INTERVENTION | To protect recall, apply EXPAND_PRIMARY to PRIMARY/PRIMARY.INTERVENTION when coverage is incomplete. | Reason=type_mismatch:global=CONDITIONAL,domain=RECALL_PROTECTIVE | Rep/Suc=1.00/0.60
  [LAW_009] NOISE_REDUCTION | RESTRICT_FILTER/FILTER.STUDY_DESIGN | To reduce noise, apply RESTRICT_FILTER to FILTER/STUDY_DESIGN when core concepts are stabilized and hits are excessive. | Reason=type_mismatch:global=CONDITIONAL,domain=NOISE_REDUCTION | Rep/Suc=0.50/1.00
  [LAW_010] NOISE_REDUCTION | RESTORE_PRIMARY/PRIMARY.CONDITION | To reduce noise, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION when core concepts are stabilized and hits are excessive. | Reason=type_mismatch:global=RECALL_PROTECTIVE,domain=NOISE_REDUCTION | Rep/Suc=0.50/1.00
  [LAW_012] NOISE_REDUCTION | RESTRICT_PRIMARY/PRIMARY.CONDITION | To reduce noise, apply RESTRICT_PRIMARY to PRIMARY/PRIMARY.CONDITION when core concepts are stabilized and hits are excessive. | Reason=type_mismatch:global=CONDITIONAL,domain=NOISE_REDUCTION | Rep/Suc=0.50/0.88
  [LAW_013] NOISE_REDUCTION | REMOVE_FIELD_TAG/PRIMARY.TIAB | To reduce noise, remove peripheral tiab variants from PRIMARY only when MeSH fully covers the concept and total hits are excessive; never remove tiab from core CONDITION, POPULATION, or INTERVENTION slots. | Reason=type_mismatch:global=AVOID,domain=NOISE_REDUCTION | Rep/Suc=0.50/0.90
  [LAW_014] NOISE_REDUCTION | RESTRICT_PRIMARY/PRIMARY.INTERVENTION | To reduce noise, apply RESTRICT_PRIMARY to PRIMARY/PRIMARY.INTERVENTION when core concepts are stabilized and hits are excessive. | Reason=type_mismatch:global=CONDITIONAL,domain=NOISE_REDUCTION | Rep/Suc=0.50/1.00
  [LAW_018] CONDITIONAL | EXPAND_FILTER/FILTER.STUDY_DESIGN | [ONE-SHOT-GUIDANCE] When building the initial query, applying EXPAND_FILTER to FILTER/STUDY_DESIGN tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. | Reason=type_mismatch:global=RECALL_PROTECTIVE,domain=CONDITIONAL | Rep/Suc=1.00/0.33

### DOMAIN_05_Infectious_Diseases_TOP_DO_LAWS
  [01] LAW_007 | NOISE_REDUCTION | REMOVE_OR/FILTER/FILTER.TIAB | To reduce noise, remove peripheral tiab variants from FILTER only when MeSH fully covers the concept and total hits are excessive; never remove tiab from core CONDITION, POPULATION, or INTERVENTION slots. | Rep/Suc/Con/Sup=1.00/1.00/1.00/0.86
  [02] LAW_001 | RECALL_PROTECTIVE | ADD_OR/PRIMARY/PRIMARY.MESH | To protect recall, apply ADD_FIELD_TAG to PRIMARY/PRIMARY.MESH when coverage is incomplete. | Rep/Suc/Con/Sup=1.00/0.67/0.67/0.86
  [03] LAW_008 | NOISE_REDUCTION | RESTRICT_FIELD/FILTER/FILTER.STUDY_DESIGN | To reduce noise, apply RESTRICT_FIELD to FILTER/FILTER.STUDY_DESIGN when core concepts are stabilized and hits are excessive. | Rep/Suc/Con/Sup=0.50/1.00/1.00/0.74
  [04] LAW_009 | NOISE_REDUCTION | REMOVE_OR/FILTER/STUDY_DESIGN | To reduce noise, apply RESTRICT_FILTER to FILTER/STUDY_DESIGN when core concepts are stabilized and hits are excessive. | Rep/Suc/Con/Sup=0.50/1.00/1.00/0.63
  [05] LAW_002 | RECALL_PROTECTIVE | ADD_OR/PRIMARY/PRIMARY.INTERVENTION | To protect recall, apply EXPAND_PRIMARY to PRIMARY/PRIMARY.INTERVENTION when coverage is incomplete. | Rep/Suc/Con/Sup=1.00/0.60/0.60/0.81
  [06] LAW_003 | RECALL_PROTECTIVE | RESTORE_BROAD/PRIMARY/PRIMARY.CONDITION_OR_POPULATION | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION_OR_POPULATION when coverage is incomplete. | Rep/Suc/Con/Sup=1.00/1.00/0.50/0.49
  [07] LAW_016 | CONDITIONAL | ADD_OR/PRIMARY/PRIMARY.TIAB | [ONE-SHOT-GUIDANCE: ADD_TIAB] In initial query construction, include tiab synonyms in PRIMARY for variant spellings and abbreviations not covered by MeSH. Pair tiab terms with MeSH equivalents where possible: ("TERM"[Mesh] OR "TERM"[tiab]). Do not use tiab as sole coverage for core CONDITION or INTERVENTION slots. NAMED-INSTANCES RULE: When a slot contains a broad category concept (e.g., Biomarkers, Heat-Shock Proteins, Membranes, Vaccines) AND the paper involves specific named instances of that category (e.g., specific protein names, specific drug names, specific gene variants, vaccine brand/strain names), add those specific instance names as tiab terms. BROAD FALLBACK FLOOR: Always keep the broad class MeSH and at least one broad tiab alongside the specific names — never replace broad coverage with only a named list. Example: ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab]) is correct; (CRP[tiab] OR ESR[tiab]) alone is incorrect. INTERVENTION VARIANT COVERAGE: For intervention classes with many historical variants (vaccines, biologics, antiseptics), include generation names, brand names, strain names, and broad class terms. Wildcard (vaccin*, biologic*) covers unknown variants. | Rep/Suc/Con/Sup=1.00/0.45/0.45/0.97
  [08] LAW_004 | RECALL_PROTECTIVE | ADD_OR/FILTER/FILTER.TIAB | To protect recall coverage, add tiab terms to FILTER when MeSH does not capture variant spellings, abbreviations, or emerging terminology; use wildcard [tiab] for terminological breadth. | Rep/Suc/Con/Sup=1.00/0.50/0.50/0.74

### DOMAIN_05_Infectious_Diseases_TOP_AVOID_LAWS


```

You are an experienced Information Specialist.

Your task is to construct a PubMed search query that retrieves studies satisfying the objectives and inclusion criteria described in `input_config.json`.

You must rely ONLY on:
- The objectives and inclusion criteria in `input_config.json`
- `query_laws.txt`
This file (`query_laws.txt`) contains normalized one-shot query-construction laws and guardrails derived from prior optimization trajectories. Follow its non-negotiable rules and deployment guidance when constructing your single final query.

----------------------------------------
GOAL
----------------------------------------

Construct ONE PubMed Boolean query that:

Highest priority: Recall = 100%
Second priority: Minimize Total Hits while maintaining Recall

----------------------------------------
CONSTRAINTS
----------------------------------------

- Do NOT create multiple alternative queries.
- Produce exactly ONE final PubMed query.
- Do NOT include explanation outside the structured output.
- Do NOT include performance speculation.
- Run SELF-CHECK internally; do NOT print checklist items in the final output.

----------------------------------------
PRE-QUERY DECISION PROCEDURE
----------------------------------------

Execute the following steps in order before writing the query.

## STEP 0 — Confirm paper identity
State: target_name=[value from input_config.json] | topic=[objectives in one sentence]
This must match the input_config.json you are processing. If uncertain, re-read input_config.json before continuing.

## STEP 1 — Study design filter decision
Count the number of distinct acceptable study design types from inclusion_criteria.
Note: a conjunctive listing such as "RCT and observational study" counts as 2 types.

    IF count >= 2:
        STUDY_FILTER = OMIT
        query = (PRIMARY_CONCEPT) only
    ELIF count == 1 AND type is RCT (and observational/other designs are explicitly excluded):
        STUDY_FILTER = INCLUDE using this exact template:
            ("Randomized Controlled Trial"[pt] OR "Controlled Clinical Trial"[pt]
             OR randomized[tiab] OR randomised[tiab] OR randomly[tiab] OR trial[ti])
    ELSE:
        STUDY_FILTER = OMIT  # default when in doubt

## STEP 2 — Classify each inclusion criterion
For each criterion in inclusion_criteria, assign one of:
    CORE      → mandatory AND block  (disease/condition, intervention/exposure)
    NON-CORE  → do NOT make a mandatory AND block

Non-core elements (must not become mandatory AND):
    - Delivery mode or platform  (digital, telehealth, mobile app, online)
    - Modality modifier          (multimodal, intraperitoneal, stereotactic)
    - Incidental/contextual qualifier  (incidentally detected, secondary finding)
    - Outcome measure            (mortality rate, QoL score, biomarker level)
      Exception A: outcome IS the study topic  (e.g., meta-analysis on PANQOL)
      Exception B: inclusion criteria use mandatory language: "must report X", "required to report X"
    - Date / language restrictions  → apply ONLY if explicitly stated in inclusion_criteria
                                      and apply uniformly to ALL included study arms.
                                      When two arms have DIFFERENT date windows, omit date filters entirely.
    - Ethnicity / geography alone   → fold into population block as OR terms, not a separate AND
    - Umbrella / category condition  (non-communicable diseases, chronic diseases,
                                      inflammatory diseases, complex chronic conditions)
      → Primary studies use specific disease names (e.g., "type 2 diabetes", "hypertension"),
        not the umbrella label. Either enumerate major constituent disease/condition examples
        as OR terms alongside the umbrella, or omit the umbrella block if the INTERVENTION
        block already limits scope. NEVER use an umbrella-only label as the sole mandatory AND.
    - Broad biological mechanism     (inflammation, oxidative stress, NF-κB, JAK/STAT)
      → Normally NON-CORE (outcome measure).
        Exception C: when inclusion criteria EXPLICITLY allow in vitro or animal-model studies
        on "models of inflammation" or "models of oxidative stress", include
        "Inflammation"[Mesh] / "Oxidative Stress"[Mesh] as OR alternatives IN the CONDITION
        block. Basic science papers study mechanisms WITHOUT naming the clinical disease; these
        terms are needed to capture them. Do NOT treat as outcome measures in this context.

## STEP 3 — AND block budget check
Count mandatory AND blocks planned.
    IF count > 3:
        Identify the least-core block and either:
        (a) fold its terms into an adjacent OR block, or
        (b) remove it
        Repeat until count <= 3.

## STEP 4 — Population / ethnicity structure check
    IF query contains ethnicity, nationality, migration-status, or host-country terms:
        ALL such terms must be in ONE flat OR block.
        Nested AND between nationality terms and diaspora/country terms is FORBIDDEN.
        Correct:   (Pakistani OR Bangladeshi OR Indian OR diaspora OR immigrant OR UK OR US)
        Incorrect: (Pakistani OR Bangladeshi OR Indian) AND (diaspora OR immigrant OR UK)

## STEP 5 — Broad fallback floor check
    FOR each block that lists specific named instances (drug names, biomarker names, vaccine names, compound names, etc.):
        PRESERVE all specific named instances — enumerate them individually in the query.
        VERIFY at least one broad class term is ALSO present alongside those specific instances.
        (e.g., "Biomarkers"[Mesh] OR biomarker*[tiab] ALONGSIDE CRP[tiab], ESR[tiab], TNF-alpha[tiab];
               "Vaccines"[Mesh] OR vaccin*[tiab] ALONGSIDE "flu vaccine"[tiab], "inactivated vaccine"[tiab])
        IF broad class term is missing: ADD it. Do NOT remove or simplify specific instances.
        Specific MeSH terms for named instances should also be included where available.

----------------------------------------
SELF-CHECK (fill in before writing FULL_QUERY)
----------------------------------------

Perform this SELF-CHECK internally only (private reasoning). Do not output these fields.

target_name: [___]
topic (1 sentence): [___]

CORE blocks:
  CONDITION: [___]
  INTERVENTION/EXPOSURE: [___]

NON-CORE elements identified and excluded from mandatory AND:
  [list each, or "none"]

STUDY_FILTER decision:
  Acceptable design types (count): [n=___]
  Decision: [OMIT / INCLUDE RCT_TEMPLATE]

Population block structure: [FLAT OR confirmed / not applicable]

Broad fallback present in all specific-instance blocks: [YES / N/A]

Umbrella/low-observability condition: [folded or omitted / not applicable]

Mechanism-scope (in vitro/animal model in criteria): [Inflammation[Mesh]/mechanism terms added to CONDITION / not applicable]

Date/language filter: [NOT APPLIED / applied because inclusion_criteria state: "___" for ALL arms]

Final AND block count: [n=___]

----------------------------------------

At the end, output your final PubMed query on a single line as: FULL_QUERY: <Query>
Output must contain only that single `FULL_QUERY:` line.
---

## ⚠ PHASE 5 CONTEXT — FULL QUERY REWRITE REQUIRED

The query below was generated and optimized through Stage A' Phases 1–4,
but still returns 18689 hits, exceeding the 9,999-hit target.

### Previous Query (after Stage A' Phases 1–4)
("breast cancer"[ti] OR "breast carcinoma"[tiab] OR "breast tumour"[tiab] OR "breast tumor"[tiab]) AND ("Genetic Variation"[Mesh] OR "germline"[tiab] OR "germline variant"[tiab] OR "germline mutation"[tiab] OR "single nucleotide polymorphism"[tiab] OR "BRCA1"[tiab] OR "BRCA2"[tiab] OR "pathogenic variant"[tiab] OR "hereditary"[tiab]) NOT "Case Reports"[pt] NOT "Letter"[pt] NOT "Comment"[pt] NOT (animals[mh] NOT humans[mh]) NOT "Editorial"[pt]

### Current Total Hits: 18689  |  Target: < 9999

### Task
Generate ONE NEW PubMed Boolean query that:
1. Returns < 9999 total hits in PubMed.
2. Preserves maximum recall — do NOT sacrifice recall for hit reduction.
3. Follows all rules in query_laws.txt and the base prompt above.

### Suggested Hit-Reduction Strategies (in order of recall safety)
Apply these where the previous query is over-broad:
1. Replace [Mesh] with [Mesh:NoExp] for terms with large MeSH subtrees and tiab backup.
2. Replace [Mesh:NoExp] with [majr] to restrict to primary-topic papers where tiab backup exists.
3. Replace broad [tiab] with [ti] where [Mesh] or [majr] backup covers the concept.
4. Remove genuinely redundant OR terms (non-wildcard term already covered by a wildcard in same block).
5. Remove very broad generic tiab when a more-specific tiab covers the concept in the same block.
6. Apply NOT publication-type filters not already present if justified by exclusion criteria.
   Safe: NOT "Comment"[pt], NOT "Letter"[pt], NOT "Editorial"[pt], NOT "Case Reports"[pt].

### Hard Constraints — Never Violate
- Do NOT remove the last tiab/MeSH coverage of a core concept (condition, intervention).
- Do NOT add new mandatory AND blocks not justified by core inclusion criteria.
- Do NOT convert OR to AND inside a primary concept block.
- Do NOT apply NOT "Review"[pt] / NOT "Meta-Analysis"[pt] if inclusion criteria
  allow systematic reviews or meta-analyses as eligible study types (SR-of-SRs rule).

Output exactly ONE line in the format:
FULL_QUERY: <your complete PubMed query>

> SR-of-SRs ACTIVE: Do NOT apply NOT "Review"[pt], NOT "Meta-Analysis"[pt], or NOT "Systematic Review"[pt] — inclusion criteria allow review-type studies.
