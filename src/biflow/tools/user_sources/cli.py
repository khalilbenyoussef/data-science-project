"""Commande add-source / remove-source (logique testable, entrees/sorties injectables).

Interactive par defaut (confirmer ou modifier) ; --mapping fichier.yaml pour un
mode non interactif. Un mapping deja confirme avec la meme empreinte de
colonnes est reutilise sans question ; une structure differente redemande.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from biflow.config import load_config
from biflow.tools.user_sources import UserSourceError
from biflow.tools.user_sources.canonical import canonical, format_report
from biflow.tools.user_sources.countries import CountryResolver, normalize_name
from biflow.tools.user_sources.detect import detect_read_params, detect_structure, read_user_csv
from biflow.tools.user_sources.mapping import fingerprint, propose_mapping, validate_mapping
from biflow.tools.user_sources.registry import find_reusable, register, unregister
from biflow.utils.countries import is_country, normalize_iso3

ROLE_LABELS = {"pays": "country", "country": "country", "annee": "year", "year": "year",
               "indicateur": "indicator", "indicator": "indicator", "valeur": "value", "value": "value"}
YES = {"o", "oui", "y", "yes"}


def _aliases(cfg: Mapping[str, Any]) -> dict[str, str]:
    return dict(((cfg.get("countries") or {}).get("name_to_iso3")) or {})


def rebind(data: dict, columns) -> dict:
    """Mapping reutilise : memes colonnes a la casse/l'ordre pres -> noms exacts du nouveau fichier."""
    actual = {normalize_name(c): c for c in columns if c != "_line"}

    def name(column):
        return actual.get(normalize_name(column), column) if isinstance(column, str) else column

    cols = data["columns"]
    cols["country"]["column"] = name(cols["country"]["column"])
    for key in ("year", "indicator", "value"):
        cols[key] = name(cols.get(key))
    cols["year_columns"] = [name(c) for c in cols.get("year_columns") or []]
    cols["indicator_columns"] = {name(c): code for c, code in (cols.get("indicator_columns") or {}).items()}
    if cols.get("dimension"):
        cols["dimension"]["column"] = name(cols["dimension"]["column"])
    return data


def _ask_answers(data: dict, proposal: dict, df, detection, ask, out, resolver, name, path, llm_suggest):
    """Questions interactives : roles, unites (obligatoires), pays non reconnus."""
    while True:
        out("Roles proposes :")
        for role, column in (("pays", data["columns"]["country"]["column"]),
                             ("annee", data["columns"].get("year") or "colonnes annees"),
                             ("indicateur", data["columns"].get("indicator") or "-"),
                             ("valeur", data["columns"].get("value") or "-")):
            origin = proposal["origins"].get(ROLE_LABELS[role], "")
            out(f"  {role:10s} : {column} {f'({origin})' if origin else ''}")
        role = ask("Modifier un role ? (pays/annee/indicateur/valeur, Entree pour garder) ").strip().lower()
        if not role:
            break
        if role not in ROLE_LABELS:
            out(f"Role inconnu : {role}")
            continue
        column = ask(f"Colonne pour {role} : ").strip()
        try:
            forced = {r: data["columns"].get(r) if r != "country" else data["columns"]["country"]["column"]
                      for r in ("country", "year", "indicator", "value")}
            forced = {r: c for r, c in forced.items() if isinstance(c, str)}
            forced[ROLE_LABELS[role]] = column
            proposal = propose_mapping(name, str(path), df, detection, resolver, llm_suggest, forced_roles=forced)
            data = proposal["mapping"]
        except UserSourceError as exc:
            out(f"Refuse : {exc}")
    for code, spec in data["indicators"].items():
        while not spec.get("unit"):
            spec["unit"] = ask(f"Unite de l'indicateur '{spec['label']}' ({code}) - jamais devinee "
                               "(ex. percent, fraction, count, usd) : ").strip()
    for value, reason in proposal["unresolved_countries"].items():
        answer = ask(f"Pays non reconnu {value!r} ({reason}) : code ISO3, ou Entree pour exclure : ").strip()
        code = normalize_iso3(answer)
        if code and is_country(code):
            data["country_names"][value] = code
        elif answer:
            out(f"Code {answer!r} invalide : {value!r} reste exclu")
    return data


