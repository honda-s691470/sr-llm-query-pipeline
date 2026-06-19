"""
analyze_logs_ver2.py

Improvements over analyze_logs.py (v1):
  1. Log weighting by iteration count: harder papers carry proportionally more evidence weight.
     weight = clamp(n_iterations / 18.0, min=0.4, max=1.0)
  2. Bidirectional tiab laws: ADD_TIAB and REMOVE_TIAB emit separate context-aware imperatives
     instead of collapsing both into a single AVOID direction.
  3. CONDITIONAL laws reformulated as [ONE-SHOT-GUIDANCE: ...] preventive construction rules
     instead of iterative feedback-dependent conditions.
  4. Output includes global laws (SECTION_2) + per-domain supplementary laws (SECTION_3).
"""

import json
import math
import re
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "04_data"
OUTPUT_BASENAME = "query_laws"

CORE_SLOTS = {"PRIMARY.CONDITION", "PRIMARY.POPULATION", "PRIMARY.INTERVENTION"}
FIELD_BLOCKS = ("PRIMARY", "FILTER")
FIELD_BUCKETS = ("MESH", "TIAB", "MAJR")

WEIGHT_NORM = 18.0  # normalizer: iteration count at which weight reaches 1.0
MIN_WEIGHT = 0.4    # floor weight for short logs
ALPHA_RISK = 0.8    # penalty weight for recall-risk behavior
BETA_PRIMARY = 0.5  # penalty weight for restrictive PRIMARY-side operations

SECTION_00_REWRITE_BEGIN = "# SECTION_00_REWRITE_BEGIN"
SECTION_00_REWRITE_END = "# SECTION_00_REWRITE_END"
SECTION_00_EDITABLE_BLOCK = r"""
# SECTION_00_REWRITE_BEGIN
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
     fracture healing rate) here — these are screened at full-text, not searched in PubMed.
  2. POPULATION: age/sex/population subgroup/setting-human descriptors.
  3. EXPOSURE_INTERVENTION: treatment/exposure/behavior/activity/procedure terms.
  4. STUDY_DESIGN: design/method/publication-type terms (RCT, cohort, etc.).

- OUTCOME_MEASURE RULE (SECTION_00 NON-NEGOTIABLE):
  Study-level outcome measures (e.g., 'mortality', 'complication rate', 'fracture healing',
  'Burnout Index', 'Cognitive Load Level', 'quality of life score') describe what is MEASURED IN the study,
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
     CRITICAL — GEOGRAPHIC OBSERVABILITY: Studies conducted in a specific country
     or ethnic population frequently do NOT state that fact in the title or abstract.
     A study from Country_X may describe participants only by clinical characteristics.
     Therefore, geographic and ethnic labels are LOW-OBSERVABILITY in [tiab] searches.
     When geographic restriction is required: include country-level MeSH geographic
     terms (e.g., "Country_X"[Mesh]) alongside tiab terms, because MeSH indexers
     assign geographic headings independently of abstract content. Even so, if no
     high-observability terms remain, OMIT the geographic AND block and leave it
     for screening — a missed paper is better than a blocked population.
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
    - Diagnostic context (e.g., differential diagnosis, disease etiology)
      EXCEPTION: if the diagnostic context IS the distinguishing topic of the review
      (e.g., 'biomarkers FOR differential diagnosis of disease etiology'), include it.
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
    Correct:   ("Anti-Bacterial Agents"[Mesh] OR antibiotic*[tiab] OR "penicillin"[tiab] OR "amoxicillin"[tiab])
    Incorrect: ("penicillin"[tiab] OR "amoxicillin"[tiab])  <- broad class removed
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
  PATHOGENIC MECHANISMS (e.g., 'models of inflammation', 'models of endoplasmic reticulum stress',
  'signaling pathway studies'), the CONDITION block MUST include broad mechanism MeSH
  terms (e.g., 'Inflammation'[Mesh], 'Endoplasmic Reticulum Stress'[Mesh]) as OR alternatives
  alongside disease-specific terms.
  Rationale: basic science papers study mechanisms WITHOUT naming the clinical disease.
  A paper titled 'EGCG inhibits NF-kB in macrophages' is relevant to a chronic
  inflammation review but will NOT contain the disease name — it is caught only via
  'Inflammation'[Mesh] or 'inflammatory'[tiab] in the CONDITION block.
  WARNING: Do NOT apply OUTCOME_MEASURE RULE to 'Inflammation'[Mesh] when the review
  explicitly includes in vitro/animal studies; here it is a CONDITION/MECHANISM term.

- ALTERNATIVE_ARM_PRESERVATION_RULE (SECTION_00 NON-NEGOTIABLE):
  When inclusion criteria describe TWO DISTINCT ELIGIBLE ARMS with different
  characteristics (e.g., 'Arm A: conventional drug therapy' OR 'Arm B: behavioral
  intervention'), the query must preserve the OR structure:
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

- METHODOLOGY_TERMINOLOGY_BREADTH_RULE (SECTION_00 NON-NEGOTIABLE):
  When the INTERVENTION/EXPOSURE block encodes a research method, analytical approach,
  or decision-support tool (e.g., 'prediction model', 'prognostic model', 'risk score',
  'clinical decision tool', 'diagnostic algorithm'), terminology varies widely across
  publications. The same concept may appear as:
    prediction model / risk model / predictive algorithm / clinical prediction rule /
    nomogram / risk stratification tool / machine learning model / deep learning model /
    scoring system / index / clinical score.
  Rules:
    a) Anchor the block with the broadest applicable MeSH heading as primary recall
       protection (e.g., "Prognosis"[Mesh], "Risk Assessment"[Mesh], "Models, Statistical"[Mesh],
       "Decision Support Techniques"[Mesh], "Algorithms"[Mesh]).
    b) Add multiple tiab synonyms for the core approach concept, covering both
       traditional (score, rule, index) and computational (algorithm, machine learning,
       deep learning, nomogram) naming conventions.
    c) Do NOT rely on a single specific phrase like "prediction model"[tiab] alone —
       papers using 'algorithm', 'nomogram', or 'risk stratification tool' will be missed.
    d) For broad methodological reviews (e.g., 'prediction models of any type'),
       the MeSH anchor alone may suffice; add tiab only when tiab terms are genuinely
       discriminating (i.e., absent from irrelevant papers).
  Correct:   ("Prognosis"[Mesh] OR "Risk Assessment"[Mesh] OR "prediction model"[tiab]
               OR "risk score"[tiab] OR nomogram[tiab] OR algorithm*[tiab]
               OR "machine learning"[tiab] OR "risk stratification"[tiab])
  Incorrect: ("prediction model"[tiab] OR "risk score"[tiab]) as the complete block
             <- this misses nomogram, algorithm, machine learning, Framingham-type papers.

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

# SECTION_00_REWRITE_END
"""

