"""
PDSNO Role-Based Access Control (RBAC)

Manages permissions and authorization for:
- Controllers (what operations each controller type can perform)
- Operators (what admins can approve/view/modify)
- API Clients (what external systems can access)
- Devices (what configurations can be applied)

Permission Model:
- Roles: Global Admin, Regional Admin, Local Operator, API Client, Viewer
- Resources: Configs, Devices, Controllers, Audit Logs, Approvals
- Actions: create, read, update, delete, approve, execute
"""

from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging


class Role(Enum):
    """System roles"""
    # Controller roles
    GLOBAL_CONTROLLER = "global_controller"
    REGIONAL_CONTROLLER = "regional_controller"
    LOCAL_CONTROLLER = "local_controller"
    
    # Operator roles
    GLOBAL_ADMIN = "global_admin"
    REGIONAL_ADMIN = "regional_admin"
    LOCAL_OPERATOR = "local_operator"
    VIEWER = "viewer"
    
    # External roles
    API_CLIENT = "api_client"
    API_CLIENT_READONLY = "api_client_readonly"


class Resource(Enum):
    """System resources"""
    CONFIG = "config"
    DEVICE = "device"
    CONTROLLER = "controller"
    AUDIT_LOG = "audit_log"
    APPROVAL = "approval"
    EXECUTION_TOKEN = "execution_token"
    BACKUP = "backup"
    DISCOVERY_REPORT = "discovery_report"
    KEY_MATERIAL = "key_material"
    USER_ACCOUNT = "user_account"


