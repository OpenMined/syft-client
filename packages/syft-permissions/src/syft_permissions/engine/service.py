from dataclasses import dataclass, field

from syft_permissions.engine.request import ACLRequest, AccessLevel
from syft_permissions.engine.tree import ACLTree
from syft_permissions.spec.ruleset import PERMISSION_FILE_NAME, RuleSet


@dataclass
class ACLService:
    owner: str
    tree: ACLTree = field(default_factory=ACLTree)

    def can_access(self, request: ACLRequest) -> bool:
        if request.user.id == self.owner:
            return True

        rule = self.tree.get_compiled_rule(request)
        if rule is None:
            return False

        # Accessing a permission file itself requires ADMIN
        if request.path.endswith(PERMISSION_FILE_NAME):
            request = ACLRequest(
                path=request.path,
                level=AccessLevel.ADMIN,
                user=request.user,
            )

        return rule.check_access(request)

    def add_ruleset(self, rs: RuleSet) -> None:
        self.tree.add_ruleset(rs)

    def remove_ruleset(self, path: str) -> None:
        self.tree.remove_ruleset(path)