def add_source(file: str | Path, name: str, *, mapping_file: str | Path | None = None, dry_run: bool = False,
               assume_yes: bool = False, cfg: Mapping[str, Any] | None = None,
               ask: Callable[[str], str] = input, out: Callable[[str], None] = print,
               llm_suggest=None, draft_path: str | Path | None = None) -> dict[str, Any]:
    cfg = cfg if cfg is not None else load_config()
    path = Path(file)
    if not path.is_file():
        raise UserSourceError(f"Fichier introuvable : {path}")
    resolver = CountryResolver(_aliases(cfg))
    read = detect_read_params(path)
    df = read_user_csv(path, read)
    detection = {**detect_structure(df, read["decimal"], resolver), "read": read}
    print_fp = fingerprint(df.columns)
    out(f"Fichier : {path.name} - {len(df)} ligne(s), encodage {read['encoding']}, separateur "
        f"{read['separator']!r}, decimale {read['decimal']!r}, en-tete ligne {read['header_row'] + 1}")
    out(f"Disposition : {detection['layout']} ({detection['evidence']})")

    interactive = not (assume_yes or mapping_file)
    missing_units: list[str] = []
    if mapping_file:
        data = yaml.safe_load(Path(mapping_file).read_text(encoding="utf-8")) or {}
        if data.get("fingerprint") and data["fingerprint"] != print_fp:
            raise UserSourceError("Le mapping fourni decrit une autre structure de colonnes (empreinte differente)")
        data.update(name=name, file=str(path), fingerprint=print_fp)
        status = "provided"
    else:
        existing, status = find_reusable(name, print_fp, cfg)
        if existing is not None:
            data = rebind(existing.model_dump(mode="json"), df.columns)
            data.update(name=name, file=str(path), read=dict(read))  # lecture du nouveau fichier
            out(f"Mapping existant reutilise ({'meme source' if status == 'reused' else 'meme structure : ' + existing.name})"
                " : aucune question")
        else:
            if status == "structure_changed":
                out("Structure differente du mapping enregistre pour cette source : nouvelle confirmation requise")
            proposal = propose_mapping(name, str(path), df, detection, resolver, llm_suggest)
            data = proposal["mapping"]
            for question in proposal["questions"]:
                out(f"? {question}")
            if interactive:
                data = _ask_answers(data, proposal, df, detection, ask, out, resolver, name, path, llm_suggest)
            else:
                missing_units = [code for code, spec in data["indicators"].items() if not spec.get("unit")]
                if missing_units and not dry_run:
                    draft = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
                    if draft_path:
                        Path(draft_path).write_text(draft, encoding="utf-8")
                        out(f"Brouillon de mapping ecrit : {draft_path}")
                    else:
                        out("Brouillon de mapping :\n" + draft)
                    raise UserSourceError("Reponses requises (unite de : " + ", ".join(missing_units)
                                          + ") : completer le brouillon puis relancer avec --mapping")
                for code in missing_units:  # apercu uniquement : unite a declarer
                    data["indicators"][code]["unit"] = "A_DECLARER"

    mapping = validate_mapping(data, df)
    frame, report = canonical(mapping, df, CountryResolver({**_aliases(cfg), **mapping.country_names}))
    report["units_missing"] = missing_units
    out(format_report(report))
    result = {"status": status, "report": report, "mapping": mapping.model_dump(mode="json"), "registered": False}
    if dry_run:
        out("Dry-run : rien n'est enregistre.")
        return result
    if report["mapped"] == 0:
        raise UserSourceError("Aucune observation exploitable : verifier le mapping (pays, annees, valeurs)")
    if report["duplicates"]["conflicting_keys"]:
        raise UserSourceError(f"{report['duplicates']['conflicting_keys']} cle(s) pays/annee/indicateur en double "
                              "avec des valeurs differentes : corriger le fichier ou mapper une dimension")
    if interactive and status != "reused":
        if ask(f"Confirmer l'ajout de la source '{name}' ? [o/N] ").strip().lower() not in YES:
            out("Annule : rien n'est enregistre.")
            return {**result, "status": "cancelled"}
    paths = register(mapping, path, cfg)
    out(f"Source '{name}' enregistree : mapping {paths['mapping']}, copie {paths['file']}. "
        "Elle sera integree au prochain `python main.py run` (nouveau snapshot, quality gate propre).")
    return {**result, "registered": True, "paths": paths}


def remove_source(name: str, cfg: Mapping[str, Any] | None = None, out: Callable[[str], None] = print) -> bool:
    removed = unregister(name, cfg if cfg is not None else load_config())
    out(f"Source '{name}' retiree (la copie dans data/uploads/ est conservee)." if removed
        else f"Aucune source utilisateur nommee '{name}'.")
    return removed


__all__ = ["add_source", "remove_source"]
