# DIAM Annotation Guidelines

These guidelines describe the protocol used to annotate the DIAM corpus — Malaysian Parliament (Dewan Rakyat) Hansard proceedings — for two tasks:

1. **Addressee Recognition (AR):** identifying the intended recipient(s) of each utterance.
2. **Dialogue Discourse Parsing (DDP):** identifying discourse relations between utterances under a SDRT-based framework.

This document summarises the working protocol given to trained annotators. The dataset, scripts, and a quantitative summary are released alongside in the same repository.

---

## 1. The Annotation Unit

Parliamentary speech is segmented hierarchically:

> **Utterance → Sentence → Elementary Discourse Unit (EDU)**

- An **utterance** is the collection of words spoken in one turn (one or more sentences).
- A **sentence** is one full sentence within an utterance.
- An **EDU** is the smallest segment of speech that carries a single proposition or communicative function.

EDUs are produced by first splitting utterances into sentences and then segmenting each sentence with an automatic discourse segmenter. Annotators work at the EDU level.

In addition, the corpus includes **Elementary Event Units (EEUs)** — non-verbal events such as `[Applause]`, `[Laughter]`, or `[Stands up]`. EEUs are extracted before segmentation and are annotated for addressees (and may participate in relations) like EDUs. Together, EDUs and EEUs are referred to as **Elementary Units (EUs)**.

**Example (utterance → EDUs):**

> **Puan Young Syefura binti Othman [Bentong]:** *Assalamualaikum warahmatullahi wabarakatuh and greetings. Thank you for giving Bentong the opportunity to discuss this evening.*

becomes three EDUs:

1. *Assalamualaikum warahmatullahi wabarakatuh and greetings.*
2. *Thank you for giving Bentong the opportunity*
3. *to discuss this evening.*

---

## 2. Addressee Annotation

Each EDU is annotated with one or more **addressees** — the intended recipient(s) of that EDU.

### Rules

1. An EDU may have **one or more specific addressees** (multi-addressee).
2. If an EDU is directed to the entire chamber (or to no one in particular), the addressee is **`everyone`**.
3. **Do not combine** `everyone` with specific addressees; if `everyone` is selected, any other selection is ignored.
4. Every EDU must have at least one addressee assigned.

Addressees are chosen from the set of **active participants** in the dialogue — speakers (or non-verbal-event sources) who produced at least one EU in that agenda. An EU cannot designate its own speaker as the addressee.

---

## 3. Discourse Relation Annotation

DIAM follows the **Segmented Discourse Representation Theory (SDRT)** framework as adopted by the STAC corpus, with 16 SDRT relations plus an additional **Interruption** relation introduced for parliamentary discourse, for a total of **17 labelled relation types**. A separate, unlabelled link is used to repair segmentation errors (see §3.3).

### 3.1 Direction convention

Every relation links two EUs and is stored as a triple `{x, y, type}` where:

- **`x` is the parent** (the antecedent — typically the earlier-occurring EU).
- **`y` is the child** (the dependent — typically the later-occurring EU).

That is, the relation arrow points **downwards** from the parent to the child, and no backward relations are permitted: the child's index is always strictly greater than the parent's.

### 3.2 Graph structure

The discourse graph is a **directed acyclic graph (DAG)**, not a tree:

- An EU may have **multiple parents** (multi-parent) — for example, a single ministerial reply that answers two prior MPs' questions.
- An EU may have **multiple children** (multi-child) — for example, a topic statement followed by several Elaborations.
- Multiple relations between the same ordered pair are allowed but rare.
- An EU may not link to itself (no self-loops).

### 3.3 Blank-relation connector (segmentation repair)

When the automatic segmenter has produced an obviously broken split (an EDU that should clearly continue the previous one, e.g., a trailing fragment like `"(6)"`), annotators connect the two adjacent EDUs with a **link but no relation label**. This `[BLANK]` connection is reserved for segmentation repair and is not counted among the 17 relation types.

---

## 4. Relation Taxonomy

Each relation is presented with its definition, cue words/phrases that frequently signal it, and a real Hansard example (English with the original Malay shown in italic). In what follows, `A` denotes the parent EU and `B` the child EU.

