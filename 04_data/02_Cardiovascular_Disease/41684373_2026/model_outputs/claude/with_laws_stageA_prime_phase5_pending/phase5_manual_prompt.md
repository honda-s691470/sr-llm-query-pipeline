input_config.json:
```json
{
  "objectives": "To systematically review and meta-analyze the predictive performance of prognostic multivariable stroke prediction models for adults in the general population, using routinely collected community data to predict future stroke and inform targeted screening and/or primary prevention.",
  "inclusion_criteria": "Eligible studies were prognostic prediction model studies: prediction model development without external validation in independent data, development with external validation in independent data, or external model validation with possible model updating. The target population was adults in the general population; the outcome was a specific future event/diagnosis of stroke; any prediction interval was allowed; and the models were intended for use in adults in the community. Included models had to describe a multivariable prediction model and use variables routinely collected in community settings, including sociodemographic variables, disease conditions/procedures, clinical assessments, prescribed medications, lifestyle factors, and simple laboratory tests/biomarkers.",
  "exclusion_criteria": "Excluded studies/models used variables not routinely available in community records or very rarely tested in community clinical practice, including waist circumference, exercise and diet, electrocardiograph parameters, and non-routine blood tests such as uric acid and homocysteine. Full-text exclusions shown in the PRISMA were: no risk model/prediction rule; selected patients not from the general population; variables not available in the community; wrong outcome measure; stroke not excluded at baseline; or population size <1000. The database-level exclusion set in the supplementary Ovid strategy (#15-24) excluded letter/comment/editorial/interview/case-report publication types and title case-report records, and applied the animal-only exclusion (animals NOT humans)."
}
```

