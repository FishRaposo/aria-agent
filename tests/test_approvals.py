from aria_agent.approvals import ApprovalGate


class TestApprovalGate:
    def test_enabled_approves(self):
        gate = ApprovalGate(enabled=True)
        assert gate.request_approval("dangerous_action", {"param": 1}) is True

    def test_disabled_bypasses(self):
        gate = ApprovalGate(enabled=False)
        assert gate.request_approval("anything", {}) is True

    def test_default_is_enabled(self):
        gate = ApprovalGate()
        assert gate.enabled is True

    def test_approval_for_various_actions(self):
        gate = ApprovalGate(enabled=True)
        assert gate.request_approval("delete", {"id": "x"}) is True
        assert gate.request_approval("deploy", {"env": "prod"}) is True
        assert gate.request_approval("read", {}) is True
