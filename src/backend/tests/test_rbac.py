"""Tests for RBAC - each role can/cannot perform each permission."""
import pytest
from app.core.rbac import Role, Permission, has_permission, PERMISSION_MATRIX, role_level, ROLE_HIERARCHY


def test_viewer_permissions():
    """Viewer can only read investigations."""
    assert has_permission(Role.viewer, Permission.read_investigation)
    assert not has_permission(Role.viewer, Permission.create_investigation)
    assert not has_permission(Role.viewer, Permission.approve_action)
    assert not has_permission(Role.viewer, Permission.manage_connectors)
    assert not has_permission(Role.viewer, Permission.manage_roles)
    assert not has_permission(Role.viewer, Permission.run_action)
    assert not has_permission(Role.viewer, Permission.collect_evidence)
    assert not has_permission(Role.viewer, Permission.generate_hypothesis)


def test_investigator_permissions():
    """Investigator can create/investigate but not approve."""
    assert has_permission(Role.investigator, Permission.create_investigation)
    assert has_permission(Role.investigator, Permission.collect_evidence)
    assert has_permission(Role.investigator, Permission.generate_hypothesis)
    assert has_permission(Role.investigator, Permission.read_investigation)
    assert has_permission(Role.investigator, Permission.suggest_action)
    assert not has_permission(Role.investigator, Permission.approve_action)
    assert not has_permission(Role.investigator, Permission.run_action)
    assert not has_permission(Role.investigator, Permission.manage_roles)
    assert not has_permission(Role.investigator, Permission.manage_connectors)
    assert not has_permission(Role.investigator, Permission.manage_org_settings)
    assert not has_permission(Role.investigator, Permission.manage_webhooks)


def test_approver_permissions():
    """Approver can approve and run actions but not manage connectors."""
    assert has_permission(Role.approver, Permission.approve_action)
    assert has_permission(Role.approver, Permission.run_action)
    assert has_permission(Role.approver, Permission.read_investigation)
    assert has_permission(Role.approver, Permission.create_investigation)
    assert has_permission(Role.approver, Permission.collect_evidence)
    assert has_permission(Role.approver, Permission.generate_hypothesis)
    assert not has_permission(Role.approver, Permission.manage_connectors)
    assert not has_permission(Role.approver, Permission.manage_roles)
    assert not has_permission(Role.approver, Permission.manage_org_settings)
    assert not has_permission(Role.approver, Permission.manage_webhooks)


def test_admin_all_permissions():
    """Admin has all permissions."""
    for perm in Permission:
        assert has_permission(Role.admin, perm), f"Admin missing: {perm}"


def test_permission_matrix_completeness():
    """All roles in matrix, no missing permissions."""
    for role in Role:
        assert role in PERMISSION_MATRIX, f"Role {role} missing from matrix"


def test_permission_matrix_no_unknown_permissions():
    """Every permission in the matrix is a valid Permission enum value."""
    valid_perms = set(Permission)
    for role, perms in PERMISSION_MATRIX.items():
        for perm in perms:
            assert perm in valid_perms, f"Unknown permission {perm} for role {role}"


def test_role_hierarchy_order():
    """Role hierarchy increases privilege level from viewer to admin."""
    assert role_level(Role.viewer) < role_level(Role.investigator)
    assert role_level(Role.investigator) < role_level(Role.approver)
    assert role_level(Role.approver) < role_level(Role.admin)


def test_role_level_unknown():
    """Unknown role string returns -1."""
    assert role_level("ghost") == -1  # type: ignore[arg-type]


def test_role_hierarchy_contains_all_roles():
    """ROLE_HIERARCHY contains every defined Role."""
    for role in Role:
        assert role in ROLE_HIERARCHY, f"Role {role} missing from ROLE_HIERARCHY"


def test_has_permission_unknown_role():
    """has_permission with an unknown role string returns False."""
    result = has_permission("ghost", Permission.read_investigation)  # type: ignore[arg-type]
    assert result is False


def test_admin_superset_of_approver():
    """Admin permissions are a superset of approver permissions."""
    approver_perms = PERMISSION_MATRIX[Role.approver]
    admin_perms = PERMISSION_MATRIX[Role.admin]
    for perm in approver_perms:
        assert perm in admin_perms, f"Admin missing approver permission: {perm}"


def test_approver_superset_of_investigator():
    """Approver permissions are a superset of investigator permissions."""
    investigator_perms = PERMISSION_MATRIX[Role.investigator]
    approver_perms = PERMISSION_MATRIX[Role.approver]
    for perm in investigator_perms:
        assert perm in approver_perms, f"Approver missing investigator permission: {perm}"


def test_investigator_superset_of_viewer():
    """Investigator permissions are a superset of viewer permissions."""
    viewer_perms = PERMISSION_MATRIX[Role.viewer]
    investigator_perms = PERMISSION_MATRIX[Role.investigator]
    for perm in viewer_perms:
        assert perm in investigator_perms, f"Investigator missing viewer permission: {perm}"