class Action(Enum):
    """Actions on resources"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    EXECUTE = "execute"
    ROLLBACK = "rollback"
    VALIDATE = "validate"


@dataclass
class Permission:
    """Represents a permission"""
    resource: Resource
    action: Action
    conditions: Optional[Dict] = None  # Additional conditions (e.g., region="zone-A")
    
    def __str__(self):
        if self.conditions:
            return f"{self.action.value}:{self.resource.value}:{self.conditions}"
        return f"{self.action.value}:{self.resource.value}"
    
    def matches(self, resource: Resource, action: Action, context: Optional[Dict] = None) -> bool:
        """Check if this permission matches the requested access"""
        if self.resource != resource or self.action != action:
            return False
        
        # Check conditions
        if self.conditions and context:
            for key, value in self.conditions.items():
                if context.get(key) != value:
                    return False
        
        return True


class RoleDefinition:
    """Defines a role with its permissions"""
    
    def __init__(self, role: Role, description: str):
        self.role = role
        self.description = description
        self.permissions: List[Permission] = []
    
    def add_permission(
        self,
        resource: Resource,
        action: Action,
        conditions: Optional[Dict] = None
    ):
        """Add permission to role"""
        self.permissions.append(Permission(resource, action, conditions))
    
    def has_permission(
        self,
        resource: Resource,
        action: Action,
        context: Optional[Dict] = None
    ) -> bool:
        """Check if role has specific permission"""
        for perm in self.permissions:
            if perm.matches(resource, action, context):
                return True
        return False


class RBACManager:
    """
    Manages role-based access control for PDSNO.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Role definitions
        self.roles: Dict[Role, RoleDefinition] = {}
        
        # Entity role assignments: entity_id -> Role
        self.role_assignments: Dict[str, Role] = {}
        
        # Initialize default roles
        self._initialize_default_roles()
    
    def _initialize_default_roles(self):
        """Setup default role permissions"""
        
        # === GLOBAL CONTROLLER ===
        gc = RoleDefinition(Role.GLOBAL_CONTROLLER, "Global Controller")
        # Can validate regional controllers
        gc.add_permission(Resource.CONTROLLER, Action.VALIDATE)
        # Can approve HIGH sensitivity configs
        gc.add_permission(Resource.CONFIG, Action.APPROVE, {'sensitivity': 'HIGH'})
        gc.add_permission(Resource.CONFIG, Action.APPROVE, {'sensitivity': 'MEDIUM'})
        gc.add_permission(Resource.CONFIG, Action.APPROVE, {'sensitivity': 'LOW'})
        # Can issue execution tokens
        gc.add_permission(Resource.EXECUTION_TOKEN, Action.CREATE)
        # Can read all audit logs
        gc.add_permission(Resource.AUDIT_LOG, Action.READ)
        # Can read all devices
        gc.add_permission(Resource.DEVICE, Action.READ)
        # Can manage key material
        gc.add_permission(Resource.KEY_MATERIAL, Action.CREATE)
        gc.add_permission(Resource.KEY_MATERIAL, Action.READ)
        
        self.roles[Role.GLOBAL_CONTROLLER] = gc
        
        # === REGIONAL CONTROLLER ===
        rc = RoleDefinition(Role.REGIONAL_CONTROLLER, "Regional Controller")
        # Can validate local controllers in their region
        rc.add_permission(Resource.CONTROLLER, Action.VALIDATE)
        # Can approve MEDIUM and LOW configs in their region
        rc.add_permission(Resource.CONFIG, Action.APPROVE, {'sensitivity': 'MEDIUM'})
        rc.add_permission(Resource.CONFIG, Action.APPROVE, {'sensitivity': 'LOW'})
        # Can issue execution tokens
        rc.add_permission(Resource.EXECUTION_TOKEN, Action.CREATE)
        # Can read audit logs for their region
        rc.add_permission(Resource.AUDIT_LOG, Action.READ)
        # Can read devices in their region
        rc.add_permission(Resource.DEVICE, Action.READ)
        # Can read discovery reports
        rc.add_permission(Resource.DISCOVERY_REPORT, Action.READ)
        
        self.roles[Role.REGIONAL_CONTROLLER] = rc
        
        # === LOCAL CONTROLLER ===
        lc = RoleDefinition(Role.LOCAL_CONTROLLER, "Local Controller")
        # Can create configs
        lc.add_permission(Resource.CONFIG, Action.CREATE)
        # Can auto-approve LOW configs
        lc.add_permission(Resource.CONFIG, Action.APPROVE, {'sensitivity': 'LOW'})
        # Can execute configs with valid token
        lc.add_permission(Resource.CONFIG, Action.EXECUTE)
        # Can rollback configs
        lc.add_permission(Resource.CONFIG, Action.ROLLBACK)
        # Can create backups
        lc.add_permission(Resource.BACKUP, Action.CREATE)
        lc.add_permission(Resource.BACKUP, Action.READ)
        # Can create discovery reports
        lc.add_permission(Resource.DISCOVERY_REPORT, Action.CREATE)
        # Can read devices in their subnet
        lc.add_permission(Resource.DEVICE, Action.READ)
        lc.add_permission(Resource.DEVICE, Action.UPDATE)  # For config application
        
        self.roles[Role.LOCAL_CONTROLLER] = lc
        
        # === GLOBAL ADMIN (Human) ===
        ga = RoleDefinition(Role.GLOBAL_ADMIN, "Global Administrator")
        # Can do everything
        for resource in Resource:
            for action in Action:
                ga.add_permission(resource, action)
        
        self.roles[Role.GLOBAL_ADMIN] = ga
        
        # === REGIONAL ADMIN (Human) ===
        ra = RoleDefinition(Role.REGIONAL_ADMIN, "Regional Administrator")
        # Can manage configs in their region
        ra.add_permission(Resource.CONFIG, Action.CREATE)
        ra.add_permission(Resource.CONFIG, Action.READ)
        ra.add_permission(Resource.CONFIG, Action.APPROVE, {'sensitivity': 'MEDIUM'})
        ra.add_permission(Resource.CONFIG, Action.APPROVE, {'sensitivity': 'LOW'})
        # Can view audit logs
        ra.add_permission(Resource.AUDIT_LOG, Action.READ)
        # Can manage devices in their region
        ra.add_permission(Resource.DEVICE, Action.READ)
        ra.add_permission(Resource.DEVICE, Action.UPDATE)
        # Can view controllers
        ra.add_permission(Resource.CONTROLLER, Action.READ)
        # Can create backups
        ra.add_permission(Resource.BACKUP, Action.CREATE)
        ra.add_permission(Resource.BACKUP, Action.READ)
        
        self.roles[Role.REGIONAL_ADMIN] = ra
        
        # === LOCAL OPERATOR (Human) ===
        lo = RoleDefinition(Role.LOCAL_OPERATOR, "Local Operator")
        # Can create LOW configs
        lo.add_permission(Resource.CONFIG, Action.CREATE, {'sensitivity': 'LOW'})
        lo.add_permission(Resource.CONFIG, Action.READ)
        # Can view devices in their subnet
        lo.add_permission(Resource.DEVICE, Action.READ)
        # Can view audit logs
        lo.add_permission(Resource.AUDIT_LOG, Action.READ)
        
        self.roles[Role.LOCAL_OPERATOR] = lo
        
        # === VIEWER (Human) ===
        viewer = RoleDefinition(Role.VIEWER, "Read-Only Viewer")
        # Can only read
        viewer.add_permission(Resource.CONFIG, Action.READ)
        viewer.add_permission(Resource.DEVICE, Action.READ)
        viewer.add_permission(Resource.AUDIT_LOG, Action.READ)
        viewer.add_permission(Resource.CONTROLLER, Action.READ)
        
        self.roles[Role.VIEWER] = viewer
        
        # === API CLIENT ===
        api = RoleDefinition(Role.API_CLIENT, "External API Client")
        # Limited read/create permissions
        api.add_permission(Resource.CONFIG, Action.CREATE)
        api.add_permission(Resource.CONFIG, Action.READ)
        api.add_permission(Resource.DEVICE, Action.READ)
        api.add_permission(Resource.AUDIT_LOG, Action.READ)
        
        self.roles[Role.API_CLIENT] = api
        
        # === API CLIENT READ-ONLY ===
        api_ro = RoleDefinition(Role.API_CLIENT_READONLY, "Read-Only API Client")
        # Only read permissions
        api_ro.add_permission(Resource.CONFIG, Action.READ)
        api_ro.add_permission(Resource.DEVICE, Action.READ)
        api_ro.add_permission(Resource.AUDIT_LOG, Action.READ)
        
        self.roles[Role.API_CLIENT_READONLY] = api_ro
        
        self.logger.info(f"Initialized {len(self.roles)} default roles")
    
    def assign_role(self, entity_id: str, role: Role):
        """
        Assign role to entity.
        
        Args:
            entity_id: Entity identifier (controller ID, username, API client)
            role: Role to assign
        """
        self.role_assignments[entity_id] = role
        self.logger.info(f"Assigned role {role.value} to {entity_id}")
    
    def get_role(self, entity_id: str) -> Optional[Role]:
        """Get entity's role"""
        return self.role_assignments.get(entity_id)
    
    def check_permission(
        self,
        entity_id: str,
        resource: Resource,
        action: Action,
        context: Optional[Dict] = None
    ) -> bool:
        """
        Check if entity has permission for action on resource.
        
        Args:
            entity_id: Entity identifier
            resource: Resource being accessed
            action: Action being performed
            context: Additional context (region, sensitivity, etc.)
        
        Returns:
            True if permitted
        """
        role = self.get_role(entity_id)
        
        if not role:
            self.logger.warning(f"No role assigned to {entity_id}")
            return False
        
        role_def = self.roles.get(role)
        
        if not role_def:
            self.logger.error(f"Role definition not found for {role}")
            return False
        
        has_perm = role_def.has_permission(resource, action, context)
        
        if has_perm:
            self.logger.debug(
                f"Permission granted: {entity_id} -> {action.value}:{resource.value}"
            )
        else:
            self.logger.warning(
                f"Permission denied: {entity_id} -> {action.value}:{resource.value}"
            )
        
        return has_perm
    
    def get_permissions(self, entity_id: str) -> List[Permission]:
        """Get all permissions for entity"""
        role = self.get_role(entity_id)
        
        if not role:
            return []
        
        role_def = self.roles.get(role)
        
        if not role_def:
            return []
        
        return role_def.permissions
    
    def can_approve_config(
        self,
        entity_id: str,
        sensitivity: str,
        region: Optional[str] = None
    ) -> bool:
        """
        Check if entity can approve config of given sensitivity.
        
        Args:
            entity_id: Entity identifier
            sensitivity: Config sensitivity (LOW/MEDIUM/HIGH)
            region: Optional region constraint
        
        Returns:
            True if can approve
        """
        context = {'sensitivity': sensitivity}
        if region:
            context['region'] = region
        
        return self.check_permission(
            entity_id,
            Resource.CONFIG,
            Action.APPROVE,
            context
        )
    
    def can_execute_config(
        self,
        entity_id: str,
        device_id: str
    ) -> bool:
        """
        Check if entity can execute config on device.
        
        Args:
            entity_id: Entity identifier
            device_id: Target device
        
        Returns:
            True if can execute
        """
        return self.check_permission(
            entity_id,
            Resource.CONFIG,
            Action.EXECUTE,
            {'device_id': device_id}
        )
    
    def can_validate_controller(
        self,
        validator_id: str,
        controller_type: str
    ) -> bool:
        """
        Check if controller can validate another controller.
        
        Args:
            validator_id: Validator controller ID
            controller_type: Type being validated (regional/local)
        
        Returns:
            True if can validate
        """
        return self.check_permission(
            validator_id,
            Resource.CONTROLLER,
            Action.VALIDATE,
            {'controller_type': controller_type}
        )