# ---------------------------------------------------------------------------
# Editable imperative / example blocks (same rewrite mechanism as SECTION_00)
# Markers: # <NAME>_BEGIN / # <NAME>_END
# Use rewrite_section00_block.py --target-variable <VAR> to replace content.
# ---------------------------------------------------------------------------

TIAB_IMPERATIVE_CONDITIONAL_ADD_EDITABLE = r"""
# TIAB_IMPL_COND_ADD_BEGIN
[ONE-SHOT-GUIDANCE: ADD_TIAB] In initial query construction, include tiab synonyms
in {target_block} for variant spellings and abbreviations not covered by MeSH.
Pair tiab terms with MeSH equivalents where possible: ("TERM"[Mesh] OR "TERM"[tiab]).
Do not use tiab as sole coverage for core CONDITION or INTERVENTION slots.
NAMED-INSTANCES RULE: When a slot contains a broad category concept (e.g., Biomarkers,
Antihypertensive Agents, Diagnostic Techniques, Pathogens) AND the paper involves specific
named instances of that category (e.g., specific protein names, specific drug names,
specific gene variants, antibiotic brand/class names), add those specific instance names
as tiab terms.
BROAD FALLBACK FLOOR: Always keep the broad class MeSH and at least one broad tiab
alongside the specific names - never replace broad coverage with only a named list.
Example: ("Biomarkers"[Mesh] OR biomarker*[tiab] OR CRP[tiab] OR ESR[tiab])
is correct; (CRP[tiab] OR ESR[tiab]) alone is incorrect.
INTERVENTION VARIANT COVERAGE: For intervention classes with many historical variants
(antibiotics, biologics, antiseptics), include generation names, brand names, class names,
and broad class terms. Wildcard (antibiotic*, biologic*) covers unknown variants.
# TIAB_IMPL_COND_ADD_END
"""

ONE_SHOT_IMPERATIVE_PRIMARY_EDITABLE = r"""
# ONE_SHOT_PRIMARY_BEGIN
Apply this action ONLY when the term being removed is a LITERAL synonym or
abbreviation/expansion pair - e.g., 'TB' when 'tuberculosis' is already present,
or vice versa.
CRITICAL: Do NOT treat a narrower (more specific) term as redundant merely because
a broader category term is present. Training-data evidence: removing
'GLP-1 Receptor Agonists'[Majr] on the grounds that 'Hypoglycemic Agents'[Majr]
already covered it caused a measurable recall loss - papers describing GLP-1 receptor
agonists did not always use the broader category label. The same applies to any
hyponym/hypernym pair (e.g., a specific biomarker vs 'biomarker', a specific drug vs
its drug class, a specific symptom vs 'symptom'). When in doubt, KEEP the specific term.
# ONE_SHOT_PRIMARY_END
"""

PLACEHOLDER_INITIAL_PRIMARY_EDITABLE = r"""
# PLACEHOLDER_INIT_BEGIN
Example: Build PRIMARY as (CONDITION_X OR CONDITION_Y) AND (INTERVENTION_Z OR TERM_A).
AND BLOCK BUDGET: Use 2-3 AND blocks maximum. Only CONDITION and INTERVENTION/EXPOSURE
are mandatory AND blocks. Delivery mode, modality, context, and provider blocks are optional.
STUDY_FILTER: Add only when inclusion criteria restrict to a SINGLE mandatory design type
(e.g., 'RCTs only' with observational excluded).
A conjunctive listing ('RCT and observational') counts as 2+ types -> OMIT STUDY_FILTER.
STUDY_FILTER TEMPLATE when needed:
("Randomized Controlled Trial"[pt] OR "Controlled Clinical Trial"[pt]
OR randomized[tiab] OR randomised[tiab] OR randomly[tiab] OR trial[ti]).
SPECIFIC-INSTANCES RULE: When a broad category concept contains named specific instances
(e.g., specific biomarker names like CRP, ESR, TNF-alpha; specific drug names; specific
antibiotic names; specific gene names), enumerate those specific instances individually as
tiab terms ALONGSIDE the broad MeSH. Never remove the broad class term.
BROAD FALLBACK FLOOR: Every block must retain at least one broad class term
(broad MeSH OR broad tiab like biomarker*, antibiotic*, substance*) even when specific
instances are listed.
# PLACEHOLDER_INIT_END
"""


def _extract_editable_text(block: str, begin_marker: str, end_marker: str) -> str:
    """Extract text between BEGIN/END markers, collapsing newlines into spaces
    for single-line law table cell output."""
    start = block.find(begin_marker)
    end = block.find(end_marker)
    if start == -1 or end == -1:
        raise ValueError(f"Markers '{begin_marker}' or '{end_marker}' not found in editable block")
    text = block[start + len(begin_marker):end]
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_str(value):
    return "" if value is None else str(value)


def normalize_concept(concept_category):
    cc = to_str(concept_category).upper()
    if any(k in cc for k in ["FILTER", "STUDY_DESIGN", "RCT", "DESIGN"]):
        role = "FILTER"
    elif any(k in cc for k in ["CONTEXT", "SETTING", "PROVIDER", "DELIVERY"]):
        role = "CONTEXT"
    else:
        role = "PRIMARY"

    if "CONDITION" in cc:
        category = "CONDITION"
    elif "POPULATION" in cc:
        category = "POPULATION"
    elif "INTERVENTION" in cc:
        category = "INTERVENTION"
    elif "OUTCOME" in cc:
        category = "OUTCOME"
    elif "DELIVERY" in cc:
        category = "DELIVERY"
    elif any(k in cc for k in ["STUDY_DESIGN", "RCT", "DESIGN"]):
        category = "STUDY_DESIGN"
    else:
        category = "OTHER"

    return f"{role}.{category}"


def infer_target_from_context(action_text, meta_concept):
    at = action_text.upper()
    role, category = meta_concept.split(".", 1)
    if "FILTER" in at:
        return "FILTER"
    if "FIELD" in at:
        return "FIELD"
    if "DESIGN" in at:
        return "DESIGN"
    if "PRIMARY" in at:
        return "PRIMARY"
    if role == "FILTER":
        return "FILTER"
    if category == "STUDY_DESIGN":
        return "FILTER"
    return "PRIMARY"


def normalize_action(action_type, concept_category):
    at = to_str(action_type).upper()
    meta_concept = normalize_concept(concept_category)
    if any(k in at for k in ["RESTORE", "ROLLBACK"]):
        return "RESTORE_PRIMARY"
    if any(k in at for k in ["INIT", "BASELINE"]):
        return "INITIAL_PRIMARY"
    if any(k in at for k in ["EXPAND", "BROADEN", "ADD", "RELAX"]):
        direction = "EXPAND"
    elif any(k in at for k in ["RESTRICT", "PRUNE", "NARROW", "REFINE", "REMOVE"]):
        direction = "RESTRICT"
    else:
        return "UNMAPPED"
    target = infer_target_from_context(at, meta_concept)
    meta_action = f"{direction}_{target}"
    if meta_action.startswith("UNMAPPED_"):
        return "UNMAPPED"
    return meta_action