query_laws.txt:
```
# SECTION_00_NON_NEGOTIABLE_RULES
- Query architecture: Query = (PRIMARY_CONCEPT) [AND (STUDY_FILTER)].
- PRIMARY_CONCEPT is recall-oriented and contains domain concepts only.
- STUDY_FILTER is precision-oriented and contains design/filter constraints only.
- Do not mix concept roles across the two layers.

- STUDY_FILTER IS OPTIONAL. Decision rule:
  Step 1: Read the inclusion criteria and count how many distinct study design types are acceptable.
  Step 2: If 2 or more design types are acceptable, OMIT STUDY_FILTER entirely.
          This includes conjunctive listings: 'RCT and observational study' counts as 2 types -> OMIT.
          Query = (PRIMARY_CONCEPT) only.
  Step 3: If exactly 1 design type is mandatory AND other designs are explicitly excluded, include a minimal STUDY_FILTER.
          For RCT-only reviews, use the full minimal trial filter template with both [pt] and text terms together:
            ("Randomized Controlled Trial"[pt] OR "Controlled Clinical Trial"[pt]
             OR randomized[tiab] OR randomised[tiab] OR randomly[tiab] OR trial[ti])
  Default when in doubt: OMIT STUDY_FILTER to protect recall.

- Deterministic concept assignment:
  1. CONDITION_OUTCOME: the disease / pathological state / clinical condition / biologic process the study is ABOUT.
  2. POPULATION: age / sex / subgroup / setting / host descriptors.
  3. EXPOSURE_INTERVENTION: treatment / exposure / behavior / procedure terms.
  4. STUDY_DESIGN: design / method / publication-type terms.

- OUTCOME_MEASURE RULE:
  Study-level measured variables are not standalone PRIMARY_CONCEPT blocks.
  Do NOT create a mandatory AND block for terms such as mortality, complication rate, cytokine level,
  quality-of-life score, biomarker level, or other readout variables.
  Exception 1: the outcome term is itself the review topic.
  Exception 2: the inclusion criteria require reporting that outcome type using mandatory language.
  When in doubt, ask: 'Is this what the study is about, or what the study measures?' Only the former belongs in PRIMARY_CONCEPT.

- ASSAY/MODEL CONTEXT RULE:
  For in vitro / cellular / mechanistic reviews, generic assay-context words are usually LOW-OBSERVABILITY.
  Do NOT spend a full mandatory AND block on generic context labels alone, such as
  cell*, cellular, cultured, in vitro, model*, inflammation model, stimulation model.
  Instead:
    a) keep the truly topic-defining disease/mechanism/exposure terms mandatory;
    b) fold assay/model terms into those blocks as OR extensions when helpful;
    c) if the review is about immune or inflammatory modulation, prefer topic terms that primary papers actually state
       (e.g., immune/immunomodulat*/cytokine/inflammat* style wording) over a separate generic '(cells AND inflammation)' gate.
  Exception: if one specific experimental system is explicitly mandatory and highly observable, it may be encoded minimally.

- POPULATION BLOCK GUARDRAIL:
  1. Age/developmental-stage criteria may be an independent AND block when definitional in eligibility.
  2. Ethnicity, nationality, geography, diaspora, and recruitment-country descriptors should usually be OR terms within an existing population/context block, not a new standalone AND block.
  3. If that subgroup/location is required but LOW-OBSERVABILITY in titles/abstracts/indexing, prefer OMITTING the block and screening later rather than enforcing a recall-damaging gate.
  4. Use FLAT OR structure inside population/context blocks. Do NOT require nested patterns such as
     (ethnicity terms) AND (diaspora/migrant terms) or (country terms) AND (ethnicity terms).

- AND BLOCK BUDGET RULE:
  Mandatory AND blocks must be limited to core searchable domain concepts.
  Core blocks: CONDITION and INTERVENTION/EXPOSURE.
  Non-core elements should usually be optional OR extensions, not their own AND blocks:
    delivery mode, platform, modality, provider, setting, generic assay context, diagnostic context.
  Exception: include a non-core element as mandatory only when it is the distinguishing topic of the review.
  Budget guideline: aim for 2-3 AND blocks maximum. If you have 4+ AND blocks, simplify.

- SCOPE-DEFINING CONTEXT RULE:
  When the objective specifies a clinical or biologic context using 'in [context]' or 'for [context]',
  encode that context in the relevant CONDITION or POPULATION block, not as an outcome measure.
  Test: if it describes the patient/disease state being studied, it is CONDITION/POPULATION;
  if it describes a measured variable, it is an outcome measure.

- BROAD FALLBACK FLOOR RULE:
  Every block built from specific instances must retain at least one broad class term
  (broad MeSH heading or broad tiab class word) alongside the specific names.
  Do NOT replace broad coverage with only a named list.

- LOW_OBSERVABILITY_GUARD:
  Every mandatory AND block must contain at least one HIGH-OBSERVABILITY term that primary studies commonly print.
  Do NOT use umbrella-only labels, administrative labels, or recruitment-setting labels as the sole content of a mandatory block.
  If a candidate block cannot be expressed with high-observability terms, omit it or fold it into an adjacent block as optional OR.

- MECHANISM_EXTENSION_RULE:
  When inclusion criteria explicitly include in vitro or animal-model studies on pathogenic mechanisms,
  the CONDITION block should include broad mechanism terms as OR alternatives alongside disease-specific terms.
  Do NOT treat such mechanism terms as forbidden outcome measures in that setting.

- ALTERNATIVE_ARM_PRESERVATION_RULE:
  When inclusion criteria define two distinct eligible arms, preserve the OR structure:
    (ArmA_terms) OR (ArmB_terms)
  Do NOT collapse distinct eligible arms into one AND gate.
  If arms have different date windows, apply no date filter.

- DATE_LANGUAGE_GUARD:
  Apply date or language filters only when inclusion criteria explicitly require them for ALL included studies.
  Do NOT convert exclusion-only date limits into mandatory filters.
  Default: omit date and language filters unless universally mandatory.

- Before turning any criterion into an AND block, ask:
  1. Is it a searchable domain concept rather than a screening rule?
  2. Is it highly observable in titles/abstracts or MeSH?
  3. Is it important enough to spend one of the limited AND slots?
  If any answer is no, prefer OR-extension or screening rather than a new mandatory block.

- For one-shot generation, prefer recall-preserving assignment when a term is ambiguous.
- If a criterion is not directly queryable in PubMed (e.g., sample size threshold), leave it for screening.

- MeSH PROTECTION RULE:
  MeSH terms and [tiab] terms are complementary, not interchangeable.
  Do NOT remove a MeSH term from a slot solely because a similar [tiab] term is present.

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
| LAW_001 | RECALL_PROTECTIVE | RESTORE_PRIMARY | FILTER.STUDY_DESIGN | RESTORE_BROAD | PRIMARY | PRIMARY.CONDITION_OR_POPULATION | RevertAllFieldsOrMesh | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION_OR_POPULATION when coverage is incomplete. | Example: If prior step over-restricted PRIMARY.CONDITION_OR_POPULATION, restore TERM_A from [tiab] to All Fields or Mesh. | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 6 | 05_Infectious_Diseases/41770456_2026/search_history.jsonl, 05_Infectious_Diseases/41781415_2026/search_history.jsonl, 05_Infectious_Diseases/41789521_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | STRONG | 1.00 | 1.00 | 0.83 | 0.86 | 0.721 | 0.000 | 0.000 | 0.721 |
| LAW_002 | RECALL_PROTECTIVE | INITIAL_PRIMARY | PRIMARY.OTHER | BUILD_BASE | PRIMARY | CONDITION+POPULATION(+INTERVENTION if required) | AllFieldsOrMesh | To protect recall, apply INITIAL_PRIMARY to PRIMARY/CONDITION+POPULATION(+INTERVENTION if required) when coverage is incomplete. | Example: Build PRIMARY as (CONDITION_X OR CONDITION_Y) AND (INTERVENTION_Z OR TERM_A). AND BLOCK BUDGET: Use 2-3 AND blocks maximum. Only CONDITION and INTERVENTION/EXPOSURE are mandatory AND blocks. Delivery mode, modality, context, and provider blocks are optional. STUDY_FILTER: Add only when inclusion criteria restrict to a SINGLE mandatory design type (e.g., 'RCTs only' with observational excluded). A conjunctive listing ('RCT and observational') counts as 2+ types -> OMIT STUDY_FILTER. STUDY_FILTER TEMPLATE when needed: ("Randomized Controlled Trial"[pt] OR "Controlled Clinical Trial"[pt] OR randomized[tiab] OR randomised[tiab] OR randomly[tiab] OR trial[ti]). SPECIFIC-INSTANCES RULE: When a broad category concept contains named specific instances (e.g., specific biomarker names like CRP, ESR, TNF-alpha; specific drug names; vaccine brand names; specific gene names), enumerate those specific instances individually as tiab terms ALONGSIDE the broad MeSH. Never remove the broad class term. BROAD FALLBACK FLOOR: Every block must retain at least one broad class term (broad MeSH OR broad tiab like biomarker*, vaccin*, substance*) even when specific instances are listed. | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 4 | 05_Infectious_Diseases/41770456_2026/search_history.jsonl, 05_Infectious_Diseases/41781415_2026/search_history.jsonl, 05_Infectious_Diseases/41789521_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | STRONG | 1.00 | 0.75 | 0.75 | 0.74 | 0.414 | 0.000 | 0.000 | 0.414 |
| LAW_003 | RECALL_PROTECTIVE | ADD_FIELD_TAG | PRIMARY.MESH | ADD_OR | PRIMARY | PRIMARY.MESH | MeshPlusTextBackup | To protect recall, apply ADD_FIELD_TAG to PRIMARY/PRIMARY.MESH when coverage is incomplete. | Example: Pair core term with field tag: ("TERM_A"[Mesh] OR "TERM_A"[tiab]). | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 7 | 05_Infectious_Diseases/41781415_2026/search_history.jsonl, 05_Infectious_Diseases/41789521_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | STRONG | 0.75 | 0.71 | 0.71 | 0.90 | 0.344 | 0.000 | 0.000 | 0.344 |
| LAW_004 | RECALL_PROTECTIVE | REMOVE_FIELD_TAG | FILTER.MESH | REMOVE_OR | FILTER | FILTER.MESH | KeepTextBackup | To protect recall, apply REMOVE_FIELD_TAG to FILTER/FILTER.MESH when coverage is incomplete. | Example: Remove Mesh-only TERM_B but retain text backup ("TERM_B"[tiab]) to protect recall. | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 3 | 05_Infectious_Diseases/41789521_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | STRONG | 0.46 | 1.00 | 1.00 | 0.63 | 0.291 | 0.000 | 0.000 | 0.291 |
| LAW_005 | RECALL_PROTECTIVE | EXPAND_PRIMARY | PRIMARY.INTERVENTION | ADD_OR | PRIMARY | PRIMARY.INTERVENTION | AllFieldsOrMesh | To protect recall, apply EXPAND_PRIMARY to PRIMARY/PRIMARY.INTERVENTION when coverage is incomplete. | Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); add synonym TERM_B to slot PRIMARY.INTERVENTION; After PRIMARY includes TERM_B by OR. | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 6 | 05_Infectious_Diseases/41781415_2026/search_history.jsonl, 05_Infectious_Diseases/41789521_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | STRONG | 0.75 | 0.67 | 0.67 | 0.86 | 0.287 | 0.000 | 0.000 | 0.287 |
| LAW_006 | RECALL_PROTECTIVE | EXPAND_FILTER | FILTER.STUDY_DESIGN | ADD_OR | FILTER | STUDY_DESIGN | PublicationTypePlusBackup | To protect recall, apply EXPAND_FILTER to FILTER/STUDY_DESIGN when coverage is incomplete. | Example: Before FILTER=(DESIGN_MESH OR DESIGN_TEXT); add DESIGN_ALT by OR; keep publication-type backup. | coverage is incomplete | law is unmapped or unsafe | Increase | Increase | Noise Gain | 4 | 05_Infectious_Diseases/41781415_2026/search_history.jsonl, 05_Infectious_Diseases/41789521_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | STRONG | 0.75 | 0.50 | 0.50 | 0.74 | 0.137 | 0.000 | 0.000 | 0.137 |
| LAW_007 | NOISE_REDUCTION | RESTRICT_FIELD | FILTER.STUDY_DESIGN | RESTRICT_FIELD | FILTER | FILTER.STUDY_DESIGN | tiab_only_for_auxiliary | To reduce noise, apply RESTRICT_FIELD to FILTER/FILTER.STUDY_DESIGN when core concepts are stabilized and hits are excessive. | Example: Keep slot FILTER.STUDY_DESIGN but restrict auxiliary TERM_E to [tiab]; do not touch core CONDITION_X/INTERVENTION_Z. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 4 | 05_Infectious_Diseases/41789521_2026/search_history.jsonl | STRONG | 0.29 | 1.00 | 1.00 | 0.74 | 0.210 | 0.000 | 0.000 | 0.210 |
| LAW_008 | NOISE_REDUCTION | RESTORE_PRIMARY | PRIMARY.CONDITION | RESTORE_BROAD | PRIMARY | PRIMARY.CONDITION | RevertAllFieldsOrMesh | To reduce noise, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION when core concepts are stabilized and hits are excessive. | Example: If prior step over-restricted PRIMARY.CONDITION, restore TERM_A from [tiab] to All Fields or Mesh. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 2 | 05_Infectious_Diseases/41781415_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | MODERATE | 0.46 | 1.00 | 1.00 | 0.49 | 0.224 | 0.000 | 0.100 | 0.174 |
| LAW_009 | NOISE_REDUCTION | RESTORE_PRIMARY | CONTEXT.POPULATION | RESTORE_BROAD | PRIMARY | PRIMARY.CONDITION_OR_POPULATION | RevertAllFieldsOrMesh | To reduce noise, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION_OR_POPULATION when core concepts are stabilized and hits are excessive. | Example: If prior step over-restricted PRIMARY.CONDITION_OR_POPULATION, restore TERM_A from [tiab] to All Fields or Mesh. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 1 | 05_Infectious_Diseases/41781415_2026/search_history.jsonl | WEAK | 0.29 | 1.00 | 1.00 | 0.28 | 0.081 | 0.000 | 0.100 | 0.031 |
| LAW_010 | NOISE_REDUCTION | REMOVE_FIELD_TAG | PRIMARY.TIAB | REMOVE_OR | PRIMARY | PRIMARY.TIAB | AvoidRemovingCoreTiab | To reduce noise, remove peripheral tiab variants from PRIMARY only when MeSH fully covers the concept and total hits are excessive; never remove tiab from core CONDITION, POPULATION, or INTERVENTION slots. | Example: Remove peripheral tiab variant TERM_E[tiab] only when MeSH fully covers concept; retain core tiab. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 14 | 05_Infectious_Diseases/41770456_2026/search_history.jsonl, 05_Infectious_Diseases/41781415_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | STRONG | 0.71 | 0.79 | 0.79 | 0.99 | 0.437 | 0.000 | 1.000 | -0.063 |
| LAW_011 | NOISE_REDUCTION | RESTRICT_PRIMARY | PRIMARY.CONDITION | REMOVE_OR | PRIMARY | PRIMARY.CONDITION | KeepBroadCore | To reduce noise, apply RESTRICT_PRIMARY to PRIMARY/PRIMARY.CONDITION when core concepts are stabilized and hits are excessive. | Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); remove low-value TERM_C from slot PRIMARY.CONDITION; keep CONDITION_X and POPULATION_Y. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 10 | 05_Infectious_Diseases/41770456_2026/search_history.jsonl, 05_Infectious_Diseases/41781415_2026/search_history.jsonl | STRONG | 0.54 | 0.80 | 0.80 | 0.96 | 0.333 | 0.000 | 0.900 | -0.117 |
| LAW_012 | NOISE_REDUCTION | RESTRICT_PRIMARY | PRIMARY.INTERVENTION | REMOVE_OR | PRIMARY | PRIMARY.INTERVENTION | KeepBroadCore | To reduce noise, apply RESTRICT_PRIMARY to PRIMARY/PRIMARY.INTERVENTION when core concepts are stabilized and hits are excessive. | Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); remove low-value TERM_C from slot PRIMARY.INTERVENTION; keep CONDITION_X and POPULATION_Y. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 2 | 05_Infectious_Diseases/41770456_2026/search_history.jsonl, 05_Infectious_Diseases/41781415_2026/search_history.jsonl | MODERATE | 0.54 | 0.50 | 0.50 | 0.49 | 0.066 | 0.000 | 0.900 | -0.384 |
| LAW_013 | NOISE_REDUCTION | REMOVE_FIELD_TAG | PRIMARY.MESH | REMOVE_OR | PRIMARY | PRIMARY.MESH | KeepTextBackup | To reduce noise, apply REMOVE_FIELD_TAG to PRIMARY/PRIMARY.MESH when core concepts are stabilized and hits are excessive. | Example: Remove Mesh-only TERM_B but retain text backup ("TERM_B"[tiab]) to protect recall. | core concepts are stabilized and hits are excessive | recall is dropping or core terms would be narrowed | Neutral | Decrease | None | 1 | 05_Infectious_Diseases/41781415_2026/search_history.jsonl | WEAK | 0.29 | 1.00 | 1.00 | 0.28 | 0.081 | 0.000 | 1.000 | -0.419 |
| LAW_014 | CONDITIONAL | ADD_FIELD_TAG | FILTER.TIAB | ADD_OR | FILTER | FILTER.TIAB | tiab_synonym_expansion | [ONE-SHOT-GUIDANCE: ADD_TIAB] In initial query construction, include tiab synonyms in FILTER for variant spellings and abbreviations not covered by MeSH. Pair tiab terms with MeSH equivalents where possible: ("TERM"[Mesh] OR "TERM"[tiab]). Do not use tiab as sole coverage for core CONDITION or INTERVENTION slots. NAMED-INSTANCES RULE: When a slot contains a broad category concept (e.g., Biomarkers, Heat-Shock Proteins, Membranes, Vaccines) AND the paper involves specific named instances of that category (e.g., specific protein names, specific drug names, specific gene variants, vaccine brand/strain names), add those specific instance names as tiab terms. BROAD FALLBACK FLOOR: Always keep the broad class MeSH and at least one broad tiab alongside the specific names - never replace broad coverage with only a named list. Example: ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab]) is correct; (CRP[tiab] OR ESR[tiab]) alone is incorrect. INTERVENTION VARIANT COVERAGE: For intervention classes with many historical variants (vaccines, biologics, antiseptics), include generation names, brand names, strain names, and broad class terms. Wildcard (vaccin*, biologic*) covers unknown variants. | Example: Add tiab synonym alongside MeSH: ("TERM_C"[Mesh] OR TERM_C*[tiab] OR TERM_D*[tiab]). | recall is below target and expansion is needed | noise increases excessively or recall starts to drop | Increase | Increase | Recall Loss | 7 | 05_Infectious_Diseases/41770456_2026/search_history.jsonl, 05_Infectious_Diseases/41781415_2026/search_history.jsonl, 05_Infectious_Diseases/41789521_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | STRONG | 1.00 | 0.57 | 0.57 | 0.90 | 0.295 | 0.143 | 0.000 | 0.181 |
| LAW_015 | CONDITIONAL | ADD_FIELD_TAG | PRIMARY.TIAB | ADD_OR | PRIMARY | PRIMARY.TIAB | tiab_synonym_expansion | [ONE-SHOT-GUIDANCE: ADD_TIAB] In initial query construction, include tiab synonyms in PRIMARY for variant spellings and abbreviations not covered by MeSH. Pair tiab terms with MeSH equivalents where possible: ("TERM"[Mesh] OR "TERM"[tiab]). Do not use tiab as sole coverage for core CONDITION or INTERVENTION slots. NAMED-INSTANCES RULE: When a slot contains a broad category concept (e.g., Biomarkers, Heat-Shock Proteins, Membranes, Vaccines) AND the paper involves specific named instances of that category (e.g., specific protein names, specific drug names, specific gene variants, vaccine brand/strain names), add those specific instance names as tiab terms. BROAD FALLBACK FLOOR: Always keep the broad class MeSH and at least one broad tiab alongside the specific names - never replace broad coverage with only a named list. Example: ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab]) is correct; (CRP[tiab] OR ESR[tiab]) alone is incorrect. INTERVENTION VARIANT COVERAGE: For intervention classes with many historical variants (vaccines, biologics, antiseptics), include generation names, brand names, strain names, and broad class terms. Wildcard (vaccin*, biologic*) covers unknown variants. | Example: Add tiab synonym alongside MeSH: ("TERM_C"[Mesh] OR TERM_C*[tiab] OR TERM_D*[tiab]). | recall is below target and expansion is needed | noise increases excessively or recall starts to drop | Increase | Increase | Noise Gain | 12 | 05_Infectious_Diseases/41781415_2026/search_history.jsonl, 05_Infectious_Diseases/41789521_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | STRONG | 0.75 | 0.42 | 0.42 | 0.98 | 0.127 | 0.000 | 0.000 | 0.127 |
| LAW_016 | CONDITIONAL | EXPAND_PRIMARY | PRIMARY.CONDITION | ADD_OR | PRIMARY | PRIMARY.CONDITION | AllFieldsOrMesh | [ONE-SHOT-GUIDANCE] When building the initial query, applying EXPAND_PRIMARY to PRIMARY/PRIMARY.CONDITION tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. | Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); add synonym TERM_B to slot PRIMARY.CONDITION; After PRIMARY includes TERM_B by OR. | recall is below target and expansion is needed | noise increases excessively or recall starts to drop | Increase | Increase | Noise Gain | 7 | 05_Infectious_Diseases/41781415_2026/search_history.jsonl, 05_Infectious_Diseases/41789521_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | STRONG | 0.75 | 0.29 | 0.57 | 0.90 | 0.110 | 0.000 | 0.000 | 0.110 |
| LAW_017 | CONDITIONAL | EXPAND_PRIMARY | CONTEXT.POPULATION | ADD_OR | PRIMARY | CONTEXT.POPULATION | AllFieldsOrMeshOrTiab | [ONE-SHOT-GUIDANCE] When building the initial query, applying EXPAND_PRIMARY to PRIMARY/CONTEXT.POPULATION tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. IMPORTANT: For ethnicity/geography/cultural-minority terms, add terms by OR within the existing population/context structure. Avoid an independent AND block for those terms because it often over-restricts recall. Exception: age/developmental-stage criteria (e.g., child, adolescent, adult) may be an independent AND population block when explicitly definitional in the inclusion criteria. | Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); add synonym TERM_B to slot CONTEXT.POPULATION; After PRIMARY includes TERM_B by OR. | recall is below target and expansion is needed | noise increases excessively or recall starts to drop | Increase | Increase | Noise Gain | 4 | 05_Infectious_Diseases/41781415_2026/search_history.jsonl, 05_Infectious_Diseases/41789521_2026/search_history.jsonl | STRONG | 0.57 | 0.25 | 0.75 | 0.74 | 0.079 | 0.000 | 0.000 | 0.079 |
| LAW_018 | CONDITIONAL | RESTRICT_FILTER | FILTER.STUDY_DESIGN | REMOVE_OR | FILTER | STUDY_DESIGN | KeepDesignBackup | [ONE-SHOT-GUIDANCE] RESTRICT_FILTER on FILTER/STUDY_DESIGN shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when inclusion criteria clearly support it, defined as: the review restricts to EXACTLY ONE specific study design type AND that restriction is explicitly stated as mandatory (not merely preferred or listed as an example). If inclusion criteria mention two or more design types, or if the restriction is ambiguous, do NOT apply this action. | Example: Before FILTER=(DESIGN_MESH OR DESIGN_TEXT); remove broad TERM_D; keep at least one design backup. | recall is below target and expansion is needed | noise increases excessively or recall starts to drop | Decrease | Decrease | Recall Loss | 17 | 05_Infectious_Diseases/41770456_2026/search_history.jsonl, 05_Infectious_Diseases/41789521_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | STRONG | 0.71 | 0.59 | 0.59 | 1.00 | 0.246 | 0.247 | 0.000 | 0.049 |
| LAW_019 | AVOID | REMOVE_FIELD_TAG | FILTER.TIAB | REMOVE_OR | FILTER | FILTER.TIAB | AvoidRemovingCoreTiab | [AVOID] Do not remove tiab terms from FILTER unless a MeSH equivalent fully covers all variant spellings of the concept. Removing tiab without MeSH backup is the primary cause of recall loss in this dataset. When in doubt, retain tiab coverage. | Example (do not execute): REMOVE_FIELD_TAG on FILTER/FILTER.TIAB; keep baseline blocks unchanged. | never | always | Increase | Decrease | Recall Loss | 12 | 05_Infectious_Diseases/41770456_2026/search_history.jsonl, 05_Infectious_Diseases/41781415_2026/search_history.jsonl, 05_Infectious_Diseases/41789521_2026/search_history.jsonl, 05_Infectious_Diseases/41790564_2026/search_history.jsonl | STRONG | 1.00 | 0.83 | 0.75 | 0.98 | 0.614 | 0.167 | 0.000 | 0.480 |
| LAW_020 | AVOID | ADD_FIELD_TAG | FILTER.MESH | ADD_OR | FILTER | FILTER.MESH | MeshPlusTextBackup | Avoid applying ADD_FIELD_TAG; this action is unsafe under always. | Example (do not execute): ADD_FIELD_TAG on FILTER/FILTER.MESH; keep baseline blocks unchanged. | never | always | Decrease | Decrease | Recall Loss | 1 | 05_Infectious_Diseases/41790564_2026/search_history.jsonl | WEAK | 0.17 | 0.00 | 1.00 | 0.28 | 0.000 | 1.444 | 0.000 | -1.156 |

# SECTION_2_COMPACT_DEPLOYMENT_LAWS
## GLOBAL_DO_LAWS
[01] LAW_001 | RECALL_PROTECTIVE | RESTORE_BROAD/PRIMARY/PRIMARY.CONDITION_OR_POPULATION | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION_OR_POPULATION when coverage is incomplete. | Example=Example: If prior step over-restricted PRIMARY.CONDITION_OR_POPULATION, restore TERM_A from [tiab] to All Fields or Mesh. | Rep/Suc/Con/Sup=1.00/1.00/0.83/0.86 | DeployScore=0.721
[02] LAW_002 | RECALL_PROTECTIVE | BUILD_BASE/PRIMARY/CONDITION+POPULATION(+INTERVENTION if required) | To protect recall, apply INITIAL_PRIMARY to PRIMARY/CONDITION+POPULATION(+INTERVENTION if required) when coverage is incomplete. | Example=Example: Build PRIMARY as (CONDITION_X OR CONDITION_Y) AND (INTERVENTION_Z OR TERM_A). AND BLOCK BUDGET: Use 2-3 AND blocks maximum. Only CONDITION and INTERVENTION/EXPOSURE are mandatory AND blocks. Delivery mode, modality, context, and provider blocks are optional. STUDY_FILTER: Add only when inclusion criteria restrict to a SINGLE mandatory design type (e.g., 'RCTs only' with observational excluded). A conjunctive listing ('RCT and observational') counts as 2+ types -> OMIT STUDY_FILTER. STUDY_FILTER TEMPLATE when needed: ("Randomized Controlled Trial"[pt] OR "Controlled Clinical Trial"[pt] OR randomized[tiab] OR randomised[tiab] OR randomly[tiab] OR trial[ti]). SPECIFIC-INSTANCES RULE: When a broad category concept contains named specific instances (e.g., specific biomarker names like CRP, ESR, TNF-alpha; specific drug names; vaccine brand names; specific gene names), enumerate those specific instances individually as tiab terms ALONGSIDE the broad MeSH. Never remove the broad class term. BROAD FALLBACK FLOOR: Every block must retain at least one broad class term (broad MeSH OR broad tiab like biomarker*, vaccin*, substance*) even when specific instances are listed. | Rep/Suc/Con/Sup=1.00/0.75/0.75/0.74 | DeployScore=0.414
[03] LAW_003 | RECALL_PROTECTIVE | ADD_OR/PRIMARY/PRIMARY.MESH | To protect recall, apply ADD_FIELD_TAG to PRIMARY/PRIMARY.MESH when coverage is incomplete. | Example=Example: Pair core term with field tag: ("TERM_A"[Mesh] OR "TERM_A"[tiab]). | Rep/Suc/Con/Sup=0.75/0.71/0.71/0.90 | DeployScore=0.344
[04] LAW_004 | RECALL_PROTECTIVE | REMOVE_OR/FILTER/FILTER.MESH | To protect recall, apply REMOVE_FIELD_TAG to FILTER/FILTER.MESH when coverage is incomplete. | Example=Example: Remove Mesh-only TERM_B but retain text backup ("TERM_B"[tiab]) to protect recall. | Rep/Suc/Con/Sup=0.46/1.00/1.00/0.63 | DeployScore=0.291
[05] LAW_005 | RECALL_PROTECTIVE | ADD_OR/PRIMARY/PRIMARY.INTERVENTION | To protect recall, apply EXPAND_PRIMARY to PRIMARY/PRIMARY.INTERVENTION when coverage is incomplete. | Example=Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); add synonym TERM_B to slot PRIMARY.INTERVENTION; After PRIMARY includes TERM_B by OR. | Rep/Suc/Con/Sup=0.75/0.67/0.67/0.86 | DeployScore=0.287
[06] LAW_007 | NOISE_REDUCTION | RESTRICT_FIELD/FILTER/FILTER.STUDY_DESIGN | To reduce noise, apply RESTRICT_FIELD to FILTER/FILTER.STUDY_DESIGN when core concepts are stabilized and hits are excessive. | Example=Example: Keep slot FILTER.STUDY_DESIGN but restrict auxiliary TERM_E to [tiab]; do not touch core CONDITION_X/INTERVENTION_Z. | Rep/Suc/Con/Sup=0.29/1.00/1.00/0.74 | DeployScore=0.210
[07] LAW_014 | CONDITIONAL | ADD_OR/FILTER/FILTER.TIAB | [ONE-SHOT-GUIDANCE: ADD_TIAB] In initial query construction, include tiab synonyms in FILTER for variant spellings and abbreviations not covered by MeSH. Pair tiab terms with MeSH equivalents where possible: ("TERM"[Mesh] OR "TERM"[tiab]). Do not use tiab as sole coverage for core CONDITION or INTERVENTION slots. NAMED-INSTANCES RULE: When a slot contains a broad category concept (e.g., Biomarkers, Heat-Shock Proteins, Membranes, Vaccines) AND the paper involves specific named instances of that category (e.g., specific protein names, specific drug names, specific gene variants, vaccine brand/strain names), add those specific instance names as tiab terms. BROAD FALLBACK FLOOR: Always keep the broad class MeSH and at least one broad tiab alongside the specific names - never replace broad coverage with only a named list. Example: ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab]) is correct; (CRP[tiab] OR ESR[tiab]) alone is incorrect. INTERVENTION VARIANT COVERAGE: For intervention classes with many historical variants (vaccines, biologics, antiseptics), include generation names, brand names, strain names, and broad class terms. Wildcard (vaccin*, biologic*) covers unknown variants. | Example=Example: Add tiab synonym alongside MeSH: ("TERM_C"[Mesh] OR TERM_C*[tiab] OR TERM_D*[tiab]). | Rep/Suc/Con/Sup=1.00/0.57/0.57/0.90 | DeployScore=0.181
[08] LAW_008 | NOISE_REDUCTION | RESTORE_BROAD/PRIMARY/PRIMARY.CONDITION | To reduce noise, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION when core concepts are stabilized and hits are excessive. | Example=Example: If prior step over-restricted PRIMARY.CONDITION, restore TERM_A from [tiab] to All Fields or Mesh. | Rep/Suc/Con/Sup=0.46/1.00/1.00/0.49 | DeployScore=0.174
[09] LAW_006 | RECALL_PROTECTIVE | ADD_OR/FILTER/STUDY_DESIGN | To protect recall, apply EXPAND_FILTER to FILTER/STUDY_DESIGN when coverage is incomplete. | Example=Example: Before FILTER=(DESIGN_MESH OR DESIGN_TEXT); add DESIGN_ALT by OR; keep publication-type backup. | Rep/Suc/Con/Sup=0.75/0.50/0.50/0.74 | DeployScore=0.137
[10] LAW_015 | CONDITIONAL | ADD_OR/PRIMARY/PRIMARY.TIAB | [ONE-SHOT-GUIDANCE: ADD_TIAB] In initial query construction, include tiab synonyms in PRIMARY for variant spellings and abbreviations not covered by MeSH. Pair tiab terms with MeSH equivalents where possible: ("TERM"[Mesh] OR "TERM"[tiab]). Do not use tiab as sole coverage for core CONDITION or INTERVENTION slots. NAMED-INSTANCES RULE: When a slot contains a broad category concept (e.g., Biomarkers, Heat-Shock Proteins, Membranes, Vaccines) AND the paper involves specific named instances of that category (e.g., specific protein names, specific drug names, specific gene variants, vaccine brand/strain names), add those specific instance names as tiab terms. BROAD FALLBACK FLOOR: Always keep the broad class MeSH and at least one broad tiab alongside the specific names - never replace broad coverage with only a named list. Example: ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab]) is correct; (CRP[tiab] OR ESR[tiab]) alone is incorrect. INTERVENTION VARIANT COVERAGE: For intervention classes with many historical variants (vaccines, biologics, antiseptics), include generation names, brand names, strain names, and broad class terms. Wildcard (vaccin*, biologic*) covers unknown variants. | Example=Example: Add tiab synonym alongside MeSH: ("TERM_C"[Mesh] OR TERM_C*[tiab] OR TERM_D*[tiab]). | Rep/Suc/Con/Sup=0.75/0.42/0.42/0.98 | DeployScore=0.127
[11] LAW_016 | CONDITIONAL | ADD_OR/PRIMARY/PRIMARY.CONDITION | [ONE-SHOT-GUIDANCE] When building the initial query, applying EXPAND_PRIMARY to PRIMARY/PRIMARY.CONDITION tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. | Example=Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); add synonym TERM_B to slot PRIMARY.CONDITION; After PRIMARY includes TERM_B by OR. | Rep/Suc/Con/Sup=0.75/0.29/0.57/0.90 | DeployScore=0.110
[12] LAW_017 | CONDITIONAL | ADD_OR/PRIMARY/CONTEXT.POPULATION | [ONE-SHOT-GUIDANCE] When building the initial query, applying EXPAND_PRIMARY to PRIMARY/CONTEXT.POPULATION tends to increase recall coverage. Include this in the initial build when broad coverage is a priority. IMPORTANT: For ethnicity/geography/cultural-minority terms, add terms by OR within the existing population/context structure. Avoid an independent AND block for those terms because it often over-restricts recall. Exception: age/developmental-stage criteria (e.g., child, adolescent, adult) may be an independent AND population block when explicitly definitional in the inclusion criteria. | Example=Example: Before PRIMARY=(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A); add synonym TERM_B to slot CONTEXT.POPULATION; After PRIMARY includes TERM_B by OR. | Rep/Suc/Con/Sup=0.57/0.25/0.75/0.74 | DeployScore=0.079

## GLOBAL_AVOID_LAWS
[01] LAW_019 | AVOID | REMOVE_OR/FILTER/FILTER.TIAB | [AVOID] Do not remove tiab terms from FILTER unless a MeSH equivalent fully covers all variant spellings of the concept. Removing tiab without MeSH backup is the primary cause of recall loss in this dataset. When in doubt, retain tiab coverage. | Example=Example (do not execute): REMOVE_FIELD_TAG on FILTER/FILTER.TIAB; keep baseline blocks unchanged. | Risk=Recall Loss | Rep/Suc/Con/Sup=1.00/0.83/0.75/0.98
[02] LAW_020 | AVOID | ADD_OR/FILTER/FILTER.MESH | Avoid applying ADD_FIELD_TAG; this action is unsafe under always. | Example=Example (do not execute): ADD_FIELD_TAG on FILTER/FILTER.MESH; keep baseline blocks unchanged. | Risk=Recall Loss | Rep/Suc/Con/Sup=0.17/0.00/1.00/0.28
[03] LAW_014 | CONDITIONAL | ADD_OR/FILTER/FILTER.TIAB | [ONE-SHOT-GUIDANCE: ADD_TIAB] In initial query construction, include tiab synonyms in FILTER for variant spellings and abbreviations not covered by MeSH. Pair tiab terms with MeSH equivalents where possible: ("TERM"[Mesh] OR "TERM"[tiab]). Do not use tiab as sole coverage for core CONDITION or INTERVENTION slots. NAMED-INSTANCES RULE: When a slot contains a broad category concept (e.g., Biomarkers, Heat-Shock Proteins, Membranes, Vaccines) AND the paper involves specific named instances of that category (e.g., specific protein names, specific drug names, specific gene variants, vaccine brand/strain names), add those specific instance names as tiab terms. BROAD FALLBACK FLOOR: Always keep the broad class MeSH and at least one broad tiab alongside the specific names - never replace broad coverage with only a named list. Example: ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab]) is correct; (CRP[tiab] OR ESR[tiab]) alone is incorrect. INTERVENTION VARIANT COVERAGE: For intervention classes with many historical variants (vaccines, biologics, antiseptics), include generation names, brand names, strain names, and broad class terms. Wildcard (vaccin*, biologic*) covers unknown variants. | Example=Example: Add tiab synonym alongside MeSH: ("TERM_C"[Mesh] OR TERM_C*[tiab] OR TERM_D*[tiab]). | Risk=Recall Loss | Rep/Suc/Con/Sup=1.00/0.57/0.57/0.90
[04] LAW_018 | CONDITIONAL | REMOVE_OR/FILTER/STUDY_DESIGN | [ONE-SHOT-GUIDANCE] RESTRICT_FILTER on FILTER/STUDY_DESIGN shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when inclusion criteria clearly support it, defined as: the review restricts to EXACTLY ONE specific study design type AND that restriction is explicitly stated as mandatory (not merely preferred or listed as an example). If inclusion criteria mention two or more design types, or if the restriction is ambiguous, do NOT apply this action. | Example=Example: Before FILTER=(DESIGN_MESH OR DESIGN_TEXT); remove broad TERM_D; keep at least one design backup. | Risk=Recall Loss | Rep/Suc/Con/Sup=0.71/0.59/0.59/1.00

# SECTION_3_DOMAIN_SPECIFIC_LAWS
# Laws below derive from per-domain subsets. Consult these when the target domain is known.
# Domain laws override global laws when Divergence_Reason is set.
# Domain laws supplement global laws (additional context) otherwise.

## DOMAIN_05_Infectious_Diseases
# No significant divergence from global laws detected. Global laws apply.

### DOMAIN_05_Infectious_Diseases_TOP_DO_LAWS
  [01] LAW_001 | RECALL_PROTECTIVE | RESTORE_BROAD/PRIMARY/PRIMARY.CONDITION_OR_POPULATION | To protect recall, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION_OR_POPULATION when coverage is incomplete. | Rep/Suc/Con/Sup=1.00/1.00/0.83/0.86
  [02] LAW_002 | RECALL_PROTECTIVE | BUILD_BASE/PRIMARY/CONDITION+POPULATION(+INTERVENTION if required) | To protect recall, apply INITIAL_PRIMARY to PRIMARY/CONDITION+POPULATION(+INTERVENTION if required) when coverage is incomplete. | Rep/Suc/Con/Sup=1.00/0.75/0.75/0.74
  [03] LAW_003 | RECALL_PROTECTIVE | ADD_OR/PRIMARY/PRIMARY.MESH | To protect recall, apply ADD_FIELD_TAG to PRIMARY/PRIMARY.MESH when coverage is incomplete. | Rep/Suc/Con/Sup=0.75/0.71/0.71/0.90
  [04] LAW_004 | RECALL_PROTECTIVE | REMOVE_OR/FILTER/FILTER.MESH | To protect recall, apply REMOVE_FIELD_TAG to FILTER/FILTER.MESH when coverage is incomplete. | Rep/Suc/Con/Sup=0.46/1.00/1.00/0.63
  [05] LAW_005 | RECALL_PROTECTIVE | ADD_OR/PRIMARY/PRIMARY.INTERVENTION | To protect recall, apply EXPAND_PRIMARY to PRIMARY/PRIMARY.INTERVENTION when coverage is incomplete. | Rep/Suc/Con/Sup=0.75/0.67/0.67/0.86
  [06] LAW_007 | NOISE_REDUCTION | RESTRICT_FIELD/FILTER/FILTER.STUDY_DESIGN | To reduce noise, apply RESTRICT_FIELD to FILTER/FILTER.STUDY_DESIGN when core concepts are stabilized and hits are excessive. | Rep/Suc/Con/Sup=0.29/1.00/1.00/0.74
  [07] LAW_014 | CONDITIONAL | ADD_OR/FILTER/FILTER.TIAB | [ONE-SHOT-GUIDANCE: ADD_TIAB] In initial query construction, include tiab synonyms in FILTER for variant spellings and abbreviations not covered by MeSH. Pair tiab terms with MeSH equivalents where possible: ("TERM"[Mesh] OR "TERM"[tiab]). Do not use tiab as sole coverage for core CONDITION or INTERVENTION slots. NAMED-INSTANCES RULE: When a slot contains a broad category concept (e.g., Biomarkers, Heat-Shock Proteins, Membranes, Vaccines) AND the paper involves specific named instances of that category (e.g., specific protein names, specific drug names, specific gene variants, vaccine brand/strain names), add those specific instance names as tiab terms. BROAD FALLBACK FLOOR: Always keep the broad class MeSH and at least one broad tiab alongside the specific names - never replace broad coverage with only a named list. Example: ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab]) is correct; (CRP[tiab] OR ESR[tiab]) alone is incorrect. INTERVENTION VARIANT COVERAGE: For intervention classes with many historical variants (vaccines, biologics, antiseptics), include generation names, brand names, strain names, and broad class terms. Wildcard (vaccin*, biologic*) covers unknown variants. | Rep/Suc/Con/Sup=1.00/0.57/0.57/0.90
  [08] LAW_008 | NOISE_REDUCTION | RESTORE_BROAD/PRIMARY/PRIMARY.CONDITION | To reduce noise, apply RESTORE_PRIMARY to PRIMARY/PRIMARY.CONDITION when core concepts are stabilized and hits are excessive. | Rep/Suc/Con/Sup=0.46/1.00/1.00/0.49

### DOMAIN_05_Infectious_Diseases_TOP_AVOID_LAWS
  [01] LAW_019 | AVOID | REMOVE_OR/FILTER/FILTER.TIAB | [AVOID] Do not remove tiab terms from FILTER unless a MeSH equivalent fully covers all variant spellings of the concept. Removing tiab without MeSH backup is the primary cause of recall loss in this dataset. When in doubt, retain tiab coverage. | Risk=Recall Loss | Rep/Suc/Con/Sup=1.00/0.83/0.75/0.98
  [02] LAW_020 | AVOID | ADD_OR/FILTER/FILTER.MESH | Avoid applying ADD_FIELD_TAG; this action is unsafe under always. | Risk=Recall Loss | Rep/Suc/Con/Sup=0.17/0.00/1.00/0.28
  [03] LAW_014 | CONDITIONAL | ADD_OR/FILTER/FILTER.TIAB | [ONE-SHOT-GUIDANCE: ADD_TIAB] In initial query construction, include tiab synonyms in FILTER for variant spellings and abbreviations not covered by MeSH. Pair tiab terms with MeSH equivalents where possible: ("TERM"[Mesh] OR "TERM"[tiab]). Do not use tiab as sole coverage for core CONDITION or INTERVENTION slots. NAMED-INSTANCES RULE: When a slot contains a broad category concept (e.g., Biomarkers, Heat-Shock Proteins, Membranes, Vaccines) AND the paper involves specific named instances of that category (e.g., specific protein names, specific drug names, specific gene variants, vaccine brand/strain names), add those specific instance names as tiab terms. BROAD FALLBACK FLOOR: Always keep the broad class MeSH and at least one broad tiab alongside the specific names - never replace broad coverage with only a named list. Example: ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab]) is correct; (CRP[tiab] OR ESR[tiab]) alone is incorrect. INTERVENTION VARIANT COVERAGE: For intervention classes with many historical variants (vaccines, biologics, antiseptics), include generation names, brand names, strain names, and broad class terms. Wildcard (vaccin*, biologic*) covers unknown variants. | Risk=Recall Loss | Rep/Suc/Con/Sup=1.00/0.57/0.57/0.90
  [04] LAW_018 | CONDITIONAL | REMOVE_OR/FILTER/STUDY_DESIGN | [ONE-SHOT-GUIDANCE] RESTRICT_FILTER on FILTER/STUDY_DESIGN shows mixed effects across training cases. In initial query construction, favor recall over precision. Apply this action ONLY when inclusion criteria clearly support it, defined as: the review restricts to EXACTLY ONE specific study design type AND that restriction is explicitly stated as mandatory (not merely preferred or listed as an example). If inclusion criteria mention two or more design types, or if the restriction is ambiguous, do NOT apply this action. | Risk=Recall Loss | Rep/Suc/Con/Sup=0.71/0.59/0.59/1.00


```