### Acknowledgement
**Definition:** B shows understanding or acceptance of A, or signals to move on.
**Cues:** "OK", "Right", "Right then", "Good", "Fine", "Thank you".
**Example:**
> **A — Tuan Yang di-Pertua:** I invite Tuan Lim Guan Eng, Bagan.
> *Saya jemput Tuan Lim Guan Eng, Bagan.*
> **B — Tuan Lim Guan Eng [Bagan]:** Thank you Mr. Speaker but before I…
> *Terima kasih Tuan Yang di-Pertua tetapi sebelum saya…*

### Alternation
**Definition:** Logical disjunction (OR) between A and B.
**Cues:** "or".
**Example:**
> **A — Datuk Seri Dr. Ronald Kiandee [Beluran]:** A question can not contain any arguments, assumptions, thoughts, accusations, praises…
> **B — Datuk Seri Dr. Ronald Kiandee [Beluran]:** or despicable words or contain confounding, sarcastic or hurtful words…

### Background
**Definition:** B (or A) provides stage-setting / context for the event described in the other.
**Cues:** "While…".

### Clarification_question
**Definition:** B is a question that seeks clarification of A (about content or domain).
**Cues:** Question mark (?).
**Example:**
> **A — Tuan Lim Guan Eng [Bagan]:** All these Members of Parliament from Penang, don't be traitors to your own state.
> *Semua ini Ahli Parlimen dari Pulau Pinang ini, jangan jadi pengkhianat kepada negeri sendiri.*
> **B — Tuan Muhammad Fawwaz bin Mohamad Jan [Permatang Pauh]:** What about it?
> *Apa pula?*