def bridge_for(meta_action, meta_concept):
    role, _ = meta_concept.split(".", 1)
    if meta_action == "UNMAPPED":
        return "BLOCKED", "NA", "NA", "NA"
    if meta_action == "INITIAL_PRIMARY":
        return "BUILD_BASE", "PRIMARY", "CONDITION+POPULATION(+INTERVENTION if required)", "AllFieldsOrMesh"
    if meta_action == "EXPAND_PRIMARY":
        policy = "AllFieldsOrMesh" if meta_concept in CORE_SLOTS else "AllFieldsOrMeshOrTiab"
        return "ADD_OR", "PRIMARY", meta_concept, policy
    if meta_action == "RESTRICT_PRIMARY":
        return "REMOVE_OR", "PRIMARY", meta_concept, "KeepBroadCore"
    if meta_action == "EXPAND_FILTER":
        return "ADD_OR", "FILTER", "STUDY_DESIGN", "PublicationTypePlusBackup"
    if meta_action == "RESTRICT_FILTER":
        return "REMOVE_OR", "FILTER", "STUDY_DESIGN", "KeepDesignBackup"
    if meta_action == "RESTRICT_FIELD":
        block = "FILTER" if role == "FILTER" else ("CONTEXT" if role == "CONTEXT" else "PRIMARY")
        return "RESTRICT_FIELD", block, meta_concept, "tiab_only_for_auxiliary"
    if meta_action == "RESTORE_PRIMARY":
        slot = meta_concept if meta_concept in CORE_SLOTS else "PRIMARY.CONDITION_OR_POPULATION"
        return "RESTORE_BROAD", "PRIMARY", slot, "RevertAllFieldsOrMesh"
    if meta_action in {"ADD_FIELD_TAG", "REMOVE_FIELD_TAG"}:
        block, tag_bucket = meta_concept.split(".", 1)
        block = block if block in FIELD_BLOCKS else "PRIMARY"
        if meta_action == "ADD_FIELD_TAG":
            if tag_bucket == "MAJR":
                return "RESTRICT_FIELD", block, meta_concept, "major_topic_only_high_risk"
            if tag_bucket == "MESH":
                return "ADD_OR", block, meta_concept, "MeshPlusTextBackup"
            if tag_bucket == "TIAB":
                return "ADD_OR", block, meta_concept, "tiab_synonym_expansion"
            return "ADD_OR", block, meta_concept, "FieldTagExpansion"
        # REMOVE_FIELD_TAG
        if tag_bucket == "MAJR":
            return "RESTORE_BROAD", block, meta_concept, "RemoveMajorTopicRestriction"
        if tag_bucket == "MESH":
            return "REMOVE_OR", block, meta_concept, "KeepTextBackup"
        if tag_bucket == "TIAB":
            return "REMOVE_OR", block, meta_concept, "AvoidRemovingCoreTiab"
        return "REMOVE_OR", block, meta_concept, "FieldTagReduction"
    return "BLOCKED", "NA", "NA", "NA"


def effect_label(delta_recall, delta_hits):
    if delta_recall > 0:
        return "RecallUp"
    if delta_recall < 0:
        return "RecallDown"
    if delta_hits < 0:
        return "HitsDown"
    if delta_hits > 0:
        return "HitsUp"
    return "Neutral"


def effect_direction(value):
    if value > 0:
        return "Increase"
    if value < 0:
        return "Decrease"
    return "Neutral"


def evidence_grade(n):
    if n >= 3:
        return "STRONG"
    if n == 2:
        return "MODERATE"
    return "WEAK"


def calc_primary_restriction_penalty(meta_action, target_block, target_slot, law_type):
    """Penalty for restrictive operations applied to PRIMARY concepts.

    Definition:
    - Measures how aggressively a law narrows PRIMARY coverage.
    - Higher when action removes/restricts PRIMARY.TIAB or PRIMARY.MESH.
    - Additional penalty for restrictive law types.
    - Output is capped to [0, 1].
    """
    if target_block != "PRIMARY":
        return 0.0

    penalty = 0.0

    if meta_action in {"RESTRICT_PRIMARY", "REMOVE_FIELD_TAG"}:
        penalty += 0.6
    elif meta_action == "RESTRICT_FIELD":
        penalty += 0.4

    if target_slot in {"PRIMARY.TIAB", "PRIMARY.MESH"} and meta_action == "REMOVE_FIELD_TAG":
        penalty += 0.3
    if target_slot in CORE_SLOTS and meta_action in {"RESTRICT_PRIMARY", "RESTRICT_FIELD"}:
        penalty += 0.2

    if law_type == "NOISE_REDUCTION":
        penalty += 0.1
    elif law_type == "AVOID":
        penalty += 0.2

    return min(1.0, penalty)


# ---------------------------------------------------------------------------
# Improvement #2: Bidirectional tiab-specific imperatives
# ---------------------------------------------------------------------------

def tiab_imperative(meta_action, law_type, target_block, apply_when, do_not_apply_when):
    """Context-aware imperative for TIAB field tag operations.

    ADD_TIAB risk profile: inflating hits without MeSH backup.
    REMOVE_TIAB risk profile: recall loss when no MeSH backup exists for the concept.
    These are asymmetric risks and must not collapse into a single AVOID direction.
    """
    if meta_action == "ADD_FIELD_TAG":
        if law_type == "RECALL_PROTECTIVE":
            return (
                f"To protect recall coverage, add tiab terms to {target_block} "
                "when MeSH does not capture variant spellings, abbreviations, or emerging terminology; "
                "use wildcard [tiab] for terminological breadth."
            )
        if law_type == "NOISE_REDUCTION":
            return (
                f"To reduce noise, add tiab terms to {target_block} only as targeted synonyms "
                "for concepts already covered by MeSH; "
                "do not rely on tiab as primary coverage for core concept slots."
            )
        if law_type == "AVOID":
            return (
                f"[AVOID] Do not add bare tiab-only terms as primary coverage in {target_block} "
                "without a MeSH-backed equivalent; "
                "tiab-only expansion inflates hits without reliably protecting recall. "
                "Always pair tiab additions with (\"TERM\"[Mesh] OR \"TERM\"[tiab]) structure."
            )
        # CONDITIONAL -> ONE-SHOT-GUIDANCE (text from TIAB_IMPERATIVE_CONDITIONAL_ADD_EDITABLE)
        return _extract_editable_text(
            TIAB_IMPERATIVE_CONDITIONAL_ADD_EDITABLE,
            "# TIAB_IMPL_COND_ADD_BEGIN",
            "# TIAB_IMPL_COND_ADD_END",
        ).format(target_block=target_block)

    else:  # REMOVE_FIELD_TAG + TIAB
        if law_type == "AVOID":
            return (
                f"[AVOID] Do not remove tiab terms from {target_block} unless a MeSH equivalent "
                "fully covers all variant spellings of the concept. "
                "Removing tiab without MeSH backup is the primary cause of recall loss in this dataset. "
                "When in doubt, retain tiab coverage."
            )
        if law_type == "NOISE_REDUCTION":
            return (
                f"To reduce noise, remove peripheral tiab variants from {target_block} "
                "only when MeSH fully covers the concept and total hits are excessive; "
                "never remove tiab from core CONDITION, POPULATION, or INTERVENTION slots."
            )
        if law_type == "RECALL_PROTECTIVE":
            return (
                f"To protect recall, retain all tiab terms in {target_block}; "
                "do not remove tiab coverage from any concept slot that lacks a full MeSH backup."
            )
        # CONDITIONAL -> ONE-SHOT-GUIDANCE
        return (
            f"[ONE-SHOT-GUIDANCE: REMOVE_TIAB] When building the initial query, "
            f"retain tiab coverage in {target_block} unless MeSH demonstrably covers all variants. "
            "In one-shot context, prefer inclusion over exclusion for tiab terms; "
            "tiab removal is a refinement step that requires recall feedback to execute safely."
        )