You are an experienced Information Specialist.

Your task is to construct a PubMed search query that retrieves studies satisfying the objectives and inclusion criteria described in `input_config.json`.

You must rely ONLY on:
- The objectives and inclusion criteria in `input_config.json`
- `query_laws_ver*.txt`
This file (`query_laws_ver*.txt`) contains normalized one-shot query-construction laws and guardrails derived from prior optimization trajectories. Follow its non-negotiable rules and deployment guidance when constructing your single final query.

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

At the end, output your final PubMed query on a single line.
Output must contain only that single query line, with no prefix or explanation.

---

## ⚠ PHASE 5 CONTEXT — FULL QUERY REWRITE REQUIRED

The query below was generated and optimized through Stage A' Phases 1–4,
but still returns 73543 hits, exceeding the 9,999-hit target.

### Previous Query (after Stage A' Phases 1–4)
(stroke[tiab] OR "cerebrovascular accident"[tiab] OR "cerebrovascular disease"[tiab] OR "ischemic stroke"[tiab] OR "ischaemic stroke"[tiab] OR "haemorrhagic stroke"[tiab] OR "hemorrhagic stroke"[tiab] OR "brain infarction"[tiab] OR "cerebral infarction"[tiab]) AND ("Prognosis"[Mesh] OR "Models, Statistical"[Mesh] OR "prediction models"[tiab] OR "predictive model"[tiab] OR "prognostic model"[tiab] OR "risk model"[tiab] OR "risk score"[tiab] OR "risk prediction"[tiab] OR "clinical prediction rule"[tiab] OR "multivariable model"[tiab] OR "multivariate model"[tiab] OR "risk stratification"[tiab] OR "prognostic score"[tiab] OR "prediction tool"[tiab] OR "risk calculator"[tiab] OR "model development"[tiab] OR "model validation"[tiab] OR "external validation"[tiab] OR "prediction model* clinical prediction rule"[tiab:~5]) english[lang] NOT "Clinical Trial Protocol"[pt] NOT "Systematic Review"[pt] NOT "Retracted Publication"[pt] NOT "Preprint"[pt] NOT "Meeting Abstract"[pt] NOT "Case Reports"[pt] NOT (animals[mh] NOT humans[mh]) NOT "Comment"[pt] NOT "Editorial"[pt] NOT "News"[pt] NOT "Published Erratum"[pt]

### Current Total Hits: 73543  |  Target: < 9999

### Recall Information (Training Mode)
- Gold standard papers: 41
- Current recall after Phase 1–4: 0.8537  (TP = 35 / 41)
- Required minimum recall for acceptance: >= 0.8337  (ΔR tolerance = 0.02)
A proposed query is accepted only if hits < 9999 AND recall >= 0.8337.

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

Output exactly ONE line containing only the complete PubMed query.
