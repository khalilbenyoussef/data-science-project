"""Isolation des tests : les sources utilisateur et le catalogue KPI utilisateur
enregistres localement (config/sources/, config/kpi_catalog.user.yaml) ne sont
jamais charges par les tests ; chaque test qui en a besoin fournit les siens.
Les cles LLM de .env sont neutralisees (valeur vide, que load_dotenv ne remplace
pas) : aucun test n'appelle un fournisseur reel ; les tests du chat simulent le LLM."""
import os
from pathlib import Path
import tempfile

_EMPTY = Path(tempfile.gettempdir()) / "biflow_tests_no_user_sources"
os.environ["BIFLOW_SOURCES_DIR"] = str(_EMPTY / "sources")
os.environ["BIFLOW_USER_CATALOG"] = str(_EMPTY / "kpi_catalog.user.yaml")
for _key in ("GROQ_API_KEY", "GOOGLE_API_KEY"):
    os.environ[_key] = ""