# ---------------------------------------------------------------------------
# Improvement #3: CONDITIONAL -> one-shot preventive guidance
# ---------------------------------------------------------------------------

def one_shot_imperative(meta_action, target_block, target_slot, mean_dr, mean_dh):
    """Rewrite CONDITIONAL iterative guidance as preventive one-shot construction rule."""
    if mean_dh < 0 and mean_dr >= 0:
        return (
            f"[ONE-SHOT-GUIDANCE] When building the initial query, applying {meta_action} "
            f"to {target_block}/{target_slot} tends to reduce hits without harming recall. "
            "Prefer including this refinement in the initial build to avoid excessive result sets."
        )
    if mean_dr > 0:
        base = (
            f"[ONE-SHOT-GUIDANCE] When building the initial query, applying {meta_action} "
            f"to {target_block}/{target_slot} tends to increase recall coverage. "
            "Include this in the initial build when broad coverage is a priority."
        )
        if "POPULATION" in target_slot or "CONTEXT" in target_slot:
            base += (
                " IMPORTANT: For ethnicity/geography/cultural-minority terms, add terms by OR "
                "within the existing population/context structure. Avoid an independent AND "
                "block for those terms because it often over-restricts recall. "
                "Exception: age/developmental-stage criteria (e.g., child, adolescent, adult) "
                "may be an independent AND population block when explicitly definitional in "
                "the inclusion criteria."
            )
        return base
    # Mixed effects: differentiate by target block
    if target_block == "FILTER":
        return (
            f"[ONE-SHOT-GUIDANCE] {meta_action} on {target_block}/{target_slot} shows mixed effects "
            "across training cases. In initial query construction, favor recall over precision. "
            "Apply this action ONLY when inclusion criteria clearly support it, defined as: "
            "the review restricts to EXACTLY ONE specific study design type AND that restriction "
            "is explicitly stated as mandatory (not merely preferred or listed as an example). "
            "If inclusion criteria mention two or more design types, or if the restriction is ambiguous, "
            "do NOT apply this action."
        )
    # PRIMARY block restriction: term redundancy rule (advice from ONE_SHOT_IMPERATIVE_PRIMARY_EDITABLE)
    _opening = (
        f"[ONE-SHOT-GUIDANCE] {meta_action} on {target_block}/{target_slot} shows mixed effects "
        "across training cases. In initial query construction, favor recall over precision. "
    )
    _advice = _extract_editable_text(
        ONE_SHOT_IMPERATIVE_PRIMARY_EDITABLE,
        "# ONE_SHOT_PRIMARY_BEGIN",
        "# ONE_SHOT_PRIMARY_END",
    )
    return _opening + _advice


def infer_conditions(law_type, mean_dr, mean_dh):
    if law_type == "RECALL_PROTECTIVE":
        return "coverage is incomplete", "law is unmapped or unsafe"
    if law_type == "NOISE_REDUCTION":
        return "core concepts are stabilized and hits are excessive", "recall is dropping or core terms would be narrowed"
    if law_type == "CONDITIONAL":
        if mean_dh < 0 and mean_dr >= 0:
            return "hits are excessive and recall is stable", "recall starts to drop"
        return "recall is below target and expansion is needed", "noise increases excessively or recall starts to drop"
    return "never", "always"


def imperative_for(law_type, meta_action, target_block, target_slot,
                   apply_when, do_not_apply_when, mean_dr=0.0, mean_dh=0.0):
    """
    Improvement #2 + #3:
    - TIAB actions get bidirectional context-aware guidance.
    - CONDITIONAL laws get [ONE-SHOT-GUIDANCE: ...] prefix instead of iterative conditions.
    """
    # Improvement #2: tiab-specific bidirectional imperatives
    tag_suffix = target_slot.split(".")[-1] if "." in target_slot else ""
    if meta_action in ("ADD_FIELD_TAG", "REMOVE_FIELD_TAG") and tag_suffix == "TIAB":
        return tiab_imperative(meta_action, law_type, target_block, apply_when, do_not_apply_when)

    # Improvement #3: CONDITIONAL -> one-shot preventive guidance
    if law_type == "CONDITIONAL":
        return one_shot_imperative(meta_action, target_block, target_slot, mean_dr, mean_dh)

    if law_type == "RECALL_PROTECTIVE":
        return f"To protect recall, apply {meta_action} to {target_block}/{target_slot} when {apply_when}."
    if law_type == "NOISE_REDUCTION":
        return f"To reduce noise, apply {meta_action} to {target_block}/{target_slot} when {apply_when}."
    return f"Avoid applying {meta_action}; this action is unsafe under {do_not_apply_when}."


# ---------------------------------------------------------------------------
# Placeholder examples
# ---------------------------------------------------------------------------

