from enum import Enum
from typing import Dict, Set
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .security import verify_session_token, TokenPayload

bearer_scheme = HTTPBearer()


class Role(str, Enum):
    viewer = "viewer"
    investigator = "investigator"
    approver = "approver"
    admin = "admin"


class Permission(str, Enum):
    read_investigation = "read_investigation"
    create_investigation = "create_investigation"
    collect_evidence = "collect_evidence"
    generate_hypothesis = "generate_hypothesis"
    suggest_action = "suggest_action"
    approve_action = "approve_action"
    run_action = "run_action"
    manage_connectors = "manage_connectors"
    manage_roles = "manage_roles"
    manage_org_settings = "manage_org_settings"
    manage_webhooks = "manage_webhooks"


# Permission matrix: role -> set of permissions
PERMISSION_MATRIX: Dict[Role, Set[Permission]] = {
    Role.viewer: {
        Permission.read_investigation,
    },
    Role.investigator: {
        Permission.read_investigation,
        Permission.create_investigation,
        Permission.collect_evidence,
        Permission.generate_hypothesis,
        Permission.suggest_action,
    },
    Role.approver: {
        Permission.read_investigation,
        Permission.create_investigation,
        Permission.collect_evidence,
        Permission.generate_hypothesis,
        Permission.suggest_action,
        Permission.approve_action,
        Permission.run_action,
    },
    Role.admin: {
        Permission.read_investigation,
        Permission.create_investigation,
        Permission.collect_evidence,
        Permission.generate_hypothesis,
        Permission.suggest_action,
        Permission.approve_action,
        Permission.run_action,
        Permission.manage_connectors,
        Permission.manage_roles,
        Permission.manage_org_settings,
        Permission.manage_webhooks,
    },
}

# Role hierarchy: index = privilege level
ROLE_HIERARCHY = [Role.viewer, Role.investigator, Role.approver, Role.admin]


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in PERMISSION_MATRIX.get(role, set())


def role_level(role: Role) -> int:
    try:
        return ROLE_HIERARCHY.index(role)
    except ValueError:
        return -1


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenPayload:
    token = credentials.credentials
    payload = verify_session_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
    return payload


def require_role(minimum_role: Role):
    """FastAPI dependency: requires user to have at least minimum_role."""
    async def _check(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        user_role = Role(user.role)
        if role_level(user_role) < role_level(minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {minimum_role.value}",
            )
        return user
    return _check


def require_permission(permission: Permission):
    """FastAPI dependency: requires user to have specific permission."""
    async def _check(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        user_role = Role(user.role)
        if not has_permission(user_role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission.value}",
            )
        return user
    return _check
