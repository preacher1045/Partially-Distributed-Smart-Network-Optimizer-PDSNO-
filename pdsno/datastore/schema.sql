-- PDSNO NIB schema (SQLite)
-- Keep this file aligned with scripts/init_db.py::_init_sqlite_schema.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS devices (
	device_id TEXT PRIMARY KEY,
	temp_scan_id TEXT,
	ip_address TEXT NOT NULL,
	mac_address TEXT UNIQUE NOT NULL,
	hostname TEXT,
	vendor TEXT,
	device_type TEXT,
	status TEXT NOT NULL,
	first_seen TEXT NOT NULL,
	last_seen TEXT NOT NULL,
	managed_by_lc TEXT,
	region TEXT,
	version INTEGER DEFAULT 0,
	metadata TEXT
);

CREATE TABLE IF NOT EXISTS controllers (
	controller_id TEXT PRIMARY KEY,
	role TEXT NOT NULL,
	region TEXT,
	status TEXT NOT NULL,
	validated_by TEXT,
	validated_at TEXT,
	public_key TEXT,
	certificate TEXT,
	capabilities TEXT,
	metadata TEXT,
	version INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS config_records (
	config_id TEXT PRIMARY KEY,
	device_id TEXT NOT NULL,
	config_lines TEXT NOT NULL,
	created_by TEXT NOT NULL,
	created_at TEXT NOT NULL,
	approved_by TEXT,
	approved_at TEXT,
	executed_at TEXT,
	status TEXT NOT NULL,
	sensitivity TEXT NOT NULL,
	version INTEGER DEFAULT 0,
	FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE TABLE IF NOT EXISTS config_approvals (
	approval_id TEXT PRIMARY KEY,
	config_id TEXT NOT NULL,
	approver_id TEXT NOT NULL,
	approved_at TEXT NOT NULL,
	decision TEXT NOT NULL,
	comments TEXT,
	FOREIGN KEY (config_id) REFERENCES config_records(config_id)
);

CREATE TABLE IF NOT EXISTS execution_tokens (
	token_id TEXT PRIMARY KEY,
	config_id TEXT NOT NULL,
	device_id TEXT NOT NULL,
	issued_by TEXT NOT NULL,
	issued_at TEXT NOT NULL,
	expires_at TEXT NOT NULL,
	signature TEXT NOT NULL,
	used INTEGER DEFAULT 0,
	FOREIGN KEY (config_id) REFERENCES config_records(config_id),
	FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE TABLE IF NOT EXISTS backups (
	backup_id TEXT PRIMARY KEY,
	device_id TEXT NOT NULL,
	config_id TEXT,
	config_snapshot TEXT NOT NULL,
	created_at TEXT NOT NULL,
	created_by TEXT NOT NULL,
	metadata TEXT,
	FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE TABLE IF NOT EXISTS events (
	event_id INTEGER PRIMARY KEY AUTOINCREMENT,
	timestamp TEXT NOT NULL,
	event_type TEXT NOT NULL,
	controller_id TEXT,
	device_id TEXT,
	config_id TEXT,
	details TEXT,
	severity TEXT
);

CREATE TABLE IF NOT EXISTS discovery_reports (
	report_id TEXT PRIMARY KEY,
	local_controller_id TEXT NOT NULL,
	subnet TEXT NOT NULL,
	scan_start TEXT NOT NULL,
	scan_end TEXT NOT NULL,
	devices_found INTEGER,
	new_devices INTEGER,
	metadata TEXT
);

CREATE TABLE IF NOT EXISTS locks (
	lock_id TEXT PRIMARY KEY,
	resource_type TEXT NOT NULL,
	resource_id TEXT NOT NULL,
	holder_id TEXT NOT NULL,
	acquired_at TEXT NOT NULL,
	expires_at TEXT,
	UNIQUE(resource_type, resource_id)
);

CREATE TABLE IF NOT EXISTS schema_version (
	version TEXT PRIMARY KEY,
	applied_at TEXT NOT NULL
);

INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES ('1.0.0', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));

CREATE INDEX IF NOT EXISTS idx_devices_mac ON devices(mac_address);
CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(ip_address);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_devices_region ON devices(region);

CREATE INDEX IF NOT EXISTS idx_controllers_role ON controllers(role);
CREATE INDEX IF NOT EXISTS idx_controllers_region ON controllers(region);

CREATE INDEX IF NOT EXISTS idx_config_device ON config_records(device_id);
CREATE INDEX IF NOT EXISTS idx_config_status ON config_records(status);
CREATE INDEX IF NOT EXISTS idx_config_sensitivity ON config_records(sensitivity);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_controller ON events(controller_id);
CREATE INDEX IF NOT EXISTS idx_events_device ON events(device_id);

CREATE INDEX IF NOT EXISTS idx_locks_resource ON locks(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_locks_holder ON locks(holder_id);