def placeholder_example_for(law_type, meta_action, action_operator, target_block, target_slot):
    base_primary = "(CONDITION_X OR CONDITION_Y) AND (POPULATION_Y OR POPULATION_Z) AND (INTERVENTION_Z OR TERM_A)"
    base_filter = "(DESIGN_MESH OR DESIGN_TEXT)"

    if law_type == "AVOID":
        return (
            f"Example (do not execute): {meta_action} on {target_block}/{target_slot}; "
            "keep baseline blocks unchanged."
        )
    if meta_action == "ADD_FIELD_TAG" and target_slot.endswith(".MESH"):
        return "Example: Pair core term with field tag: (\"TERM_A\"[Mesh] OR \"TERM_A\"[tiab])."
    if meta_action == "REMOVE_FIELD_TAG" and target_slot.endswith(".MESH"):
        return "Example: Remove Mesh-only TERM_B but retain text backup (\"TERM_B\"[tiab]) to protect recall."
    if meta_action == "ADD_FIELD_TAG" and target_slot.endswith(".TIAB"):
        return "Example: Add tiab synonym alongside MeSH: (\"TERM_C\"[Mesh] OR TERM_C*[tiab] OR TERM_D*[tiab])."
    if meta_action == "REMOVE_FIELD_TAG" and target_slot.endswith(".TIAB"):
        return "Example: Remove peripheral tiab variant TERM_E[tiab] only when MeSH fully covers concept; retain core tiab."
    if meta_action == "ADD_FIELD_TAG" and target_slot.endswith(".MAJR"):
        return "Example: Restrict to major topic (\"TERM_F\"[Majr]); apply only when recall is demonstrably stable."
    if meta_action == "REMOVE_FIELD_TAG" and target_slot.endswith(".MAJR"):
        return "Example: Roll back [Majr] restriction to [Mesh]/[tiab] when recall drops."
    if meta_action == "INITIAL_PRIMARY":
        return _extract_editable_text(
            PLACEHOLDER_INITIAL_PRIMARY_EDITABLE,
            "# PLACEHOLDER_INIT_BEGIN",
            "# PLACEHOLDER_INIT_END",
        )
    if action_operator == "ADD_OR" and target_block == "PRIMARY":
        return (
            f"Example: Before PRIMARY={base_primary}; "
            f"add synonym TERM_B to slot {target_slot}; After PRIMARY includes TERM_B by OR."
        )
    if action_operator == "REMOVE_OR" and target_block == "PRIMARY":
        return (
            f"Example: Before PRIMARY={base_primary}; "
            f"remove low-value TERM_C from slot {target_slot}; keep CONDITION_X and POPULATION_Y."
        )
    if action_operator == "ADD_OR" and target_block == "FILTER":
        return f"Example: Before FILTER={base_filter}; add DESIGN_ALT by OR; keep publication-type backup."
    if action_operator == "REMOVE_OR" and target_block == "FILTER":
        return f"Example: Before FILTER={base_filter}; remove broad TERM_D; keep at least one design backup."
    if action_operator == "RESTRICT_FIELD":
        return (
            f"Example: Keep slot {target_slot} but restrict auxiliary TERM_E to [tiab]; "
            "do not touch core CONDITION_X/INTERVENTION_Z."
        )
    if action_operator == "RESTORE_BROAD":
        return (
            f"Example: If prior step over-restricted {target_slot}, "
            "restore TERM_A from [tiab] to All Fields or Mesh."
        )
    return (
        f"Example: Apply {meta_action} as {action_operator} on {target_block}/{target_slot}; "
        "use TERM_A/TERM_B placeholders."
    )


# ---------------------------------------------------------------------------
# Domain parsing (Improvement #4)
# ---------------------------------------------------------------------------

def get_domain_from_log(log_name):
    """Extract the domain from a public-release log key.

    Expected format:
        02_Cardiovascular_Disease/41522206_2026/search_history.jsonl
    """
    parts = Path(log_name).parts
    if len(parts) >= 3 and parts[-1] == "search_history.jsonl":
        return parts[-3]
    m = re.match(r'search_history_(\d{2}_[A-Za-z][A-Za-z_]+?)_\d{5,}', log_name)
    if m:
        return m.group(1).rstrip('_')
    base = log_name.replace('search_history_', '').replace('.jsonl', '')
    return f'Legacy_{base}' if base else 'Unknown'


def get_log_key(log_file):
    try:
        return log_file.relative_to(DATA_DIR).as_posix()
    except ValueError:
        return log_file.name


# ---------------------------------------------------------------------------
# I/O: load records with iteration-based weights (Improvement #1)
# ---------------------------------------------------------------------------

def load_records():
    log_files = sorted(DATA_DIR.glob("*/*/search_history.jsonl"))
    records = []
    log_iter_sets = defaultdict(set)

    for log_file in log_files:
        log_name = get_log_key(log_file)
        with log_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                try:
                    iter_num = int(rec.get("iteration", 0))
                except (TypeError, ValueError):
                    iter_num = 0
                log_iter_sets[log_name].add(iter_num)
                records.append((log_name, rec))

    # Improvement #1: weight = clamp(n_iterations / WEIGHT_NORM, MIN_WEIGHT, 1.0)
    log_weights = {}
    for log_file in log_files:
        log_name = get_log_key(log_file)
        n_iter = max(len(log_iter_sets.get(log_name, {0})), 1)
        w = max(MIN_WEIGHT, min(n_iter / WEIGHT_NORM, 1.0))
        log_weights[log_name] = w

    return log_files, records, log_weights


# ---------------------------------------------------------------------------
# Field-tag transition extraction (unchanged from v1)
# ---------------------------------------------------------------------------

def has_ellipsis_placeholder(text):
    t = to_str(text)
    return "..." in t or "\u2026" in t


def normalize_field_tag(tag):
    t = to_str(tag).strip().lower()
    if "majr" in t or "major topic" in t:
        return "MAJR"
    if "mesh" in t:
        return "MESH"
    if "tiab" in t:
        return "TIAB"
    if "publication type" in t or t == "pt":
        return "PT"
    if "language" in t:
        return "LANGUAGE"
    return "OTHER"


def field_profile_for_text(text):
    t = to_str(text)
    if not t or has_ellipsis_placeholder(t):
        return None
    counts = defaultdict(int)
    for tag in re.findall(r"\[([^\]]+)\]", t):
        bucket = normalize_field_tag(tag)
        counts[bucket] += 1
    for b in FIELD_BUCKETS:
        counts[b] += 0
    return counts


def records_by_log(records):
    by_log = defaultdict(list)
    for log_name, rec in records:
        iteration = rec.get("iteration", len(by_log[log_name]) + 1)
        try:
            iteration = int(iteration)
        except (TypeError, ValueError):
            iteration = len(by_log[log_name]) + 1
        by_log[log_name].append((iteration, rec))
    for log_name in by_log:
        by_log[log_name].sort(key=lambda x: x[0])
    return by_log


