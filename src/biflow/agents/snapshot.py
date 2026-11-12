"""Snapshot Agent : versionne les sources brutes apres la collecte (aucun LLM)."""

from __future__ import annotations

from typing import Any, Mapping

from biflow.agents.base import AgentError, BaseAgent
from biflow.utils.io import cached_sha256_file
from biflow.tools.snapshots import SnapshotStore


class SnapshotAgent(BaseAgent):
    name = "snapshot"

    def get_llm(self):
        self.llm_error = "Snapshot Agent deterministe : aucun LLM"
        return None

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        snap_cfg = self.cfg.get("snapshots") or {}
        if not snap_cfg.get("enabled", True):
            self.log.info("[snapshot] desactive (snapshots.enabled=false)")
            return {"snapshot": {"status": "disabled", "snapshot_id": None}}
        store = SnapshotStore(snap_cfg.get("root", "data/snapshots"))
        if ctx.get("rebuild"):
            return self._rebuild(store, ctx)
        raw_paths = ctx.get("raw_paths") or {}
        if not raw_paths:
            raise AgentError("aucune source collectee a versionner")
        result = store.prepare(raw_paths, ctx.get("sources") or {}, ctx.get("run_id") or self.run_id)
        if result["status"] == "no_change":
            self.log.info("[snapshot] aucune donnee nouvelle (identique a %s) : ETL et KPI ignores",
                          result["snapshot_id"])
            note = f"aucun changement depuis {result['snapshot_id']}"
        else:
            self.log.info("[snapshot] nouvelles donnees -> %s (pending, precedent : %s)",
                          result["snapshot_id"], result.get("previous"))
            note = f"nouveau snapshot {result['snapshot_id']} (pending)"
        notes = dict(ctx.get("llm_notes") or {})
        notes["snapshot"] = note
        return {"snapshot": result, "snapshot_id": result["snapshot_id"], "llm_notes": notes}

    def _rebuild(self, store: SnapshotStore, ctx: Mapping[str, Any]) -> dict[str, Any]:
        """--rebuild : rejoue la suite du pipeline sur les blobs du snapshot publie."""
        try:
            published = store.published_inputs()
        except KeyError as exc:
            raise AgentError("--rebuild : aucun snapshot publie a rejouer") from exc
        for name, meta in published["raw_meta"].items():
            if cached_sha256_file(meta["path"]) != meta["sha256"]:
                raise AgentError(f"--rebuild : blob {name} altere (hash different du manifeste)")
        snapshot_id = published["entry"]["snapshot_id"]
        self.log.info("[snapshot] reconstruction depuis les blobs de %s", snapshot_id)
        notes = dict(ctx.get("llm_notes") or {})
        notes["snapshot"] = f"reconstruction depuis {snapshot_id} (blobs)"
        return {
            "snapshot": {"status": "rebuild", "snapshot_id": snapshot_id,
                         "content_key": published["entry"].get("content_key")},
            "snapshot_id": snapshot_id,
            "raw_paths": published["raw_paths"],
            "raw_meta": published["raw_meta"],
            "llm_notes": notes,
        }
