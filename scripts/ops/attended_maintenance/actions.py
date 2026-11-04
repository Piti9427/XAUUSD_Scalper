"""Distinct internal action adapters; no generic workflow or callback registry."""

from dataclasses import replace

from .model import APMeasurement, CostInstallation, OwnedProbe, Reboot


class APAdapter:
    effect = "measure_ap"

    def cohort(self, plan, observed):
        return plan.cohort

    def after_action(self, plan, state, observed):
        return None

    def recovery(self, plan, state, observed, approval):
        if observed.owned_probe:
            identity = observed.owned_probe
            if (not approval.allow_probe_cleanup or type(identity) is not OwnedProbe
                    or identity.operation != plan.operation or identity.boot != observed.boot
                    or type(identity.pid) is not int or identity.pid <= 0 or not identity.started
                    or identity.source != plan.action.probe_sha256):
                raise ValueError("reader_ownership_unverified")
            return "cleanup_probe", (identity,)
        return None


class CostAdapter:
    effect = "install_cost"

    def cohort(self, plan, observed):
        if observed.cost_marker == plan.action.generation:
            return replace(plan.cohort, policy=plan.action.policy, review=plan.action.review)
        if observed.cost_marker == "original":
            return plan.cohort
        raise ValueError("cost_acceptance_unknown")

    def after_action(self, plan, state, observed):
        if observed.cost_marker != plan.action.generation:
            state["failures"].append({"stage": self.effect, "category": "PRIMARY",
                                      "code": "cost_installation_unverified", "exception_type": None})
        return None

    def recovery(self, plan, state, observed, approval):
        if state["effects"].get(self.effect, {}).get("state") != "ACKED":
            # cohort() rejects an unknown marker before any restoration.
            self.cohort(plan, observed)
            return "restore_cost", (observed.cost_marker,)
        return None


class RebootAdapter:
    effect = "reboot"

    def cohort(self, plan, observed):
        return plan.cohort

    def after_action(self, plan, state, observed):
        if observed.boot == state["action_boot"]:
            return "WAITING_REBOOT"
        if not observed.startup_verified:
            return "OPERATOR_REQUIRED"
        return None

    def recovery(self, plan, state, observed, approval):
        return None


_ADAPTERS = {APMeasurement: APAdapter(), CostInstallation: CostAdapter(), Reboot: RebootAdapter()}


def action_adapter(plan):
    return _ADAPTERS[type(plan.action)]
