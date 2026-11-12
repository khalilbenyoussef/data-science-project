"""Sources CSV ajoutees par l'utilisateur : detection, mapping, forme canonique.

Ces outils ne s'appliquent qu'aux sources de type "user". Les sources
officielles (findex, fas, gdp) gardent exactement leur lecteur actuel.
"""


class UserSourceError(ValueError):
    """Erreur explicite (message en francais) sur une source utilisateur."""
