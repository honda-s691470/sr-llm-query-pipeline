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

## STEP 0 - Confirm paper identity
State: target_name=[value from input_config.json] | topic=[objectives in one sentence]
This must match the input_config.json you are processing. If uncertain, re-read input_config.json before continuing.

## STEP 1 - Study design filter decision
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

## STEP 2 - Classify each inclusion criterion
For each criterion in inclusion_criteria, assign one of:
    CORE      -> mandatory AND block  (disease/condition, intervention/exposure)
    NON-CORE  -> do NOT make a mandatory AND block

Non-core elements (must not become mandatory AND):
    - Delivery mode or platform  (digital, telehealth, mobile app, online)
    - Modality modifier          (multimodal, intraperitoneal, stereotactic)
    - Incidental/contextual qualifier  (incidentally detected, secondary finding)
    - Outcome measure            (mortality rate, QoL score, biomarker level)
      Exception A: outcome IS the study topic  (e.g., meta-analysis on PANQOL)
      Exception B: inclusion criteria use mandatory language: "must report X", "required to report X"
    - Date / language restrictions  -> apply ONLY if explicitly stated in inclusion_criteria
                                      and apply uniformly to ALL included study arms.
                                      When two arms have DIFFERENT date windows, omit date filters entirely.
    - Ethnicity / geography alone   -> fold into population block as OR terms, not a separate AND
    - Umbrella / category condition  (non-communicable diseases, chronic diseases,
                                      inflammatory diseases, complex chronic conditions)
      -> Primary studies use specific disease names (e.g., "type 2 diabetes", "hypertension"),
        not the umbrella label. Either enumerate major constituent disease/condition examples
        as OR terms alongside the umbrella, or omit the umbrella block if the INTERVENTION
        block already limits scope. NEVER use an umbrella-only label as the sole mandatory AND.
    - Broad biological mechanism     (inflammation, oxidative stress, NF-kappaB, JAK/STAT)
      -> Normally NON-CORE (outcome measure).
        Exception C: when inclusion criteria EXPLICITLY allow in vitro or animal-model studies
        on "models of inflammation" or "models of oxidative stress", include
        "Inflammation"[Mesh] / "Oxidative Stress"[Mesh] as OR alternatives IN the CONDITION
        block. Basic science papers study mechanisms WITHOUT naming the clinical disease; these
        terms are needed to capture them. Do NOT treat as outcome measures in this context.

## STEP 3 - AND block budget check
Count mandatory AND blocks planned.
    IF count > 3:
        Identify the least-core block and either:
        (a) fold its terms into an adjacent OR block, or
        (b) remove it
        Repeat until count <= 3.

## STEP 4 - Population / ethnicity structure check
    IF query contains ethnicity, nationality, migration-status, or host-country terms:
        ALL such terms must be in ONE flat OR block.
        Nested AND between nationality terms and diaspora/country terms is FORBIDDEN.
        Correct:   (Pakistani OR Bangladeshi OR Indian OR diaspora OR immigrant OR UK OR US)
        Incorrect: (Pakistani OR Bangladeshi OR Indian) AND (diaspora OR immigrant OR UK)

## STEP 5 - Broad fallback floor check
    FOR each block that lists specific named instances (drug names, biomarker names, vaccine names, compound names, etc.):
        PRESERVE all specific named instances - enumerate them individually in the query.
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