### Contrast
**Definition:** A and B share structure but express opposing ideas or negate an expected consequence.
**Cues:** "but", "however", "on the other hand", "nevertheless"; "while"-clauses can also introduce Contrast.
**Example:**
> **A — Perdana Menteri [Dato' Seri Anwar bin Ibrahim]:** It must go down to the level that is considered acceptable as announced
> **B — Perdana Menteri [Dato' Seri Anwar bin Ibrahim]:** but can not be too sudden
> *tetapi tidak boleh terlalu mendadak*

### Correction
**Definition:** B identifies and fixes an error in A (often a self-correction).
**Example:**
> **A — Tuan Afnan Hamimi bin Taib Azamudden [Alor Setar]:** At that time about when discussing compensation rights claims
> **B — Tuan Afnan Hamimi bin Taib Azamudden [Alor Setar]:** I'm sorry, the demand for pamper and also the Penang water payment.

### Comment
**Definition:** B provides an opinion or evaluation of the content of A.
**Cues:** Speaker-oriented adverbs ("luckily", "amazingly"); utterance modifiers ("frankly", "confidentially"); discourse particles ("sorry", "Ooh", "bah").
**Example:**
> **A — Timbalan Yang di-Pertua [Puan Alice Lau Kiong Yieng]:** The Honorable Kangar stood up first, sorry.
> **B — Tuan Zakri bin Hassan [Kangar]:** I'm sorry.

### Conditional
**Definition:** A is a hypothesis and B is the consequence (If A, then B).
**Cues:** "If… then…".
**Example:**
> **A — Puan Yeoh Tseow Suan:** If we can give tax incentives through training
> **B — Puan Yeoh Tseow Suan:** I believe…

### Continuation
**Definition:** B extends or adds to the content of A. Similar to Narration but without a temporal sequence; often both EDUs elaborate or background the same segment.
**Example:**
> **A — Datuk Seri Haji Ahmad bin Haji Maslan [Pontian]:** Overall, the country's inflation rate in 2022 recorded 3.3 percent
> **B — Datuk Seri Haji Ahmad bin Haji Maslan [Pontian]:** and is expected to continue to be under control in 2023.

### Elaboration
**Definition:** B provides further information about the eventuality introduced in A (examples, sub-events, listings).
**Cues:** "for instance", "for example"; explicit listings ("first", "second", "(i)", "(ii)", …).
**Example:**
> **A — Timbalan Menteri Kewangan [Datuk Seri Haji Ahmad bin Haji Maslan]:** Of course I also find it strange
> **B — Timbalan Menteri Kewangan [Datuk Seri Haji Ahmad bin Haji Maslan]:** For example, Yang Berhormat Selayang has given an interesting proposal

### Explanation
**Definition:** B explains the cause or reasoning behind what happened in A.
**Cues:** "because", "since".
**Example:**
> **A — Tuan Jimmy Puah Wee Tse [Tebrau]:** This is very strange
> **B — Tuan Jimmy Puah Wee Tse [Tebrau]:** because if we look at the opposition…

### Narration
**Definition:** The main eventualities of A and B occur in sequential temporal order.
**Example:**
> **A — Tuan Jamaluddin bin Yahya [Pasir Salak]:** During my 23 years of sitting, coming back from teaching in Sarawak
> **B — Tuan Jamaluddin bin Yahya [Pasir Salak]:** and then teaching in 2000

### Parallel
**Definition:** Same structural requirements as Contrast, but A and B share a common theme rather than opposing it.
**Cues:** "too", "also".
**Example:**
> **A — Tuan Lee Chean Chung [Petaling Jaya]:** Now in 2000, it has already used, adopted the accrued accounting system.
> **B — Tuan Lee Chean Chung [Petaling Jaya]:** Also, don't forget Canada in 2002, has already adopted accrued accounting.

### Q-Elab (Question Elaboration)
**Definition:** B is a follow-up question intended to elicit more information needed to answer a prior question A.
**Cues:** Question mark (?).
**Example:**
> **A — Dato' Siti Zailah binti Mohd Yusoff [Rantau Panjang]:** May I ask for some clarification please, Your Honor?
> **B — Datuk Seri Haji Ahmad bin Haji Maslan:** Is it about EPF?

### Question-Answer Pair
**Definition:** A poses a question; B provides the corresponding answer.
**Cues:** Question mark in A.
**Example:**
> **A — Tuan Yang di-Pertua:** Which standing order is that?
> **B — Datuk Che Mohamad Zulkifly bin Jusoh [Besut]:** Standing Order 23(1)(b).

### Result
**Definition:** A causes B; the main eventuality of A is understood to bring about the eventuality of B.
**Cues:** "so".
**Example:**
> **A — Tuan Yang di-Pertua:** I have looked at this question … and have made a decision that this question does not contradict what Beluran said earlier.
> **B — Tuan Yang di-Pertua:** So, I will continue with the question.

### Interruption *(DIAM-specific)*
**Definition:** B interrupts A to shift the topic or seize conversational control. Used when no other relation captures the discourse move and connectivity to the prior context would otherwise be lost. Frequent in parliamentary debate.

---

## 5. Annotator Workflow

Annotation was carried out in a web-based tool with per-user accounts. For each agenda document, an annotator:

1. **Reviews the participant list** — the set of speakers and non-verbal-event sources active in that agenda. Addressees are chosen from this set.
2. **For every EU in order:**
   a. Selects one or more addressees (or `everyone`).
   b. Optionally creates one or more relations linking this EU back to a prior EU. The relation arrow is set to point from the parent (the prior EU) to the child (the current EU), and a label from the 17-relation taxonomy is applied.
3. **Repairs segmentation errors** with the blank-relation connector when an adjacent EU is plainly a fragment of the previous one.

Each agenda is treated as a self-contained dialogue. Annotation respects the no-backward-relation constraint and the addressee rules above.

### Quality control

Three annotators participated, all fluent in English and Malay. Two annotated each document independently; a third served as an adjudicator who resolved disagreements and verified completeness (no orphan EUs or clusters, no backward relations, every EU assigned at least one addressee). Inter-annotator agreement scores are reported in the accompanying paper.

---

## 6. Known Sources of Annotator Disagreement

During adjudication, two label confusion patterns were the most common, both reflecting genuine ambiguity in the data rather than annotator error:

- **Continuation vs. Elaboration.** Both extend a prior EU; Elaboration adds sub-events or examples, while Continuation lacks that specialisation. When the addition is mildly more specific than the parent without listing sub-events, both readings are defensible.
- **Acknowledgment vs. Continuation** on floor-management exchanges (e.g., one speaker thanking the chair before continuing). One reading treats the move as a social receipt (Acknowledgment); the other treats it as structural continuation of the prior turn.

These cases were resolved by the adjudicator on a per-instance basis, and contribute to the moderate label-level inter-annotator agreement reported in the paper.

---

## 7. Related Resources

- The **paper** describes the dataset construction, statistics, and benchmark results in full.
- `data/` contains the annotated train / dev / test splits.
- `generate_statistics.py` reproduces the dataset statistics from `data/`.
- `baseline_ddp/` and `llama3_1_vanilla/` contain the discourse-parsing baselines and the vanilla LLM probe used in the paper.
