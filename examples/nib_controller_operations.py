"""
NIBStore Controller Operations - Gap Fix

Add this code to pdsno/datastore/sqlite_store.py after the device operations section.
"""

# ===== Controller Operations =====

def get_controller(self, controller_id: str) -> Optional[Controller]:
    """Get controller by ID"""
    with self._get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM controllers WHERE controller_id = ?",
            (controller_id,)
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_controller(row)
        return None

def get_controllers_by_region(self, region: str) -> List[Controller]:
    """Get all controllers in a specific region"""
    with self._get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM controllers WHERE region = ? AND status = 'active'",
            (region,)
        )
        return [self._row_to_controller(row) for row in cursor.fetchall()]

def upsert_controller(self, controller: Controller) -> NIBResult:
    """
    Insert or update controller with optimistic locking.
    
    Returns:
        NIBResult with success=False and conflict=True on version mismatch
    """
    with self._get_connection() as conn:
        # Check if controller exists
        existing = self.get_controller(controller.controller_id)
        
        if existing:
            # Update with version check
            cursor = conn.execute(
                """
                UPDATE controllers SET
                    role = ?, region = ?, status = ?, validated_by = ?,
                    validated_at = ?, public_key = ?, certificate = ?,
                    capabilities = ?, metadata = ?, version = version + 1
                WHERE controller_id = ? AND version = ?
                """,
                (
                    controller.role, controller.region, controller.status,
                    controller.validated_by,
                    controller.validated_at.isoformat() if controller.validated_at else None,
                    controller.public_key, controller.certificate,
                    json.dumps(controller.capabilities) if isinstance(controller.capabilities, list) else controller.capabilities,
                    json.dumps(controller.metadata) if isinstance(controller.metadata, dict) else controller.metadata,
                    controller.controller_id, controller.version
                )
            )
            
            if cursor.rowcount == 0:
                return NIBResult(
                    success=False,
                    error="CONFLICT: Version mismatch - controller was modified by another process",
                    conflict=True
                )
            
            return NIBResult(success=True, data=controller.controller_id)
        else:
            # Insert new controller
            controller.validated_at = controller.validated_at or datetime.now(timezone.utc)
            
            conn.execute(
                """
                INSERT INTO controllers (
                    controller_id, role, region, status, validated_by,
                    validated_at, public_key, certificate, capabilities,
                    metadata, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    controller.controller_id, controller.role, controller.region,
                    controller.status, controller.validated_by,
                    controller.validated_at.isoformat(),
                    controller.public_key, controller.certificate,
                    json.dumps(controller.capabilities) if isinstance(controller.capabilities, list) else controller.capabilities,
                    json.dumps(controller.metadata) if isinstance(controller.metadata, dict) else controller.metadata,
                    controller.version
                )
            )
            
            return NIBResult(success=True, data=controller.controller_id)

def _row_to_controller(self, row: sqlite3.Row) -> Controller:
    """Convert database row to Controller object"""
    return Controller(
        controller_id=row['controller_id'],
        role=row['role'],
        region=row['region'],
        status=row['status'],
        validated_by=row['validated_by'],
        validated_at=datetime.fromisoformat(row['validated_at']) if row['validated_at'] else None,
        public_key=row['public_key'],
        certificate=row['certificate'],
        capabilities=json.loads(row['capabilities']) if row['capabilities'] else [],
        metadata=json.loads(row['metadata']) if row['metadata'] else {},
        version=row['version']
    )
