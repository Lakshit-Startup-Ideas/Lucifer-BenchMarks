"""M6 experiment: accept-all vs deterministic vs hybrid (deterministic + peer evaluation) review, and what a poor tenant gains. Registered in docs/M6-PREREGISTRATION.md."""
from __future__ import annotations

import json
import sys

import numpy as np

from .distributed import Child, Parent
from .knowledge import KnowledgeBase, Reviewer
from .learner import D
from .m2 import paired_ci
from .m5 import _weights

CONTEXTS, SHARED = 6, range(3)
N_TRAIN = {"A": 60, "B": 12, "C": 12}
N_VAL, N_TEST, EXTRA_EPOCHS, LR = 200, 300, 5, 0.1
RECEIVER_MARGIN = 0.02
POISON_KINDS = ("flip", "random", "blend")


def make_world(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    wa = _weights(rng)
    own = {"B": _weights(rng), "C": _weights(rng)}
    rules = {"A": wa, **{t: wa[:3] + own[t][3:] for t in ("B", "C")}}  # contexts 0-2 shared by everyone, 3-5 tenant-specific
    data = {}
    for t, w in rules.items():
        draw = lambda n: [(lambda X: (X, (X @ w[c] > 0).astype(float)))(rng.normal(size=(n, D))) for c in range(CONTEXTS)]
        data[t] = {"train": draw(N_TRAIN[t]), "val": draw(N_VAL), "test": draw(N_TEST)}
    return {"rules": rules, "data": data}


def train_child(child: Child, blocks: list, seed: int) -> None:
    rng = np.random.default_rng([seed, 31])
    ids = [child.learner.observe(c, X[i], int(y[i])) for c, (X, y) in enumerate(blocks) for i in range(len(X))]
    for _ in range(1 + EXTRA_EPOCHS):
        child.learner.learn([ids[i] for i in rng.permutation(len(ids))], lr=LR)


def pkg_accuracy(rule, X, y) -> float:
    return float(np.mean((X @ np.asarray(rule) > 0) == y))


def local_accuracy(child: Child, ctx: int, X, y) -> float:
    return float(np.mean((child.learner.model.logit(ctx, X) > 0) == y))


class Peer:
    """A child that evaluates packages on its own private validation data and reports two numbers."""

    def __init__(self, child: Child, val: list) -> None:
        self.child, self.val = child, val

    def evaluate(self, pkg: dict) -> list[dict]:
        X, y = self.val[pkg["ctx"]]
        suite = pkg["pkg_id"]
        return [self.child.evaluation(suite, "pkg-acc", pkg_accuracy(pkg["rule"], X, y), len(y)),
                self.child.evaluation(suite, "local-acc", local_accuracy(self.child, pkg["ctx"], X, y), len(y))]


def poison_rule(kind: str, honest: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    r = rng.normal(size=D)
    r /= np.linalg.norm(r)
    v = {"flip": -honest, "random": r, "blend": -0.5 * honest + 0.5 * r}[kind]
    return v / np.linalg.norm(v)


def run_seed(seed: int) -> dict:
    world = make_world(seed)
    parent = Parent()
    ids = {t: parent.issue_credentials(f"tenant-{t.lower()}") for t in ("A", "B", "C")}
    ids["M"] = parent.issue_credentials("tenant-m")
    kids = {t: Child(cid, f"tenant-{t.lower()}", key, seed * 10 + i) for i, (t, (cid, key)) in enumerate(ids.items())}
    for t in ("A", "B", "C"):
        train_child(kids[t], world["data"][t]["train"], seed + 100 * "ABC".index(t))
    for t, kid in kids.items():
        assert parent.receive(kid.checkpoint("cp-1"))[0]
    peers = [Peer(kids[t], world["data"][t]["val"]) for t in ("B", "C")]
    rng = np.random.default_rng([seed, 41])
    kbs = {a: KnowledgeBase() for a in ("accept-all", "deterministic", "hybrid")}
    reviewer = Reviewer(parent, kbs["hybrid"])
    batch = []
    for ctx in range(CONTEXTS):
        honest = kids["A"].export_package(ctx, "cp-1")
        batch.append(({**honest, "pkg_id": reviewer.new_id()}, "honest-shared" if ctx in SHARED else "honest-specific", kids["A"]))
        kind = POISON_KINDS[int(rng.integers(0, 3))]
        bad = kids["M"].export_package(ctx, "cp-1", rule=poison_rule(kind, np.array(honest["rule"]), rng))
        batch.append(({**bad, "pkg_id": reviewer.new_id()}, f"poison-{kind}", kids["M"]))
    order = rng.permutation(len(batch))
    outcomes = {a: {} for a in kbs}
    messages = 0
    for i in order:
        pkg, category, origin = batch[i]
        det_reasons = reviewer.deterministic(pkg, origin)
        evidence = reviewer.peer_evidence(pkg, peers)
        messages += 2 * len(peers)
        decisions = {"accept-all": True, "deterministic": not det_reasons}
        for arm in ("accept-all", "deterministic"):
            if decisions[arm]:
                kbs[arm].promote(pkg, {"arm": arm})
        decisions["hybrid"] = (not det_reasons) and reviewer.peers_agree(pkg, evidence)
        if decisions["hybrid"]:
            kbs["hybrid"].promote(pkg, {"peers": evidence})
        for arm, ok in decisions.items():
            outcomes[arm].setdefault(category, []).append(float(ok))
    # transfer to B (poor tenant): accuracy on shared and tenant-specific contexts
    test, val, b = world["data"]["B"]["test"], world["data"]["B"]["val"], kids["B"]
    acc = {"local-only": [], "blind": [], "reviewed": []}
    for ctx in range(CONTEXTS):
        Xt, yt = test[ctx]
        Xv, yv = val[ctx]
        local = local_accuracy(b, ctx, Xt, yt)
        acc["local-only"].append(local)
        blind = kbs["accept-all"].current().get(ctx)
        acc["blind"].append(pkg_accuracy(blind["rule"], Xt, yt) if blind else local)
        promoted = kbs["hybrid"].current().get(ctx)
        use = promoted is not None and pkg_accuracy(promoted["rule"], Xv, yv) - local_accuracy(b, ctx, Xv, yv) >= RECEIVER_MARGIN
        acc["reviewed"].append(pkg_accuracy(promoted["rule"], Xt, yt) if use else local)
    rates = {arm: {cat: float(np.mean(v)) for cat, v in cats.items()} for arm, cats in outcomes.items()}
    transfer = {arm: {"shared": float(np.mean(v[:3])), "specific": float(np.mean(v[3:]))} for arm, v in acc.items()}
    return {"rates": rates, "transfer": transfer, "messages": messages, "packages": len(batch)}


def analyse(runs: list[dict]) -> dict:
    def poison(arm):
        return np.array([np.mean([r["rates"][arm][k] for k in r["rates"][arm] if k.startswith("poison")]) for r in runs])
    cat = lambda arm, c: np.array([r["rates"][arm][c] for r in runs])
    a: dict = {}
    for arm in ("accept-all", "deterministic", "hybrid"):
        a[f"poison_accept_{arm}"] = paired_ci(poison(arm))
    a["H6a_pass"] = bool(a["poison_accept_hybrid"][0] <= 0.05 and a["poison_accept_hybrid"][2] < 0.10 and a["poison_accept_deterministic"][0] >= 0.90)
    a["H6b_honest_shared_accept_hybrid"] = paired_ci(cat("hybrid", "honest-shared"))
    a["H6b_pass"] = bool(a["H6b_honest_shared_accept_hybrid"][0] >= 0.80)
    a["H6c_honest_specific_accept_hybrid"] = paired_ci(cat("hybrid", "honest-specific"))
    a["H6c_pass"] = bool(a["H6c_honest_specific_accept_hybrid"][0] <= 0.10)
    t = lambda arm, part: np.array([r["transfer"][arm][part] for r in runs])
    a["H6d_reviewed_minus_local_shared"] = paired_ci(t("reviewed", "shared") - t("local-only", "shared"))
    a["H6d_reviewed_minus_local_specific"] = paired_ci(t("reviewed", "specific") - t("local-only", "specific"))
    a["H6d_blind_minus_local_shared"] = paired_ci(t("blind", "shared") - t("local-only", "shared"))
    a["H6d_blind_minus_local_specific"] = paired_ci(t("blind", "specific") - t("local-only", "specific"))
    a["H6d_pass"] = bool(a["H6d_reviewed_minus_local_shared"][0] >= 0.10 and a["H6d_reviewed_minus_local_shared"][1] > 0.05 and a["H6d_reviewed_minus_local_specific"][1] > -0.02)
    kinds = sorted({k for r in runs for k in r["rates"]["hybrid"]})
    a["acceptance_by_category"] = {arm: {k: float(np.mean([r["rates"][arm][k] for r in runs if k in r["rates"][arm]])) for k in kinds} for arm in ("accept-all", "deterministic", "hybrid")}
    a["H6f_messages_per_package"] = float(np.mean([r["messages"] / r["packages"] for r in runs]))
    a["H6f_peer_evaluations_per_package"] = 2.0
    return a


if __name__ == "__main__":
    seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    runs = [run_seed(s) for s in range(seeds)]
    analysis = analyse(runs)
    if len(sys.argv) > 2:
        json.dump({"analysis": analysis, "raw": runs}, open(sys.argv[2], "w"), indent=1)
    print(json.dumps(analysis, indent=1))