def extract_field_transition_occurrences(records):
    occurrences = []
    grouped_logs = records_by_log(records)

    for log_name, timeline in grouped_logs.items():
        prev_profiles = None
        for _, rec in timeline:
            qp = rec.get("query_parts")
            if not isinstance(qp, dict):
                qp = {}
            curr_profiles = {
                "PRIMARY": field_profile_for_text(qp.get("primary", "")),
                "FILTER": field_profile_for_text(qp.get("filter", "")),
            }
            if prev_profiles is not None:
                dr = to_float(rec.get("delta_recall", 0.0), 0.0)
                dh = to_float(rec.get("delta_hits", 0.0), 0.0)
                label = effect_label(dr, dh)
                for block in FIELD_BLOCKS:
                    prev_block = prev_profiles.get(block)
                    curr_block = curr_profiles.get(block)
                    if prev_block is None or curr_block is None:
                        continue
                    for bucket in FIELD_BUCKETS:
                        diff = curr_block[bucket] - prev_block[bucket]
                        if diff == 0:
                            continue
                        meta_action = "ADD_FIELD_TAG" if diff > 0 else "REMOVE_FIELD_TAG"
                        meta_concept = f"{block}.{bucket}"
                        occurrences.append({
                            "action": meta_action,
                            "concept": meta_concept,
                            "dr": dr,
                            "dh": dh,
                            "label": label,
                            "log": log_name,
                        })
            prev_profiles = curr_profiles

    return occurrences


# ---------------------------------------------------------------------------
# Rule building with weighted Rep (Improvement #1)
# ---------------------------------------------------------------------------

def build_rules_from(records, log_weights):
    """Build law rows from a set of (log_name, rec) pairs using given log_weights.

    Improvement #1: Rep = sum(weight(log) for logs containing key) / sum(all_weights)
    instead of plain count / total_logs.
    """
    grouped = defaultdict(list)
    logs_per_key = defaultdict(set)

    for log_name, rec in records:
        action = normalize_action(rec.get("action_type", ""), rec.get("concept_category", ""))
        concept = normalize_concept(rec.get("concept_category", ""))
        dr = to_float(rec.get("delta_recall", 0.0), 0.0)
        dh = to_float(rec.get("delta_hits", 0.0), 0.0)
        label = effect_label(dr, dh)
        key = (action, concept)
        grouped[key].append({"dr": dr, "dh": dh, "label": label, "log": log_name})
        logs_per_key[key].add(log_name)

    for ev in extract_field_transition_occurrences(records):
        key = (ev["action"], ev["concept"])
        grouped[key].append({"dr": ev["dr"], "dh": ev["dh"], "label": ev["label"], "log": ev["log"]})
        logs_per_key[key].add(ev["log"])

    total_weight = sum(log_weights.values()) if log_weights else 1.0
    rows = []

    for (meta_action, meta_concept), occ in grouped.items():
        n = len(occ)
        mean_dr = sum(x["dr"] for x in occ) / n
        mean_dh = sum(x["dh"] for x in occ) / n

        counts = {"RecallUp": 0, "RecallDown": 0, "HitsDown": 0, "HitsUp": 0, "Neutral": 0}
        for x in occ:
            counts[x["label"]] += 1

        recall_drop_rate = counts["RecallDown"] / n
        recall_gain_rate = counts["RecallUp"] / n
        has_conflict = counts["RecallUp"] > 0 and counts["RecallDown"] > 0

        successful = counts["RecallUp"] + counts["HitsDown"]
        # Improvement #1: weighted Rep
        w_rep = sum(log_weights.get(lg, MIN_WEIGHT) for lg in logs_per_key[(meta_action, meta_concept)])
        rep = w_rep / total_weight
        suc = successful / n
        con = max(counts.values()) / n
        sup = 1 - math.exp(-n / 3)
        conf_total = rep * suc * con * sup

        # Law type classification
        if meta_action == "UNMAPPED" or recall_drop_rate >= 0.50:
            law_type = "AVOID"
        elif recall_gain_rate >= 0.50 and recall_drop_rate == 0:
            law_type = "RECALL_PROTECTIVE"
        elif mean_dr >= 0 and mean_dh < 0 and recall_drop_rate <= 0.20:
            law_type = "NOISE_REDUCTION"
        else:
            law_type = "CONDITIONAL"

        if has_conflict:
            law_type = "CONDITIONAL"

        action_operator, target_block, target_slot, field_policy = bridge_for(meta_action, meta_concept)

        # Safety gates
        if meta_action == "RESTRICT_FIELD" and meta_concept in {"PRIMARY.CONDITION", "PRIMARY.INTERVENTION"}:
            law_type = "AVOID"
        if "NA" in (action_operator, target_block, target_slot, field_policy):
            law_type = "AVOID"
        if law_type == "NOISE_REDUCTION" and mean_dh >= 0:
            law_type = "CONDITIONAL"
        if meta_concept.endswith(".MAJR") and meta_action == "ADD_FIELD_TAG" and recall_drop_rate > 0:
            law_type = "AVOID"
        # Improvement #2 note: REMOVE_TIAB + recall_drop -> AVOID is retained (directionally correct).
        # ADD_TIAB is NOT gated here - it gets its own bidirectional guidance in imperative_for().
        if meta_concept.endswith(".TIAB") and meta_action == "REMOVE_FIELD_TAG" and recall_drop_rate > 0:
            law_type = "AVOID"

        apply_when, do_not_apply_when = infer_conditions(law_type, mean_dr, mean_dh)
        imperative = imperative_for(
            law_type, meta_action, target_block, target_slot,
            apply_when, do_not_apply_when, mean_dr, mean_dh
        )

        risk_penalty = recall_drop_rate * (1 + abs(min(mean_dr, 0.0)))
        primary_restriction_penalty = calc_primary_restriction_penalty(
            meta_action, target_block, target_slot, law_type
        )
        deploy_score = (
            conf_total
            - ALPHA_RISK * risk_penalty
            - BETA_PRIMARY * primary_restriction_penalty
        )

        row = {
            "Law_ID": "",
            "Law_Type": law_type,
            "META_ACTION": meta_action,
            "META_CONCEPT": meta_concept,
            "Action_Operator": action_operator,
            "Target_Block": target_block,
            "Target_Slot": target_slot,
            "Field_Policy": field_policy,
            "Imperative_EN": imperative,
            "Example_Placeholder": placeholder_example_for(
                law_type, meta_action, action_operator, target_block, target_slot
            ),
            "Apply_When": apply_when,
            "Do_Not_Apply_When": do_not_apply_when,
            "Expected_Effect_Recall": effect_direction(mean_dr),
            "Expected_Effect_Hits": effect_direction(mean_dh),
            "Risk": "Recall Loss" if recall_drop_rate > 0 else ("Noise Gain" if mean_dh > 0 else "None"),
            "Evidence_n": n,
            "Evidence_logs": ", ".join(sorted(logs_per_key[(meta_action, meta_concept)])),
            "Evidence_Grade": evidence_grade(n),
            "Rep": rep,
            "Suc": suc,
            "Con": con,
            "Sup": sup,
            "Confidence_Total_Optional": conf_total,
            "Risk_Penalty": risk_penalty,
            "Primary_Restriction_Penalty": primary_restriction_penalty,
            "Deploy_Score": deploy_score,
            "mean_dr": mean_dr,
            "mean_dh": mean_dh,
            "has_conflict": has_conflict,
        }
        rows.append(row)

    type_priority = {"RECALL_PROTECTIVE": 4, "NOISE_REDUCTION": 3, "CONDITIONAL": 2, "AVOID": 1}
    rows.sort(
        key=lambda x: (
            type_priority.get(x["Law_Type"], 0),
            x["Deploy_Score"],
            x["Rep"],
            x["Suc"],
            x["Con"],
            x["Sup"],
            abs(x["mean_dr"]),
        ),
        reverse=True,
    )
    for idx, row in enumerate(rows, 1):
        row["Law_ID"] = f"LAW_{idx:03d}"

    return rows