# Example usage:
"""
from pdsno.security.rbac import RBACManager, Role, Resource, Action

# Initialize RBAC
rbac = RBACManager()

# Assign roles
rbac.assign_role("global_cntl_1", Role.GLOBAL_CONTROLLER)
rbac.assign_role("regional_cntl_zone-A_1", Role.REGIONAL_CONTROLLER)
rbac.assign_role("local_cntl_001", Role.LOCAL_CONTROLLER)
rbac.assign_role("admin_user", Role.GLOBAL_ADMIN)
rbac.assign_role("monitoring_api", Role.API_CLIENT_READONLY)

# Check permissions

# Can Global Controller approve HIGH sensitivity config?
can_approve = rbac.check_permission(
    entity_id="global_cntl_1",
    resource=Resource.CONFIG,
    action=Action.APPROVE,
    context={'sensitivity': 'HIGH'}
)  # Returns: True

# Can Regional Controller approve HIGH sensitivity config?
can_approve = rbac.check_permission(
    entity_id="regional_cntl_zone-A_1",
    resource=Resource.CONFIG,
    action=Action.APPROVE,
    context={'sensitivity': 'HIGH'}
)  # Returns: False

# Can Local Controller execute config?
can_execute = rbac.can_execute_config(
    entity_id="local_cntl_001",
    device_id="switch-01"
)  # Returns: True

# Can API client create configs?
can_create = rbac.check_permission(
    entity_id="monitoring_api",
    resource=Resource.CONFIG,
    action=Action.CREATE
)  # Returns: False (read-only)

# Get all permissions for an entity
permissions = rbac.get_permissions("admin_user")
for perm in permissions:
    print(perm)
"""