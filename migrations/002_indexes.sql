CREATE INDEX IF NOT EXISTS ix_members_user ON project_members(user_id);
CREATE INDEX IF NOT EXISTS ix_edges_source ON edges(project_id,source_id);
CREATE INDEX IF NOT EXISTS ix_edges_target ON edges(project_id,target_id);
CREATE INDEX IF NOT EXISTS ix_evidence_claim ON evidence(claim_id,stance);
CREATE INDEX IF NOT EXISTS ix_reviews_claim ON reviews(claim_id,stance);