def build_rules(log_files, records, log_weights):
    return build_rules_from(records, log_weights)


# ---------------------------------------------------------------------------
# Deployment selection
# ---------------------------------------------------------------------------

def select_deployment(rows, n=12):
    deployable = []
    for row in rows:
        if row["Law_Type"] == "AVOID":
            continue
        if row["META_ACTION"] == "UNMAPPED":
            continue
        if "NA" in (row["Action_Operator"], row["Target_Block"], row["Target_Slot"], row["Field_Policy"]):
            continue
        if row.get("Deploy_Score", 0.0) <= 0:
            continue
        deployable.append(row)
    deployable.sort(key=lambda x: (x.get("Deploy_Score", 0.0), x["Rep"], x["Suc"]), reverse=True)
    return deployable[:n]


def select_negative_laws(rows, n=12):
    negatives = []
    for row in rows:
        if row["Law_Type"] == "AVOID":
            negatives.append(row)
            continue
        if row["Risk"] == "Recall Loss":
            negatives.append(row)
            continue
        if row["Expected_Effect_Recall"] == "Decrease":
            negatives.append(row)
    negatives.sort(
        key=lambda x: (1 if x["Law_Type"] == "AVOID" else 0, x["Rep"], x["Sup"], x["Evidence_n"]),
        reverse=True,
    )
    return negatives[:n]


# ---------------------------------------------------------------------------
# Improvement #4: Domain-specific law building
# ---------------------------------------------------------------------------

def build_domain_laws(records, log_weights):
    """Build per-domain rule sets. Returns {domain_name: rows}."""
    domain_records = defaultdict(list)
    for log_name, rec in records:
        domain = get_domain_from_log(log_name)
        if not domain.startswith("Legacy_"):
            domain_records[domain].append((log_name, rec))

    domain_rows = {}
    for domain, d_records in domain_records.items():
        d_log_names = {ln for ln, _ in d_records}
        d_weights = {ln: log_weights.get(ln, MIN_WEIGHT) for ln in d_log_names}
        rows = build_rules_from(d_records, d_weights)
        domain_rows[domain] = rows

    return domain_rows


def find_divergent_laws(global_rows, domain_rows):
    """Return domain laws that diverge significantly from global laws.

    Divergence criteria:
    - Domain-only: action/concept key has no global counterpart.
    - Type mismatch: global and domain have different Law_Type for same key.
    - Rep gap: domain_rep >= 0.8 but global_rep < 0.4.
    """
    global_map = {(r["META_ACTION"], r["META_CONCEPT"]): r for r in global_rows}
    divergent = []

    for row in domain_rows:
        key = (row["META_ACTION"], row["META_CONCEPT"])
        g = global_map.get(key)
        reason = ""

        if g is None:
            reason = "domain-only"
        elif g["Law_Type"] != row["Law_Type"]:
            reason = f"type_mismatch:global={g['Law_Type']},domain={row['Law_Type']}"
        elif row["Rep"] >= 0.8 and g["Rep"] < 0.4:
            reason = f"rep_gap:domain={row['Rep']:.2f},global={g['Rep']:.2f}"

        if reason:
            row_copy = dict(row)
            row_copy["Divergence_Reason"] = reason
            divergent.append(row_copy)

    return divergent


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

COLS = [
    "Law_ID", "Law_Type", "META_ACTION", "META_CONCEPT",
    "Action_Operator", "Target_Block", "Target_Slot", "Field_Policy",
    "Imperative_EN", "Example_Placeholder",
    "Apply_When", "Do_Not_Apply_When",
    "Expected_Effect_Recall", "Expected_Effect_Hits", "Risk",
    "Evidence_n", "Evidence_Grade",
    "Rep", "Suc", "Con", "Sup", "Confidence_Total_Optional",
    "Risk_Penalty", "Primary_Restriction_Penalty", "Deploy_Score",
]


def format_row(row, cols=COLS):
    values = []
    for c in cols:
        value = row.get(c, "")
        if c in {"Rep", "Suc", "Con", "Sup"}:
            values.append(f"{float(value):.2f}")
        elif c in {"Confidence_Total_Optional", "Risk_Penalty", "Primary_Restriction_Penalty", "Deploy_Score"}:
            values.append(f"{float(value):.3f}")
        else:
            values.append(str(value))
    return "| " + " | ".join(values) + " |"


def render_law_table(rows, cols=COLS):
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in rows:
        lines.append(format_row(row, cols))
    return "\n".join(lines)


def build_section00_lines():
    lines = []
    for raw_line in SECTION_00_EDITABLE_BLOCK.strip().splitlines():
        if raw_line.strip() in {SECTION_00_REWRITE_BEGIN, SECTION_00_REWRITE_END}:
            continue
        lines.append(raw_line)
    return lines


def render_compact_section(deployment, negatives, prefix="GLOBAL"):
    out = [f"## {prefix}_DO_LAWS"]
    for idx, row in enumerate(deployment, 1):
        out.append(
            f"[{idx:02d}] {row['Law_ID']} | {row['Law_Type']} | "
            f"{row['Action_Operator']}/{row['Target_Block']}/{row['Target_Slot']} | "
            f"{row['Imperative_EN']} | "
            f"Example={row['Example_Placeholder']} | "
            f"Rep/Suc/Con/Sup={row['Rep']:.2f}/{row['Suc']:.2f}/{row['Con']:.2f}/{row['Sup']:.2f} | "
            f"DeployScore={row.get('Deploy_Score', 0.0):.3f}"
        )
    out.append("")
    out.append(f"## {prefix}_AVOID_LAWS")
    for idx, row in enumerate(negatives, 1):
        out.append(
            f"[{idx:02d}] {row['Law_ID']} | {row['Law_Type']} | "
            f"{row['Action_Operator']}/{row['Target_Block']}/{row['Target_Slot']} | "
            f"{row['Imperative_EN']} | "
            f"Example={row['Example_Placeholder']} | Risk={row['Risk']} | "
            f"Rep/Suc/Con/Sup={row['Rep']:.2f}/{row['Suc']:.2f}/{row['Con']:.2f}/{row['Sup']:.2f}"
        )
    return "\n".join(out)


