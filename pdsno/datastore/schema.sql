-- Canonical PDSNO NIB schema (SQLite)
-- This file is the single source of truth loaded by NIBStore._initialize_schema.

CREATE TABLE IF NOT EXISTS devices (
	device_id          TEXT     PRIMARY KEY,
	temp_scan_id       TEXT,
	ip_address         TEXT     NOT NULL,
	mac_address        TEXT     UNIQUE NOT NULL,
	hostname           TEXT,
	vendor             TEXT,
	device_type        TEXT,
	firmware_version   TEXT,
	region             TEXT,
	local_controller   TEXT,
	status             TEXT     NOT NULL DEFAULT 'active',
	discovery_method   TEXT,
	first_seen         TEXT,
	last_seen          TEXT,
	last_updated       TEXT,
	version            INTEGER  NOT NULL DEFAULT 0,
	metadata           TEXT     DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS configs (
	config_id          TEXT     PRIMARY KEY,
	device_id          TEXT     NOT NULL,
	config_hash        TEXT     NOT NULL DEFAULT '',
	category           TEXT     NOT NULL DEFAULT 'LOW',
	status             TEXT     NOT NULL DEFAULT 'PENDING',
	proposed_by        TEXT,
	approved_by        TEXT,
	execution_token    TEXT,
	proposed_at        TEXT,
	approved_at        TEXT,
	executed_at        TEXT,
	expiry             TEXT,
	policy_version     TEXT,
	rollback_payload   TEXT,
	config_data        TEXT,
	reason             TEXT,
	version            INTEGER  NOT NULL DEFAULT 0,
	FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE TABLE IF NOT EXISTS policies (
	policy_id          TEXT     PRIMARY KEY,
	policy_version     TEXT     NOT NULL,
	scope              TEXT     NOT NULL,
	target_region      TEXT,
	content            TEXT     NOT NULL,
	distributed_by     TEXT     NOT NULL,
	distributed_at     TEXT,
	valid_from         TEXT,
	valid_until        TEXT,
	is_active          INTEGER  NOT NULL DEFAULT 1,
	version            INTEGER  NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
	event_id           TEXT     PRIMARY KEY,
	event_type         TEXT     NOT NULL,
	actor              TEXT     NOT NULL,
	subject            TEXT,
	action             TEXT     NOT NULL,
	decision           TEXT,
	timestamp          TEXT     NOT NULL,
	payload_ref        TEXT,
	notes              TEXT,
	signature          TEXT     NOT NULL,
	details            TEXT     NOT NULL DEFAULT '{}'
);

CREATE TRIGGER IF NOT EXISTS prevent_event_update
BEFORE UPDATE ON events
BEGIN
	SELECT RAISE(FAIL, 'Event log is immutable - updates not allowed');
END;

CREATE TRIGGER IF NOT EXISTS prevent_event_delete
BEFORE DELETE ON events
BEGIN
	SELECT RAISE(FAIL, 'Event log is immutable - deletions not allowed');
END;

CREATE TABLE IF NOT EXISTS locks (
	lock_id            TEXT     PRIMARY KEY,
	lock_type          TEXT     NOT NULL,
	subject_id         TEXT     NOT NULL,
	held_by            TEXT     NOT NULL,
	acquired_at        TEXT     NOT NULL,
	expires_at         TEXT     NOT NULL,
	associated_request TEXT,
	status             TEXT     NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS controllers (
	controller_id      TEXT     PRIMARY KEY,
	role               TEXT     NOT NULL,
	region             TEXT,
	status             TEXT     NOT NULL DEFAULT 'validating',
	validated_by       TEXT,
	validated_at       TEXT,
	public_key         TEXT,
	certificate        TEXT,
	capabilities       TEXT     DEFAULT '[]',
	metadata           TEXT     DEFAULT '{}',
	version            INTEGER  NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_mac
	ON devices(mac_address);
CREATE INDEX IF NOT EXISTS idx_devices_region
	ON devices(region);
CREATE INDEX IF NOT EXISTS idx_devices_lc
	ON devices(local_controller);
CREATE INDEX IF NOT EXISTS idx_configs_device
	ON configs(device_id);
CREATE INDEX IF NOT EXISTS idx_configs_status
	ON configs(status);
CREATE INDEX IF NOT EXISTS idx_events_type
	ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_actor
	ON events(actor);
CREATE INDEX IF NOT EXISTS idx_events_timestamp
	ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_locks_subject
	ON locks(subject_id, lock_type);
CREATE INDEX IF NOT EXISTS idx_policies_scope
	ON policies(scope, is_active);
