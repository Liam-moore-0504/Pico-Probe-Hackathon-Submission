ALTER TABLE plugin_packages ADD COLUMN package_path TEXT;
CREATE INDEX ix_plugin_packages_state ON plugin_packages(approval_status,enabled);
