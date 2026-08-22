"""Fix production schema: add missing columns and create missing tables.

After `alembic stamp --purge head` was used to clear a stale revision
(20250730_user_profile_cv) and stamp to 021, the DB's alembic_version table
shows 021 but the actual schema is from the old migration — lacking columns
and tables added in migrations 001-021.

This migration uses IF NOT EXISTS everywhere so it is safe to run on a DB
that is either (a) missing schema from those migrations, or (b) already fully
up to date.

Revision ID: 022_fix_production_schema
Revises: 021
Create Date: 2026-08-22
"""
from alembic import op

revision = "022_fix_production_schema"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Fix users table — add is_active if missing ─────────────────────────
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active"
        " BOOLEAN NOT NULL DEFAULT TRUE"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at"
        " TIMESTAMP NOT NULL DEFAULT NOW()"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users(email)"
    )

    # ── 2. Legacy tables (may already exist from old schema) ──────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS cv_sessions (
            id UUID PRIMARY KEY,
            original_filename VARCHAR(255),
            original_text TEXT,
            cv_data JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id UUID PRIMARY KEY,
            session_id UUID NOT NULL REFERENCES cv_sessions(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # ── 3. Core tables from migration 001 ─────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(255),
            email VARCHAR(255),
            location VARCHAR(255),
            target_roles JSONB,
            preferences JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_candidates_user_id ON candidates(user_id)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS candidate_sources (
            id UUID PRIMARY KEY,
            candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            source_type VARCHAR(50) NOT NULL,
            source_url VARCHAR(2048),
            raw_content TEXT,
            extracted_content JSONB,
            extraction_confidence FLOAT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_candidate_sources_candidate_id"
        " ON candidate_sources(candidate_id)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS candidate_profiles (
            id UUID PRIMARY KEY,
            candidate_id UUID NOT NULL UNIQUE REFERENCES candidates(id) ON DELETE CASCADE,
            summary TEXT,
            professional_identity JSONB,
            career_level VARCHAR(50),
            industries JSONB,
            competencies JSONB,
            skills JSONB,
            experience JSONB,
            education JSONB,
            projects JSONB,
            certifications JSONB,
            achievements JSONB,
            conflicts JSONB,
            version INTEGER NOT NULL DEFAULT 1,
            rebuilt_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_candidate_profiles_candidate_id"
        " ON candidate_profiles(candidate_id)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS evidence_records (
            id UUID PRIMARY KEY,
            candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            claim TEXT NOT NULL,
            evidence_type VARCHAR(50) NOT NULL,
            source_ref VARCHAR(512),
            source_text TEXT,
            strength FLOAT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_evidence_records_candidate_id"
        " ON evidence_records(candidate_id)"
    )

    # ── 4. Jobs tables from migration 002 ─────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id UUID PRIMARY KEY,
            candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            title VARCHAR(255),
            company VARCHAR(255),
            job_url VARCHAR(2048),
            location VARCHAR(255),
            remote_type VARCHAR(50),
            seniority VARCHAR(50),
            employment_type VARCHAR(50),
            salary_min INTEGER,
            salary_max INTEGER,
            salary_currency VARCHAR(10),
            tech_stack JSONB,
            key_responsibilities JSONB,
            company_description TEXT,
            parsing_confidence FLOAT,
            raw_jd TEXT NOT NULL DEFAULT '',
            status VARCHAR(50) NOT NULL DEFAULT 'analyzed',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_jobs_candidate_id ON jobs(candidate_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs(status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS job_requirements (
            id UUID PRIMARY KEY,
            job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            requirement_type VARCHAR(50) NOT NULL,
            category VARCHAR(50) NOT NULL,
            is_required BOOLEAN NOT NULL DEFAULT TRUE,
            seniority_signal VARCHAR(100)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_requirements_job_id"
        " ON job_requirements(job_id)"
    )

    # ── 5. Match table from migration 003 ─────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS match_analyses (
            id UUID PRIMARY KEY,
            candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            overall_score FLOAT NOT NULL DEFAULT 0,
            deterministic_score FLOAT NOT NULL DEFAULT 0,
            llm_score FLOAT,
            match_tier VARCHAR(50) NOT NULL DEFAULT 'low',
            skill_overlap_score FLOAT NOT NULL DEFAULT 0,
            experience_score FLOAT NOT NULL DEFAULT 0,
            location_score FLOAT NOT NULL DEFAULT 0,
            education_score FLOAT NOT NULL DEFAULT 0,
            matched_skills JSONB,
            missing_skills JSONB,
            llm_reasoning TEXT,
            llm_strengths JSONB,
            llm_gaps JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_match_candidate_job UNIQUE (candidate_id, job_id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_match_analyses_candidate_id"
        " ON match_analyses(candidate_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_match_analyses_job_id"
        " ON match_analyses(job_id)"
    )

    # ── 6. Application tables from migration 004 ──────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id UUID PRIMARY KEY,
            candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            status VARCHAR(50) NOT NULL DEFAULT 'draft',
            strategy JSONB,
            notes TEXT,
            follow_up_date DATE,
            applied_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_applications_candidate_id"
        " ON applications(candidate_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_applications_status ON applications(status)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS cv_versions (
            id UUID PRIMARY KEY,
            application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            summary_adapted TEXT,
            headline_adapted VARCHAR(255),
            skills_ordered JSONB,
            changes JSONB,
            evidence_refs JSONB,
            ats_keywords JSONB,
            validation_result JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS cover_letters (
            id UUID PRIMARY KEY,
            application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            content TEXT NOT NULL DEFAULT '',
            evidence_refs JSONB,
            validation_result JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS application_answers (
            id UUID PRIMARY KEY,
            application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            evidence_refs JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS application_events (
            id UUID PRIMARY KEY,
            application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            event_type VARCHAR(50) NOT NULL,
            notes TEXT,
            occurred_at TIMESTAMP NOT NULL DEFAULT NOW(),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # ── 7. Interview preps from migration 005 ─────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS interview_preps (
            id UUID PRIMARY KEY,
            application_id UUID NOT NULL UNIQUE REFERENCES applications(id) ON DELETE CASCADE,
            technical_questions JSON,
            behavioral_questions JSON,
            star_stories JSON,
            questions_to_ask JSON,
            company_research JSON,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_interview_preps_application_id"
        " ON interview_preps(application_id)"
    )

    # ── 8. Form intelligence from migration 011 ───────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS application_forms (
            id UUID PRIMARY KEY,
            application_id UUID NOT NULL UNIQUE
                REFERENCES applications(id) ON DELETE CASCADE,
            form_url VARCHAR(2048),
            discovery_method VARCHAR(50) NOT NULL DEFAULT 'manual',
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            human_fields_pending INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_application_forms_application_id"
        " ON application_forms(application_id)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS application_form_fields (
            id UUID PRIMARY KEY,
            form_id UUID NOT NULL REFERENCES application_forms(id) ON DELETE CASCADE,
            label TEXT NOT NULL,
            field_type VARCHAR(50) NOT NULL DEFAULT 'text',
            semantic_type VARCHAR(100) NOT NULL,
            is_required BOOLEAN NOT NULL DEFAULT TRUE,
            auto_fill_value TEXT,
            human_required BOOLEAN NOT NULL DEFAULT FALSE,
            human_answer TEXT,
            options JSON,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_application_form_fields_form_id"
        " ON application_form_fields(form_id)"
    )

    # ── 9. Application submissions from migration 012 ─────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS application_submissions (
            id UUID PRIMARY KEY,
            application_id UUID NOT NULL UNIQUE
                REFERENCES applications(id) ON DELETE CASCADE,
            submitted_at TIMESTAMP NOT NULL DEFAULT NOW(),
            confirmation_number VARCHAR(255),
            submission_url VARCHAR(2048),
            submitted_via VARCHAR(100) NOT NULL DEFAULT 'manual',
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_application_submissions_application_id"
        " ON application_submissions(application_id)"
    )

    # ── 10. Agent sessions from migration 013 ────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS application_agent_sessions (
            id UUID PRIMARY KEY,
            application_id UUID NOT NULL
                REFERENCES applications(id) ON DELETE CASCADE,
            status VARCHAR(50) NOT NULL DEFAULT 'initializing',
            ats_name VARCHAR(100),
            form_url VARCHAR(2048),
            fields_total INTEGER NOT NULL DEFAULT 0,
            fields_auto_filled INTEGER NOT NULL DEFAULT 0,
            fields_human_pending INTEGER NOT NULL DEFAULT 0,
            fields_confirmed INTEGER NOT NULL DEFAULT 0,
            fields_skipped INTEGER NOT NULL DEFAULT 0,
            avg_confidence FLOAT,
            min_confidence FLOAT,
            confirmation_id VARCHAR(255),
            final_url VARCHAR(2048),
            human_review_requested VARCHAR(1) NOT NULL DEFAULT '0',
            human_confirmed VARCHAR(1) NOT NULL DEFAULT '0',
            screenshot_before_path VARCHAR(1024),
            screenshot_filled_path VARCHAR(1024),
            screenshot_confirm_path VARCHAR(1024),
            error_message TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMP NOT NULL DEFAULT NOW(),
            discovered_at TIMESTAMP,
            filled_at TIMESTAMP,
            submitted_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # ── 11. Skill snapshots from migration 015 ────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS skill_snapshots (
            id UUID PRIMARY KEY,
            role VARCHAR(64) NOT NULL,
            skill_slug VARCHAR(128) NOT NULL,
            skill_name VARCHAR(128) NOT NULL,
            category VARCHAR(64) NOT NULL,
            frequency_pct FLOAT NOT NULL,
            job_count INTEGER NOT NULL DEFAULT 0,
            snapshot_date DATE NOT NULL,
            created_at TIMESTAMP
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_skill_snapshots_role ON skill_snapshots(role)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_skill_snapshots_skill_slug"
        " ON skill_snapshots(skill_slug)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_skill_snapshots_snapshot_date"
        " ON skill_snapshots(snapshot_date)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_skill_snapshot"
        " ON skill_snapshots(role, skill_slug, snapshot_date)"
    )

    # ── 12. Standard answers from migration 019 ───────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS standard_answers (
            id UUID PRIMARY KEY,
            candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            question_type VARCHAR(80) NOT NULL,
            label VARCHAR(255) NOT NULL DEFAULT '',
            answer_text TEXT NOT NULL,
            applies_to_seniority VARCHAR(50),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # ── 13. ADD COLUMN IF NOT EXISTS for columns from intermediate migrations ──
    # migration 006: match_analyses.outcome
    op.execute(
        "ALTER TABLE match_analyses ADD COLUMN IF NOT EXISTS outcome VARCHAR(50)"
    )
    # migration 007: match_analyses career fit columns
    op.execute(
        "ALTER TABLE match_analyses"
        " ADD COLUMN IF NOT EXISTS career_fit_score FLOAT"
    )
    op.execute(
        "ALTER TABLE match_analyses"
        " ADD COLUMN IF NOT EXISTS application_decision VARCHAR(50)"
    )
    op.execute(
        "ALTER TABLE match_analyses ADD COLUMN IF NOT EXISTS hard_blockers JSON"
    )
    # migration 008: candidates knowledge-base columns
    op.execute(
        "ALTER TABLE candidates"
        " ADD COLUMN IF NOT EXISTS work_authorization VARCHAR(100)"
    )
    op.execute(
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS availability VARCHAR(50)"
    )
    op.execute(
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS career_goals TEXT"
    )
    op.execute(
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS salary_min_usd INTEGER"
    )
    op.execute(
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS languages JSON"
    )
    # migration 009: jobs.visa_sponsorship, job_requirements.classification
    op.execute(
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS visa_sponsorship BOOLEAN"
    )
    op.execute(
        "ALTER TABLE job_requirements"
        " ADD COLUMN IF NOT EXISTS classification VARCHAR(50)"
    )
    # migration 010: evidence_records.verification_status
    op.execute(
        "ALTER TABLE evidence_records"
        " ADD COLUMN IF NOT EXISTS verification_status VARCHAR(20)"
    )
    # migration 014: application_agent_sessions.screenshot_after_path
    op.execute(
        "ALTER TABLE application_agent_sessions"
        " ADD COLUMN IF NOT EXISTS screenshot_after_path VARCHAR(1024)"
    )
    # migration 016: cv_versions bullets, application_submissions evidence
    op.execute(
        "ALTER TABLE cv_versions"
        " ADD COLUMN IF NOT EXISTS experience_personalized JSON"
    )
    op.execute(
        "ALTER TABLE cv_versions"
        " ADD COLUMN IF NOT EXISTS projects_personalized JSON"
    )
    op.execute(
        "ALTER TABLE application_submissions"
        " ADD COLUMN IF NOT EXISTS form_data_submitted JSON"
    )
    op.execute(
        "ALTER TABLE application_submissions"
        " ADD COLUMN IF NOT EXISTS screenshot_confirmation_path VARCHAR(2048)"
    )
    # migration 017: match_analyses.requirement_matches
    op.execute(
        "ALTER TABLE match_analyses"
        " ADD COLUMN IF NOT EXISTS requirement_matches JSON"
    )
    # migration 018: jobs.jd_hash
    op.execute(
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS jd_hash VARCHAR(64)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_jobs_jd_hash ON jobs(jd_hash)"
    )
    # migration 020: semantic columns + pgvector
    op.execute(
        "ALTER TABLE match_analyses ADD COLUMN IF NOT EXISTS semantic_score FLOAT"
    )
    op.execute(
        "ALTER TABLE match_analyses ADD COLUMN IF NOT EXISTS top_evidence JSON"
    )
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute(
            "ALTER TABLE jobs"
            " ADD COLUMN IF NOT EXISTS embedding vector(1536)"
        )
        op.execute(
            "ALTER TABLE candidate_profiles"
            " ADD COLUMN IF NOT EXISTS embedding vector(1536)"
        )
        op.execute(
            "ALTER TABLE evidence_records"
            " ADD COLUMN IF NOT EXISTS embedding vector(1536)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_embedding"
            " ON jobs USING hnsw (embedding vector_cosine_ops)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_evidence_embedding"
            " ON evidence_records USING hnsw (embedding vector_cosine_ops)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_profile_embedding"
            " ON candidate_profiles USING hnsw (embedding vector_cosine_ops)"
        )
    except Exception:
        pass
    # migration 021: application_agent_sessions.pause_metadata
    op.execute(
        "ALTER TABLE application_agent_sessions"
        " ADD COLUMN IF NOT EXISTS pause_metadata JSON"
    )


def downgrade() -> None:
    # This migration is a one-way fix; downgrade is a no-op
    # (we cannot safely remove columns added to a production DB)
    pass
