# Candidate host books

Medical textbooks used as host documents, stored locally (never committed). A second corpus, of
clinical guidelines, uses the same layout and steps with `configs/guidelines.yaml`.

```
data/corpora/<corpus>/
├── pdf/           the documents, prefixed with their number
├── parts/         textbooks only: the parts first chosen below
└── processed/
    ├── pages.jsonl    one cleaned page per line (input of mmore), references removed
    ├── texts.jsonl    the reference text of each document before chunking; character
    │                  positions elsewhere are offsets in this text
    ├── chunks/        the chunks of each document (mmore sentence chunker, 256 tokens)
    ├── entities/      the Hetionet entities of each document, with the position, page and
    │                  gap of every mention
    └── plots/         heatmaps of these entities
```

To rebuild a corpus:

    uv run python src/books.py pages configs/textbooks.yaml
    uv run python src/books.py chunk configs/textbooks.yaml
    uv run python src/book_entities.py configs/textbooks.yaml
    uv run python src/plot_entities.py configs/textbooks.yaml

The sections below describe the parts first chosen in each textbook; the pipeline now runs on
the full textbooks (`pdf/`).

| # | Book | Part to use | File in `data/corpora/textbooks/parts/` |
|---|---|---|---|
| 1 | [Genetics of Colorectal Cancer (PDQ®), Health Professional Version](https://www.cancer.gov/types/colorectal/hp/colorectal-genetics-pdq) (NCI, version of 21 Mar 2025) | "Major Genetic Syndromes" section (printed pages 28–184) | `1-pdq-colorectal-major-genetic-syndromes.pdf` |
| 2 | [Medical Genetics Summaries](https://www.ncbi.nlm.nih.gov/books/NBK61999/) (NCBI) | CYP2D6 overview + thioridazine, valbenazine, metoprolol, atomoxetine | `2-medical-genetics-cyp2d6.pdf` |
| 3 | [The EBMT Handbook, 8th ed.](https://library.oapen.org/handle/20.500.12657/89904) (2024) | Part V, chapters 35–47 (pages 320–441) | `3-ebmt-part5-ch35-47.pdf` |
| 4 | [Microbiology, Pharmacology, and Immunology for Pre-Clinical Students](https://pressbooks.lib.vt.edu/micropharmimmuno/) (Virginia Tech, 2025) | Chapters 5–6 (pages 321–420) | `4-microbiology-ch5-6.pdf` |
| 5 | [Nursing: Mental Health and Community Concepts](https://wtcs.pressbooks.pub/nursingmhcc/) (Open RN) | Chapters 7–9 (pages 451–708) | `5-nursing-mental-health-ch7-9.pdf` |

## Hetionet entities in each part

Number of distinct Hetionet entities named in each part (`src/book_entities.py`: whole-word
name match on the reference text, licence-filtered graph):

| Book | Pages | Chunks | Gene | Compound | Disease | Side Effect | Symptom | Anatomy | Pharmacologic Class |
|---|---|---|---|---|---|---|---|---|---|
| 1-pdq-colorectal-major-genetic-syndromes | 157 | 715 | 41 | 17 | 22 | 66 | 4 | 22 | 1 |
| 2-medical-genetics-cyp2d6 | 99 | 855 | 33 | 51 | 10 | 106 | 23 | 16 | 3 |
| 3-ebmt-part5-ch35-47 | 122 | 913 | 24 | 92 | 13 | 252 | 35 | 33 | 17 |
| 4-microbiology-ch5-6 | 98 | 450 | 5 | 58 | 7 | 194 | 35 | 53 | 5 |
| 5-nursing-mental-health-ch7-9 | 258 | 637 | 3 | 41 | 15 | 209 | 45 | 19 | 7 |

How to read this:

- Counts are distinct entities; the number in brackets below is how many times the name appears.
- Mentions are counted on the reference text of each book, which still contains the reference
  lists of the parts (book 1 at least): titles of cited articles add mentions.
- **Pathogens are not a Hetionet node type.** Infections only appear as *Side Effect* nodes
  (Aspergillosis, Pneumonia, Influenza...), which only connect to Compounds through
  `causes`. Books 3 and 4 are about pathogens, so few of their main entities can be chain links.
- Many Hetionet names are generic words and match everywhere: *Side Effect* (Infection,
  Anxiety, Surgery, Pregnancy, Death), *Anatomy* (blood, face, arm), *Pharmacologic Class*
  (Vasodilation, Urea). Read the Side Effect counts with care.
- Gene symbols are matched case-sensitively, and a symbol is dropped when the book defines it
  as something else (listed per book below). Abbreviations the book does not define still slip
  through: e.g. NTM, SARS (SARS-CoV-2), NRM in book 3; PDF, CAT, DPT in books 2, 4 and 5.
- Names are matched exactly: aliases that Hetionet does not have (brand names, old gene
  symbols such as TACSTD1 for EPCAM) are not counted.

## Most frequent entities per part

### 1-pdq-colorectal-major-genetic-syndromes

- **Gene:** MLH1 (159), MSH2 (141), APC (113), MSH6 (108), PMS2 (97), MUTYH (66), PTEN (44), EPCAM (42), POLE (32), POLD1 (26)
- **Compound:** Sulindac (32), Celecoxib (21), Erlotinib (9), Raloxifene (7), Sorafenib (7), Imatinib (5), Fluorouracil (5), Oxaliplatin (5), Tamoxifen (4), Irinotecan (3)
- **Disease:** colon cancer (60), breast cancer (53), pancreatic cancer (18), prostate cancer (18), ovarian cancer (15), thyroid cancer (6), melanoma (5), Barrett's esophagus (4), ulcerative colitis (3), pancreatitis (2)
- **Side Effect:** Colorectal cancer (196), Endometrial cancer (94), Colon cancer (60), Surgery (55), Breast cancer (53), Polyp (42), Dysplasia (37), Adenocarcinoma (33), Carcinoma (32), Hepatoblastoma (23)
- **Symptom:** Diarrhea (4), Confusion (2), Fatigue (1), Obesity (1)
- **Anatomy:** brain (19), pancreas (14), arm (13), epithelium (9), renal pelvis (8), endometrium (5), liver (4), ureter (4), blood (3), kidney (3)
- **Pharmacologic Class:** Dyes (1)
- *Gene symbols dropped (the book uses them for something else):* FAP = familial adenomatous polyposis

### 2-medical-genetics-cyp2d6

- **Gene:** CYP2D6 (1053), CYP2C19 (20), ADRB1 (17), ADRB2 (17), CYP2C9 (12), SLC18A2 (12), CYP3A4 (7), GRK5 (5), CYP1A2 (4), OR10P1 (4)
- **Compound:** Metoprolol (144), Atomoxetine (112), Thioridazine (88), Tamoxifen (17), Paroxetine (17), Fluoxetine (15), Quinidine (13), Risperidone (10), Dopamine (9), Primaquine (8)
- **Disease:** schizophrenia (19), hypertension (19), malaria (9), breast cancer (6), attention deficit hyperactivity disorder (5), bipolar disorder (2), gestational diabetes (2), asthma (1), obesity (1), Parkinson's disease (1)
- **Side Effect:** Tardive dyskinesia (38), Schizophrenia (19), Hypertension (19), Bradycardia (17), Parkinsonism (10), Malaria (9), Pregnancy (9), Pain (8), Depression (8), Suicidal ideation (7)
- **Symptom:** Pain (8), Chorea (6), Dystonia (6), Huntington Disease (4), Tics (4), Vomiting (3), Abdominal Pain (3), Constipation (3), Body Weight (3), Muscle Rigidity (2)
- **Anatomy:** heart (65), blood (21), brain (11), liver (6), head (3), tongue (2), face (2), kidney (2), pupil (2), lung (1)
- **Pharmacologic Class:** Phenothiazines (1), Vesicular Monoamine Transporter 2 Inhibitors (1), Catecholamines (1)
- *Gene symbols dropped (the book uses them for something else):* NMS = neuroleptic malignant syndrome

### 3-ebmt-part5-ch35-47

- **Gene:** NTM (14), CD34 (11), SARS (8), CRP (5), NRM (4), TNC (4), CD19 (3), TPO (2), CFH (2), PIGF (2)
- **Compound:** Iron (68), Ceftazidime (17), Voriconazole (17), Amphotericin B (16), Fluconazole (12), Warfarin (11), Sirolimus (11), Vancomycin (10), Posaconazole (10), Thalidomide (10)
- **Disease:** anemia (13), hypertension (10), melanoma (4), breast cancer (3), osteoporosis (2), skin cancer (2), periodontitis (1), primary biliary cirrhosis (1), pancreatitis (1), thyroid cancer (1)
- **Side Effect:** Infection (151), Iron overload (26), Acute graft versus host disease (25), Pneumonia (24), Thrombosis (24), Encephalitis (23), Lymphoma (23), Neutropenia (22), Chronic graft versus host disease (21), Injury (20)
- **Symptom:** Fever (45), Diarrhea (10), Nausea (6), Edema (6), Seizures (5), Vomiting (5), Confusion (4), Headache (4), Chest Pain (3), Cough (3)
- **Anatomy:** blood (184), bone marrow (70), liver (36), lung (15), brain (13), endothelium (8), kidney (5), urine (4), epithelium (4), pes (3)
- **Pharmacologic Class:** Aminoglycosides (9), Polymyxins (7), Carbapenems (6), Azoles (3), Cephalosporins (2), Glycopeptides (2), Anthracyclines (2), Lipoglycopeptides (1), Neuraminidase Inhibitors (1), Macrolides (1)
- *Gene symbols dropped (the book uses them for something else):* PML = progressive multifocal leukoencephalopathy, CPE = carbapenemase producing enterobacterales, MSC = mesenchymal stem cells, FOS = fluid overload syndrome

### 4-microbiology-ch5-6

- **Gene:** CD4 (13), CFTR (1), DPT (1), TNF (1), CAT (1)
- **Compound:** Doxycycline (35), Amphotericin B (21), Chloramphenicol (11), Clindamycin (9), Erythromycin (8), Ceftriaxone (7), Gentamicin (7), Tetracycline (6), Ketoconazole (6), Itraconazole (6)
- **Disease:** malaria (33), anemia (6), acquired immunodeficiency syndrome (2), asthma (1), rheumatoid arthritis (1), Kawasaki disease (1), schizophrenia (1)
- **Side Effect:** Infection (172), Pneumonia (109), Rash (74), Influenza (69), Headache (54), Measles (51), Inflammation (51), Death (48), Cough (46), Pain (41)
- **Symptom:** Fever (282), Headache (54), Cough (46), Pain (41), Vomiting (30), Chills (23), Fatigue (21), Nausea (19), Myalgia (16), Diarrhea (13)
- **Anatomy:** blood (175), heart (49), feces (32), urine (30), liver (25), nose (22), face (22), lung (21), respiratory system (20), brain (18)
- **Pharmacologic Class:** Macrolides (14), Cephalosporins (4), Vasodilation (2), Penicillins (2), Tetracyclines (1)
- *Gene symbols dropped (the book uses them for something else):* SARS = severe acute respiratory syndrome

### 5-nursing-mental-health-ch7-9

- **Gene:** CRH (7), PDF (7), CD4 (1)
- **Compound:** Lithium (40), Buspirone (11), Norepinephrine (9), Lorazepam (8), Caffeine (8), Dopamine (7), Hydroxyzine (5), Sertraline (2), Valproic Acid (2), Topiramate (2)
- **Disease:** bipolar disorder (100), panic disorder (10), schizophrenia (8), Alzheimer's disease (7), hypothyroidism (4), chronic obstructive pulmonary disease (3), asthma (2), multiple sclerosis (2), Parkinson's disease (2), migraine (2)
- **Side Effect:** Anxiety (360), Depression (330), Stress (142), Bipolar disorder (100), Suicide (60), Anxiety disorder (48), Obsessive-compulsive disorder (46), Fear (43), Mania (36), Distress (32)
- **Symptom:** Fatigue (21), Hallucinations (12), Weight Gain (11), Confusion (11), Pain (10), Constipation (10), Dizziness (10), Nausea (10), Vomiting (9), Weight Loss (8)
- **Anatomy:** brain (50), blood (30), eye (15), heart (12), nerve (9), kidney (9), liver (9), face (8), head (7), urine (5)
- **Pharmacologic Class:** Benzodiazepines (30), Barbiturates (4), General Anesthesia (4), Urea (2), Central Nervous System Depression (2), Amino Acids (1), Increased Blood Pressure (1)
- *Gene symbols dropped (the book uses them for something else):* DBT = dialectal behavior therapy, CFI = cultural formulation interview, NMS = neuroleptic malignant syndrome