def render_output(global_rows, global_deployment, global_negatives, domain_law_dict):
    out = []
    out.extend(build_section00_lines())
    out.append("")

    out.append("# SECTION_0_METRIC_DEFINITIONS")
    out.append(f"- Rep: Weighted cross-log reproducibility = sum(weight(log)) / sum(all_weights).")
    out.append(f"  weight = clamp(n_iterations / {WEIGHT_NORM:.0f}, min={MIN_WEIGHT}, max=1.0).")
    out.append("- Suc: Success rate = (RecallUp + HitsDown) / total occurrences.")
    out.append("- Con: Effect consistency = max(effect-direction count) / total occurrences.")
    out.append("- Sup: Support weight = 1 - exp(-n/3), n = total occurrences.")
    out.append("- Confidence_Total_Optional: Rep * Suc * Con * Sup.")
    out.append("- Risk_Penalty: recall_drop_rate * (1 + abs(min(mean_dr, 0))).")
    out.append("- Primary_Restriction_Penalty: penalty for restrictive PRIMARY operations")
    out.append("  (especially remove/restrict on PRIMARY.TIAB or PRIMARY.MESH).")
    out.append("- Deploy_Score: Confidence_Total_Optional")
    out.append(f"  - {ALPHA_RISK:.1f} * Risk_Penalty")
    out.append(f"  - {BETA_PRIMARY:.1f} * Primary_Restriction_Penalty.")
    out.append("")

    out.append("# SECTION_1_NORMALIZED_RULE_TABLE")
    out.append(render_law_table(global_rows))
    out.append("")

    out.append("# SECTION_2_COMPACT_DEPLOYMENT_LAWS")
    out.append(render_compact_section(global_deployment, global_negatives, prefix="GLOBAL"))
    out.append("")

    # Improvement #4: Domain-specific laws
    out.append("# SECTION_3_DOMAIN_SPECIFIC_LAWS")
    out.append("# Laws below derive from per-domain subsets. Consult these when the target domain is known.")
    out.append("# Domain laws override global laws when Divergence_Reason is set.")
    out.append("# Domain laws supplement global laws (additional context) otherwise.")
    out.append("")

    for domain in sorted(domain_law_dict):
        d_rows = domain_law_dict[domain]
        divergent = find_divergent_laws(global_rows, d_rows)
        d_deployment = select_deployment(d_rows, n=8)
        d_negatives = select_negative_laws(d_rows, n=6)

        out.append(f"## DOMAIN_{domain}")

        if not divergent:
            out.append("# No significant divergence from global laws detected. Global laws apply.")
        else:
            out.append(f"# {len(divergent)} divergent law(s) found. These supplement or override global laws.")
            out.append(f"### DOMAIN_{domain}_DIVERGENT_LAWS")
            for r in divergent:
                reason = r.get("Divergence_Reason", "")
                out.append(
                    f"  [{r['Law_ID']}] {r['Law_Type']} | "
                    f"{r['META_ACTION']}/{r['META_CONCEPT']} | "
                    f"{r['Imperative_EN']} | "
                    f"Reason={reason} | Rep/Suc={r['Rep']:.2f}/{r['Suc']:.2f}"
                )

        out.append("")
        out.append(f"### DOMAIN_{domain}_TOP_DO_LAWS")
        for idx, row in enumerate(d_deployment, 1):
            out.append(
                f"  [{idx:02d}] {row['Law_ID']} | {row['Law_Type']} | "
                f"{row['Action_Operator']}/{row['Target_Block']}/{row['Target_Slot']} | "
                f"{row['Imperative_EN']} | "
                f"Rep/Suc/Con/Sup={row['Rep']:.2f}/{row['Suc']:.2f}/{row['Con']:.2f}/{row['Sup']:.2f}"
            )

        out.append("")
        out.append(f"### DOMAIN_{domain}_TOP_AVOID_LAWS")
        for idx, row in enumerate(d_negatives, 1):
            out.append(
                f"  [{idx:02d}] {row['Law_ID']} | {row['Law_Type']} | "
                f"{row['Action_Operator']}/{row['Target_Block']}/{row['Target_Slot']} | "
                f"{row['Imperative_EN']} | "
                f"Risk={row['Risk']} | "
                f"Rep/Suc/Con/Sup={row['Rep']:.2f}/{row['Suc']:.2f}/{row['Con']:.2f}/{row['Sup']:.2f}"
            )

        out.append("")

    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log_files, records, log_weights = load_records()

    print("=== Log Weights (Improvement #1) ===")
    for lf in log_files:
        log_name = get_log_key(lf)
        w = log_weights.get(log_name, MIN_WEIGHT)
        domain = get_domain_from_log(log_name)
        n_iter = len(set(
            rec.get("iteration", 0)
            for ln, rec in records
            if ln == log_name
        ))
        print(f"  {log_name}: weight={w:.2f}, n_iter={n_iter}, domain={domain}")
    print()

    global_rows = build_rules(log_files, records, log_weights)
    global_deployment = select_deployment(global_rows)
    global_negatives = select_negative_laws(global_rows)

    domain_law_dict = build_domain_laws(records, log_weights)

    output_text = render_output(global_rows, global_deployment, global_negatives, domain_law_dict)
    existing_paths = sorted(
        BASE_DIR.glob(f"{OUTPUT_BASENAME}_ver*.txt"),
        key=lambda p: int(re.search(r"_ver(\d+)\.txt$", p.name).group(1)) if re.search(r"_ver(\d+)\.txt$", p.name) else 0,
    )

    latest_path = existing_paths[-1] if existing_paths else None
    if latest_path and latest_path.read_text(encoding="utf-8") == output_text:
        output_path = latest_path
        print(f"No changes detected. Latest version remains: {output_path}")
    else:
        next_ver = 1
        output_path = BASE_DIR / f"{OUTPUT_BASENAME}_ver{next_ver}.txt"
        while output_path.exists():
            next_ver += 1
            output_path = BASE_DIR / f"{OUTPUT_BASENAME}_ver{next_ver}.txt"
        output_path.write_text(output_text, encoding="utf-8")
        print(f"Written: {output_path}")

    print(f"Global laws: {len(global_rows)} total | {len(global_deployment)} DO | {len(global_negatives)} AVOID")
    for domain in sorted(domain_law_dict):
        d_rows = domain_law_dict[domain]
        divergent = find_divergent_laws(global_rows, d_rows)
        print(f"  Domain {domain}: {len(d_rows)} laws, {len(divergent)} divergent")


if __name__ == "__main__":
    main()
