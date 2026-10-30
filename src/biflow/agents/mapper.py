"""Mapper : suggestion LLM optionnelle des roles de colonnes d'un CSV utilisateur.

Le LLM ne propose que des roles (pays, annee, indicateur, valeur) parmi les
colonnes existantes ; chaque suggestion est re-validee par des regles
deterministes (biflow.tools.user_sources.mapping). Jamais d'unite ni de valeur.
"""

from __future__ import annotations

from typing import Any, Mapping

from biflow.agents.base import BaseAgent
from biflow.tools.user_sources.mapping import llm_role_suggester


class MapperAgent(BaseAgent):
    name = "mapper"

    def suggester(self):
        """Fonction de suggestion, ou None si aucun LLM n'est disponible."""
        if self.get_llm() is None:
            return None
        return llm_role_suggester(self.ask_json)

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        suggest = self.suggester()
        return {"mapper_suggestion": suggest(dict(ctx)) if suggest else None}
