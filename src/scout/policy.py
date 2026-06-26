from scout.models import Requirement


def default_requirements() -> list[Requirement]:
    return [
        Requirement(id="sso_admin", label="SSO/admin controls required", keywords=["sso", "saml", "admin", "rbac"], fail_weight=10),
        Requirement(id="no_training", label="No training on customer data", keywords=["not train", "not used to train", "training", "train models"], fail_weight=15),
        Requirement(id="dpa", label="DPA available", keywords=["data processing agreement", "dpa"], fail_weight=12),
        Requirement(id="deletion_retention", label="Deletion/retention controls", keywords=["delete", "deletion", "retention", "export"], fail_weight=12),
        Requirement(id="soc2_iso", label="SOC2 or equivalent preferred", keywords=["soc 2", "soc2", "iso 27001", "iso27001"], fail_weight=8),
        Requirement(id="audit_logs", label="Audit logs preferred", keywords=["audit log", "audit logs", "logging"], fail_weight=8),
    ]
