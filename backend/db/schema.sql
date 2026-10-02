PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    ecli TEXT UNIQUE,
    process_number TEXT,

    court TEXT NOT NULL DEFAULT 'STJ',
    section TEXT,
    area TEXT,

    decision_date TEXT,
    rapporteur TEXT,

    descriptors_json TEXT,
    procedural_type TEXT,
    decision TEXT,
    voting TEXT,

    summary TEXT,
    full_text TEXT,

    text_hash TEXT,

    source_url TEXT NOT NULL UNIQUE,
    fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cases_process_number
    ON cases(process_number);

CREATE INDEX IF NOT EXISTS idx_cases_decision_date
    ON cases(decision_date);


CREATE TABLE IF NOT EXISTS case_norms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    case_id INTEGER NOT NULL,

    diploma TEXT NOT NULL,
    article TEXT,
    paragraph TEXT,
    letter TEXT,
    raw_text TEXT,

    FOREIGN KEY(case_id)
        REFERENCES cases(id)
        ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS issues (
    slug TEXT PRIMARY KEY,

    title TEXT NOT NULL,
    question TEXT NOT NULL,

    source TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,

    issue_slug TEXT NOT NULL,

    label TEXT NOT NULL,
    description TEXT NOT NULL,

    FOREIGN KEY(issue_slug)
        REFERENCES issues(slug)
        ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS stances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    case_id INTEGER NOT NULL,
    issue_slug TEXT NOT NULL,
    position_id TEXT,

    decides_issue INTEGER NOT NULL,

    status TEXT NOT NULL DEFAULT 'REVIEW',

    extraction_model TEXT,
    prompt_version TEXT,

    UNIQUE(case_id, issue_slug),

    FOREIGN KEY(case_id)
        REFERENCES cases(id)
        ON DELETE CASCADE,

    FOREIGN KEY(issue_slug)
        REFERENCES issues(slug),

    FOREIGN KEY(position_id)
        REFERENCES positions(id)
);


CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    stance_id INTEGER NOT NULL,

    role TEXT NOT NULL,

    start_offset INTEGER,
    end_offset INTEGER,

    quote TEXT NOT NULL,

    verified INTEGER NOT NULL DEFAULT 0,

    FOREIGN KEY(stance_id)
        REFERENCES stances(id)
        ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS case_citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    case_id INTEGER NOT NULL,

    cited_process TEXT,
    cited_case_id INTEGER,

    relationship TEXT NOT NULL DEFAULT 'UNKNOWN',

    evidence_id INTEGER,

    FOREIGN KEY(case_id)
        REFERENCES cases(id)
        ON DELETE CASCADE,

    FOREIGN KEY(cited_case_id)
        REFERENCES cases(id),

    FOREIGN KEY(evidence_id)
        REFERENCES evidence(id)
);


CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    stage TEXT NOT NULL,

    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,

    input_hash TEXT NOT NULL UNIQUE,

    output_json TEXT NOT NULL,

    input_tokens INTEGER,
    output_tokens INTEGER,

    cost REAL,

    created_at TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS gold_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    case_id INTEGER NOT NULL,

    issue_slug TEXT NOT NULL,

    expected_position_id TEXT,

    expected_decides_issue INTEGER NOT NULL,

    source TEXT NOT NULL,

    notes TEXT,

    UNIQUE(case_id, issue_slug),

    FOREIGN KEY(case_id)
        REFERENCES cases(id),

    FOREIGN KEY(issue_slug)
        REFERENCES issues(slug)
);

CREATE TABLE IF NOT EXISTS corpus_membership (
    case_id INTEGER NOT NULL,
    issue_slug TEXT NOT NULL,
    inclusion_method TEXT NOT NULL,
    inclusion_note TEXT,
    PRIMARY KEY (case_id, issue_slug),
    FOREIGN KEY (case_id) REFERENCES cases(id),
    FOREIGN KEY (issue_slug) REFERENCES issues(slug)
);