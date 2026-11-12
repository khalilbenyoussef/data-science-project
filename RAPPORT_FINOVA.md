# FinOVA

## Rapport de préparation et guide complet de l'application

**De la donnée publique au tableau de bord expliqué**

Version 1.0 — 6 novembre 2026

---

## Comment lire ce rapport

Ce document poursuit deux objectifs.

1. **Rassembler tout ce qui a été préparé** : les sources de données, le pipeline de contrôle, le calcul des indicateurs, l'audit indépendant, l'authentification, les rapports PDF et l'interface.
2. **Expliquer l'application de bout en bout**, écran par écran, pour qu'un lecteur non spécialiste comprenne ce qu'il voit, d'où viennent les chiffres et ce qu'ils ne permettent pas de conclure.

Les encadrés **« En clair »** donnent une explication sans jargon. Les sections techniques sont regroupées dans la dernière partie et peuvent être lues séparément.

> **La règle centrale de FinOVA : aucun chiffre n'est inventé, estimé ou calculé par une intelligence artificielle dans l'interface.** Chaque valeur affichée provient d'une source identifiée, passe des contrôles automatiques, puis est publiée avec sa provenance.

---

## Sommaire

1. [Résumé exécutif](#1-résumé-exécutif)
2. [Les principes de conception](#2-les-principes-de-conception)
3. [L'architecture de bout en bout](#3-larchitecture-de-bout-en-bout)
4. [Les données utilisées](#4-les-données-utilisées)
5. [Du fichier brut au chiffre publié](#5-du-fichier-brut-au-chiffre-publié)
6. [Les indicateurs et leur lecture](#6-les-indicateurs-et-leur-lecture)
7. [L'audit indépendant](#7-laudit-indépendant)
8. [Se connecter et gérer les comptes](#8-se-connecter-et-gérer-les-comptes)
9. [La navigation générale](#9-la-navigation-générale)
10. [Les interfaces, page par page](#10-les-interfaces-page-par-page)
11. [Ask Finova](#11-ask-finova)
12. [Les rapports PDF](#12-les-rapports-pdf)
13. [Le design et les animations](#13-le-design-et-les-animations)
14. [L'API et la sécurité](#14-lapi-et-la-sécurité)
15. [Exploiter l'application](#15-exploiter-lapplication)
16. [Ce qui a été vérifié](#16-ce-qui-a-été-vérifié)
17. [Limites et prochaines étapes](#17-limites-et-prochaines-étapes)
18. [Glossaire](#18-glossaire)
19. [Annexes](#19-annexes)

---

# 1. Résumé exécutif

FinOVA est une application de lecture des données d'inclusion financière. Elle rassemble des chiffres publics sur cinq pays — Tunisie, Algérie, Égypte, Jordanie et Maroc — les vérifie, les rend comparables, puis les présente dans un tableau de bord en français, accessible à un utilisateur non expert.

L'application répond à une question simple : **qui utilise les services financiers, comment cela évolue-t-il, et que peut-on raisonnablement en dire ?**

Pour y répondre, FinOVA sépare deux chaînes de traitement.

| Chaîne | Rôle | Résultat |
|---|---|---|
| **Route 1 — Fiabiliser** | Collecter, versionner, profiler, contrôler et charger les données | Une base de données centrale, traçable et contrôlée |
| **Route 2 — Expliquer et publier** | Calculer les indicateurs, les auditer, produire les constats et le tableau de bord | Une vue publiée, lisible et défendable |

### Ce qui a été préparé dans cette phase

| Élément | État | Ce que cela apporte |
|---|---|---|
| Tableau de bord React | Livré | 7 pages métier + administration, responsive |
| Authentification sécurisée | Livré | Comptes sur invitation, rôles, sessions, réinitialisation |
| Page de connexion immersive | Livré | Quatre vidéos locales en arrière-plan, carte de connexion de marque |
| Design system FinOVA | Livré | Palette marine et or, composants cohérents, plus de 4 000 lignes de styles |
| Animations | Livré | Apparitions échelonnées, tracés de courbes, barres progressives, compteurs |
| Page « Mes données » | Livré | Import CSV, détection, mapping, contrôle qualité, comparaison séparée |
| Page « Audit et confiance » | Livré | Contrôles, statuts de publication, traçabilité, test par injection de fautes |
| Ask Finova | Livré | Réponses fondées sur les faits affichés, chiffres vérifiés |
| Rapports PDF | Livré | Rapport d'évaluation et rapport de constats avec annexe optionnelle |
| Sources et qualité | Livré | Frise des agents, contrôle qualité, signatures, historique |

### Les premiers chiffres, en un coup d'œil

Pour la Tunisie en 2024, la vue publiée indique notamment :

| Indicateur | Valeur | Lecture |
|---|---:|---|
| Détention d'un compte | 37,8 % | Un peu plus d'un adulte sur trois |
| Paiement numérique | 23,7 % | Usage encore minoritaire, distinct de la détention |
| Épargne, toutes formes | 48,2 % | Près d'un adulte sur deux a mis de l'argent de côté |
| Fonds d'urgence possible | 88,4 % | Capacité déclarée à réunir une somme en 30 jours |
| Distributeurs automatiques | 35,44 / 100 000 adultes | Réseau physique en progression |
| Agences bancaires | 22,37 / 100 000 adultes | Densité du réseau bancaire |
| Compte en ville / à la campagne | 46,7 % / 30,2 % | Écart de 16,6 points |

Ces valeurs servent d'illustration dans ce rapport. L'application affiche toujours la valeur de la sélection courante, avec son année réellement utilisée.

> **En clair :** FinOVA ne remplace pas une analyse métier. C'est un outil de lecture fiable : il montre le chiffre, dit d'où il vient, signale ses limites et évite les conclusions trop rapides.

---

# 2. Les principes de conception

## 2.1 Le chiffre avant le récit

Une intelligence artificielle peut aider à reformuler une phrase. Elle ne calcule jamais un indicateur, ne complète jamais une valeur manquante et n'invente jamais une année. Les calculs sont déterministes : les mêmes données produisent toujours le même résultat.

## 2.2 Une valeur absente reste absente

Aucune interpolation n'est faite entre deux enquêtes. Si une année n'a pas d'observation, l'application l'indique. Elle peut afficher la dernière enquête disponible, mais le dit explicitement : « Pas d'enquête Findex en 2022 : les chiffres viennent de l'enquête 2021. »

## 2.3 Chaque chiffre a une provenance

Quatre familles de provenance sont affichées sous forme de badges :

| Badge | Signification |
|---|---|
| **Indicateur suivi** | Indicateur du catalogue officiel, calculé par la chaîne sémantique |
| **Source interne** | Indicateur complémentaire lu directement dans la base (ATM, agences, dépôts, crédits) |
| **Source officielle** | Référence nationale ou internationale vérifiée |
| **En attente de données** | La source existe mais n'est pas encore intégrée |
| **Vos données** | Fichier importé par l'utilisateur, jamais mélangé aux chiffres officiels |

Le bouton **« Source et méthode »** de chaque carte ouvre une fiche qui précise la définition, la source, le périmètre, l'année réellement utilisée, les points à vérifier et, si besoin, les détails techniques.

## 2.4 Séparer ce qui est officiel de ce qui est déclaré

Les fichiers importés par un utilisateur ne sont jamais fondus dans les indicateurs officiels. Ils apparaissent dans une page dédiée, avec le badge **« Vos données »**, et dans une annexe séparée des rapports PDF. L'audit officiel ne les compte pas.

## 2.5 Parler à un non-spécialiste

Les libellés techniques sont traduits. Les sigles sont explicités. Les graphiques sont accompagnés d'une phrase de lecture. Les limites sont écrites à côté du chiffre, pas cachées dans une note de bas de page.

Exemples de traductions appliquées dans l'interface :

| Terme technique | Formulation affichée |
|---|---|
| `warehouse` | base de données |
| `KPI` | indicateur |
| `lineage` | traçabilité |
| `fin11a-f` | colonnes détaillées / obstacles déclarés |
| `To load` | En attente de données |
| `UNDP` | PNUD |
| `Association, pas causalité` | Lien observé, pas une cause |

## 2.6 Ne pas suggérer une causalité

Un écart entre deux groupes n'est pas une preuve de cause. L'application écrit « Lien observé, pas une cause » et explique que les sous-groupes ne représentent pas les mêmes personnes. Les pistes proposées sont des hypothèses à tester, pas des recommandations causales.

---

# 3. L'architecture de bout en bout

## 3.1 Vue d'ensemble

```text
Sources publiques
  Findex (Banque mondiale)
  FAS (FMI)
  WDI (Banque mondiale)
        |
        v
+----------------------------- Route 1 : fiabiliser -----------------------------+
| Collecte -> Version des données -> Profilage -> Contrôle qualité -> ETL        |
|                                                       |                        |
|                                            échec ----> arrêt, rien n'est publié |
|                                                       |                        |
|                                                    succès                      |
+-------------------------------------------------------+------------------------+
                                                        v
                                             Base DuckDB (lecture seule pour l'UI)
                                                        |
        +----------------------------- Route 2 : expliquer ----------------------+
        | Semantic / KPI -> Analyste -> Contrat de tableau de bord                |
        |                        \-> Audit indépendant (contrôles A/B/C/F)         |
        +------------------------------------+-----------------------------------+
                                             v
                                  API FastAPI (lecture seule)
                                             v
                                  Interface React (navigateur)
                                             v
                         Pages métier + Ask Finova + PDF + administration
```

## 3.2 Les quatre couches

| Couche | Technologie | Responsabilité |
|---|---|---|
| Pipeline | Python, LangGraph | Orchestrer les étapes, gérer les reprises et les erreurs |
| Données | DuckDB | Stocker les faits, les indicateurs, les explications et l'audit |
| API | FastAPI | Servir le contrat, les sources, l'audit, les PDF et l'authentification |
| Interface | React + TypeScript + Vite | Afficher, expliquer, interagir |

## 3.3 Séparation des responsabilités

- **Route 1** ne publie rien tant que le contrôle qualité n'est pas passé.
- **Route 2** ne recalcule pas les faits : elle les lit et les met en forme.
- **L'API** est en lecture seule sur les données métier ; seules les actions explicitement prévues (import, suppression, administration) écrivent.
- **L'interface** ne fait aucun calcul métier. Elle affiche les valeurs du contrat et ne les modifie pas.

> **En clair :** chaque couche a un seul travail. Si un chiffre est faux, on peut remonter la chaîne jusqu'au fichier source sans traverser une boîte noire.

---

# 4. Les données utilisées

## 4.1 Trois familles de sources

| Source | Contenu | Période | Usage |
|---|---|---|---|
| **Global Findex 2025** (Banque mondiale) | Enquête sur la détention d'un compte, les paiements, l'épargne, l'emprunt, les obstacles, le genre, le revenu, l'éducation, l'activité, le milieu de résidence | Vagues 2011, 2014, 2017, 2021, 2024 selon les pays | Cœur des indicateurs d'inclusion |
| **FAS** (Fonds monétaire international) | Agences bancaires, distributeurs, déposants, emprunteurs, crédits et dépôts rapportés au PIB | 2015–2024 | Réseau physique et intermédiation |
| **WDI** (Banque mondiale) | PIB, PIB par habitant, croissance, taux de change officiel | Selon disponibilité | Contexte macroéconomique |

## 4.2 Couverture pays

Cinq pays sont suivis : **Tunisie (TUN), Algérie (DZA), Égypte (EGY), Jordanie (JOR), Maroc (MAR)**.

Les vagues d'enquête ne sont pas identiques pour tous :

- la Tunisie n'a pas de vague 2011 dans le fichier exploité ;
- le Maroc commence en 2017 ;
- toutes les années ne sont pas des années d'enquête.

L'interface affiche les années réellement observées et signale les reprises d'enquête antérieure. Elle ne fait jamais comme si une année sans enquête était une nouvelle mesure.

## 4.3 Versionnement et signatures

Chaque collecte produit un **snapshot** : une copie horodatée des fichiers, avec une empreinte SHA-256. Cette empreinte permet de vérifier que le fichier lu est bien celui qui a été contrôlé. Les tables de la base conservent le lien vers le snapshot, le run et la version du catalogue.

## 4.4 Ce que les données ne disent pas

| Limite | Conséquence |
|---|---|
| Enquête par échantillon | Les écarts de moins de 2 points sont traités comme du bruit d'enquête |
| Questions séparées | La baisse entre « compte » et « paiement » n'est pas un taux de conversion individuel |
| Sous-groupes distincts | Les écarts entre groupes ne sont pas des effets mesurés |
| Millésimes différents | Les déposants peuvent dater de 2018 alors que d'autres indicateurs sont de 2024 |
| Obstacles détaillés non chargés | La carte des obstacles reste « en attente de données » |
| Données utilisateur | Non vérifiées par l'audit officiel, clairement étiquetées |

---

# 5. Du fichier brut au chiffre publié

## 5.1 Les huit étapes

| Étape | Ce qui se passe | En cas d'échec |
|---|---|---|
| **1. Collecte** | Récupération des fichiers Findex, FAS et WDI | La mise à jour s'arrête |
| **2. Version des données** | Copie horodatée et empreinte SHA-256 | Pas de version, pas de publication |
| **3. Profilage** | Lecture de la structure, des colonnes, des types, des années | Anomalie signalée |
| **4. Contrôle qualité** | Complétude, cohérence, valeurs plausibles, seuil requis | Source exclue ou run arrêté |
| **5. Intégration (ETL)** | Les données validées rejoignent la base centrale | Rien n'est publié |
| **6. Calcul des indicateurs** | Application du catalogue, formules figées | Indicateur bloqué |
| **7. Audit indépendant** | Recalcul et contrôles A1–A5, B1–B9, C1–C4, F1 | Valeur bloquée ou réserve |
| **8. Route 2 et tableau de bord** | Constats, contrat, publication | Vue indisponible, jamais inventée |

## 5.2 Le contrôle qualité

Le contrôle qualité est un **portillon** : une source qui ne dépasse pas le seuil requis ne rejoint pas la base. Les fichiers utilisateur ont leur propre portillon et peuvent être exclus sans bloquer le pipeline officiel.

Le rapport qualité conserve :

- le nombre de lignes et de colonnes ;
- le score obtenu et le seuil requis ;
- les problèmes critiques ;
- les lignes écartées et la raison ;
- la signature du fichier.

## 5.3 La base centrale

La base contient notamment :

| Table | Contenu |
|---|---|
| `fact` | Observations brutes normalisées, avec source, pays, année, indicateur, dimension et valeur |
| `country_year` | Vue large par pays et année |
| `kpi_values` | Indicateurs calculés, statut de publication, raisons de revue |
| `kpi_explanations` | Explication détaillée de chaque valeur |
| `audit_report` | Résultats des contrôles et constats |
| `user_*` | Données importées par les utilisateurs, séparées |

L'interface ne lit jamais une colonne « pratique » sans passer par le contrat Route 2. Cela évite qu'une ancienne définition ou un libellé ambigu réapparaisse à l'écran.

## 5.4 Le contrat de tableau de bord

Le contrat est un fichier JSON versionné. Il décrit :

- le pays, l'année, la date de génération ;
- les pages et leur disponibilité ;
- les cartes, graphiques, encadrés et constats ;
- la provenance de chaque élément ;
- les précautions de lecture ;
- l'historique des changements.

L'API peut générer un contrat à la demande pour un autre pays ou une autre année, avec les mêmes constructeurs déterministes. Le résultat est mis en cache et conservé localement pour une seconde visite immédiate.

---

# 6. Les indicateurs et leur lecture

## 6.1 Deux familles d'indicateurs

| Famille | Exemples | Source | Badge |
|---|---|---|---|
| **Catalogue sémantique** | Détention d'un compte, paiement numérique, épargne, emprunt, écarts de genre, de revenu, d'âge | Findex, calcul déterministe | Indicateur suivi |
| **Indicateurs complémentaires** | Distributeurs, agences, déposants, emprunteurs, crédits/PIB, dépôts/PIB | FAS, lecture directe | Source interne |

Les seconds ne sont pas dans le catalogue officiel : ils sont affichés avec un badge distinct et peuvent porter une réserve.

## 6.2 Les indicateurs principaux

| Indicateur | Définition simple | Unité |
|---|---|---|
| Détention d'un compte | Part des adultes ayant un compte bancaire, financier ou mobile money | % |
| Paiement numérique | Part des adultes ayant envoyé ou reçu un paiement numérique | % |
| Épargne, toutes formes | Part des adultes ayant épargné, quelle que soit la forme | % |
| Épargne formelle | Part des adultes ayant épargné dans une institution financière | % |
| Emprunt formel | Part des adultes ayant emprunté auprès d'une institution financière | % |
| Fonds d'urgence | Part des adultes pouvant réunir une somme en 30 jours | % |
| Écart femmes-hommes | Différence de détention entre hommes et femmes | points |
| Écart de revenu | Différence entre 40 % les plus pauvres et 60 % les plus riches | points |
| Écart d'éducation | Différence entre niveau primaire ou moins et secondaire ou plus | points |
| Écart d'activité | Différence entre hors population active et population active | points |
| Écart villes-campagnes | Différence entre milieu urbain et rural | points |
| Distributeurs | Nombre pour 100 000 adultes | /100k |
| Agences | Nombre pour 100 000 adultes | /100k |
| Déposants / emprunteurs | Nombre pour 1 000 adultes | /1 000 |
| Crédits / dépôts | Encours en pourcentage du PIB | % du PIB |

## 6.3 Comment lire un écart

Un écart de 23 points entre femmes et hommes signifie que les taux de détention diffèrent de 23 points de pourcentage. Il ne signifie pas que 23 % des femmes sont exclues, ni que le genre est la cause de l'écart.

L'application précise :

- les deux valeurs comparées ;
- l'écart en points ;
- l'évolution depuis l'année antérieure observée ;
- le fait que les groupes sont distincts et non appariés ;
- le seuil de signification pratique (environ 2 points).

## 6.4 Le cas de l'épargne et de l'emprunt

L'épargne « toutes formes » et l'épargne « formelle » sont affichées côte à côte. FinOVA ne fabrique pas une catégorie « épargne informelle » par soustraction : cette soustraction ne serait pas une mesure officielle. La même prudence s'applique à l'emprunt.

## 6.5 Les valeurs illustratives de la Tunisie 2024

| Indicateur | Valeur | Année |
|---|---:|---|
| Détention d'un compte | 37,8 % | 2024 |
| Paiement numérique | 23,7 % | 2024 |
| Épargne, toutes formes | 48,2 % | 2024 |
| Épargne formelle | 21,6 % | 2024 |
| Emprunt formel | 3,5 % | 2024 |
| Fonds d'urgence | 88,4 % | 2024 |
| Compte en ville | 46,7 % | 2024 |
| Compte à la campagne | 30,2 % | 2024 |
| Distributeurs | 35,44 / 100 000 adultes | 2024 |
| Agences | 22,37 / 100 000 adultes | 2024 |
| Déposants | 1 063,3 / 1 000 adultes | 2018 |
| Emprunteurs | 253,7 / 1 000 adultes | 2024 |
| Crédits bancaires | 67,8 % du PIB | 2024 |
| Dépôts bancaires | 71,7 % du PIB | 2024 |

> **En clair :** un chiffre de 2018 affiché à côté d'un chiffre de 2024 n'est pas une erreur. C'est la dernière valeur disponible pour cet indicateur, et l'année est toujours visible.

---

# 7. L'audit indépendant

## 7.1 À quoi sert l'audit

L'audit ne refait pas le pipeline : il le contredit. Il relit les données, recalcule les valeurs et vérifie que ce qui est publié correspond à ce qui est stocké. Il peut bloquer une valeur.

## 7.2 Les familles de contrôles

| Famille | Objet | Effet |
|---|---|---|
| **A1–A5 — Recalcul** | Chaque valeur est recalculée depuis les faits, avec une tolérance stricte ; les valeurs nulles restent nulles ; les moyennes de pairs et la complétude sont vérifiées | Échec bloquant |
| **B1–B2 — Unités** | Une seule unité par indicateur ; pourcentages entre 0 et 100 ; points entre -100 et 100 ; densités positives | Échec bloquant |
| **B3–B4 — Entités** | Aucun agrégat présenté comme un pays ; les pairs sont exactement ceux configurés | Échec bloquant |
| **B5–B7 — Traçabilité** | Même snapshot, même run, mêmes empreintes entre l'index, le lineage, le rapport qualité et les valeurs | Échec bloquant |
| **B8–B9 — Catalogue et qualité** | Pas de définition provisoire non signalée ; catalogue identique ; portillon qualité passé | Échec bloquant |
| **C1–C4 — Avertissements** | Vague partielle, pairs incomplets, diagnostic qualité, variation inférieure au bruit d'enquête | Avertissement |
| **F1 — Constats** | Chaque nombre d'un constat doit correspondre à une valeur publiée | Avertissement |

## 7.3 Les statuts de publication

| Statut | Signification |
|---|---|
| **Approuvé** | Aucun contrôle en échec, aucune réserve |
| **Approuvé avec réserve** | Des avertissements ou des raisons de revue existent, mais la valeur reste publiable |
| **Bloqué** | Un contrôle en échec touche la valeur ; elle n'est pas publiée |
| **Non évalué** | La valeur n'a pas encore été soumise à l'audit |

Une valeur absente n'est pas forcément une erreur : elle peut être publiée comme « indisponible », avec sa raison.

## 7.4 Les explications

Pour chaque valeur, l'audit conserve une explication qui remonte jusqu'au fichier :

1. la valeur publiée ;
2. la ou les cellules sources lues, avec le texte brut ;
3. la transformation appliquée ;
4. la formule et la version du catalogue ;
5. les dépendances (sous-groupes, pairs, détention de compte) ;
6. les contrôles qui touchent la valeur ;
7. le statut de publication et les raisons de revue ;
8. une phrase en français et une en anglais.

C'est cette chaîne que la page **Audit et confiance** rend visible.

## 7.5 Le test par injection de fautes

Pour vérifier que l'audit détecte réellement les erreurs, une copie des données est volontairement altérée : valeur modifiée, unité incorrecte, ligne manquante, doublon, etc. L'audit doit signaler chaque faute. Le résultat est affiché dans la page d'audit et dans le rapport d'évaluation.

> **En clair :** l'audit n'est pas un décor. Il a été testé en introduisant de vraies erreurs, et on vérifie qu'il les attrape.

---

# 8. Se connecter et gérer les comptes

## 8.1 La page de connexion

La page de connexion est la première impression de FinOVA. Elle combine :

- quatre vidéos locales en arrière-plan, jouées en boucle, avec passage automatique à la suivante et saut d'une vidéo introuvable ;
- le logo et la signature de marque ;
- un message de positionnement : **« Les chiffres d'abord. Les sources toujours. »** ;
- une carte de connexion claire, avec email, mot de passe et lien « Mot de passe oublié ? » ;
- un fond statique de secours si aucune vidéo ne se charge.

L'accès est réservé aux comptes autorisés. Il n'existe **aucune inscription publique**.

## 8.2 Les parcours de compte

| Parcours | Route | Ce qui se passe |
|---|---|---|
| Connexion | `/login` | Email + mot de passe, création d'une session |
| Mot de passe oublié | `/forgot-password` | Message constant, lien valable 15 minutes, usage unique |
| Réinitialisation | `/reset-password?token=…` | Nouveau mot de passe, déconnexion de toutes les sessions |
| Activation | `/activate?token=…` | Finalisation d'un compte invité, choix du mot de passe |
| Administration | `/admin/users` | Réservé aux administrateurs |

Le message de « mot de passe oublié » est toujours le même, que l'adresse existe ou non. Cela évite de révéler la présence d'un compte.

## 8.3 Les rôles

| Rôle | Accès |
|---|---|
| **Utilisateur** | Tableau de bord, sources, audit, rapports |
| **Administrateur** | Tout, plus la page **Utilisateurs** |

Un administrateur peut inviter un compte, changer son rôle, renvoyer une invitation, désactiver ou réactiver un compte. Il ne peut pas se retirer lui-même le rôle administrateur, et le système refuse de supprimer le dernier administrateur actif.

## 8.4 Les protections

| Mécanisme | Mise en œuvre |
|---|---|
| Mot de passe | Argon2id, mémoire 64 Mio, 3 passes (recommandation OWASP 2024) |
| Jeton d'accès | JWT HS256, durée 15 minutes |
| Jeton de rafraîchissement | Cookie HttpOnly, SameSite Strict, rotation à chaque usage, durée 30 jours |
| Protection CSRF | Jeton dans un cookie lisible + en-tête `X-CSRF-Token` |
| Révocation | Déconnexion, désactivation, réinitialisation : sessions révoquées |
| Invitation | Lien à usage unique, durée 7 jours |
| Réinitialisation | Lien à usage unique, durée 15 minutes |
| Journal | Connexions réussies, échecs, blocages, actions d'administration |
| Stockage | SQLite dédié `data/auth/auth.sqlite3`, séparé de la base métier |

## 8.5 L'envoi des emails

L'application utilise un serveur SMTP configurable. Le parcours Gmail a été validé avec un mot de passe d'application : l'email de réinitialisation arrive réellement dans la boîte du destinataire.

Si le SMTP est indisponible, le message est écrit dans `data/auth/outbox/` et l'interface le signale. Il n'y a pas de faux succès silencieux.

> **En clair :** un compte ne s'improvise pas. Un administrateur invite, la personne active son compte, et chaque session peut être révoquée.

---

# 9. La navigation générale

## 9.1 La barre latérale

La barre latérale contient sept entrées :

1. **Vue d'ensemble**
2. **Inclusion et inégalités**
3. **Accès et crédit**
4. **Pourquoi l'exclusion ?**
5. **Sources et qualité**
6. **Mes données**
7. **Audit et confiance**

Un administrateur voit en plus **Utilisateurs**.

Chaque entrée a une icône, un libellé et un indicateur actif doré. Le bas de la barre affiche l'email de l'utilisateur, son rôle et le bouton **Déconnexion**.

## 9.2 La barre supérieure

La barre supérieure contient :

- le fil d'Ariane de la page courante ;
- le sélecteur de **pays** (Tunisie, Algérie, Égypte, Jordanie, Maroc) ;
- le sélecteur d'**année** ;
- un repère « enquête » à côté des années réellement observées.

Le changement de pays ou d'année recharge le contrat. La vue précédente reste affichée pendant le calcul, avec un bandeau indiquant le temps écoulé. Les pages déjà consultées sont mises en cache pour être instantanées.

## 9.3 Les bandeaux de contexte

| Bandeau | Quand il apparaît | Ce qu'il dit |
|---|---|---|
| Années d'enquête | Le pays a des vagues observées | « Années d'enquête Findex pour la Tunisie : 2017, 2021, 2024. Les autres années reprennent la dernière enquête antérieure. » |
| Vague utilisée | L'année demandée n'a pas d'enquête | « Pas d'enquête Findex en 2022 : les chiffres viennent de l'enquête 2021. » |
| Vue générée | La vue a été calculée à la demande | « Cette vue a été préparée à la demande pour ce pays et cette année. » |

## 9.4 Le pied de page

Le pied de page rappelle le pays, l'année, la date de mise à jour et le nombre de données sourcées. Ce n'est pas un décor : c'est un repère de version.

---

# 10. Les interfaces, page par page

## 10.1 Vue d'ensemble

**Objectif :** donner en quelques secondes l'état de l'inclusion financière du pays, puis permettre d'approfondir.

### Ce que l'on voit

- Un en-tête avec le pays, l'année et la date de mise à jour.
- Un bouton **PDF** qui télécharge « Constats et pistes de recommandation ».
- Quatre cartes clés : détention d'un compte, paiement numérique, épargne, fonds d'urgence.
- Un graphique en courbe de la détention d'un compte par vague Findex.
- Un graphique en barres de comparaison avec les pays voisins.
- Un encadré **« À retenir »** avec cinq constats.
- Un panneau **« Évolutions depuis la précédente mise à jour »**.
- Un bloc **Contexte macroéconomique** (PIB par habitant, taux de change, ordre de grandeur mensuel).
- Les comparaisons avec les données de l'utilisateur, si des fichiers ont été importés.
- Des **pistes de recommandation** déterministes.

### Comment lire les cartes

Chaque carte affiche :

- le libellé métier ;
- la valeur et son unité ;
- l'année réellement utilisée ;
- la variation par rapport à l'année précédente, si elle existe ;
- un badge de provenance ;
- le bouton **Source et méthode** ;
- éventuellement un lien vers la première année disponible.

La valeur numérique est animée par un compteur progressif de 900 ms. Les valeurs composées (montants avec séparateur de milliers, textes) ne sont pas animées pour éviter d'afficher un nombre incomplet.

### Le graphique d'historique

La courbe ne relie que des observations réelles. Chaque point est une enquête. La ligne est tracée progressivement au chargement. Une note rappelle qu'aucune valeur n'est estimée entre deux points.

### La comparaison régionale

Les barres comparent la Tunisie à l'Algérie, l'Égypte, la Jordanie et le Maroc. Le pays sélectionné est mis en évidence. Les barres poussent de gauche à droite, l'une après l'autre.

### « À retenir »

Chaque constat est une phrase courte, accompagnée d'un lien **« Voir les données sources »** qui révèle les identifiants des preuves. Les constats ne sont pas générés librement : ils sont dérivés des faits et contrôlés.

### « Évolutions depuis la précédente mise à jour »

Ce panneau compare la version courante à la précédente. Il indique les valeurs avant/après, l'écart et l'état. S'il n'y a pas d'historique, il le dit simplement.

> **En clair :** cette page répond à « où en est le pays ? », puis propose deux portes : les inégalités et l'accès.

---

## 10.2 Inclusion et inégalités

**Objectif :** montrer qui utilise les services financiers et comment les écarts évoluent.

### Les quatre graphiques

| Graphique | Type | Question à laquelle il répond |
|---|---|---|
| **Du compte à l'usage formel** | Entonnoir | Quelle part des adultes détient un compte, paie numériquement, épargne formellement, emprunte formellement ? |
| **Formel vs tout moyen confondu** | Barres | Combien d'adultes utilisent une forme formelle par rapport à toutes les formes ? |
| **Détention d'un compte par groupe** | Dumbbell | Où se situent les femmes/hommes, pauvres/riches, peu/plus éduqués, inactifs/actifs, ruraux/urbains ? |
| **Évolution des écarts 2021 → 2024** | Écarts | Les inégalités se réduisent-elles ou se creusent-elles ? |

### L'entonnoir n'est pas un taux de conversion

Les questions Findex sont posées séparément. Une personne peut détenir un compte sans payer numériquement, ou épargner sans emprunter. La baisse entre les étapes n'est donc pas un pourcentage de personnes qui « passent » d'une étape à l'autre. L'interface le dit explicitement pour éviter une erreur d'interprétation fréquente.

### Le graphique dumbbell

Chaque ligne représente un groupe. Deux points indiquent les valeurs comparées, reliés par un segment. L'écart est affiché en points. Les libellés sont placés pour rester lisibles même lorsque les points sont proches.

### Les écarts illustratifs (Tunisie 2024)

| Groupe | Écart | Lecture |
|---|---:|---|
| Femmes / hommes | 23,0 points | 26,6 % contre 49,6 % |
| 40 % les plus pauvres / 60 % les plus riches | 27,0 points | 21,7 % contre 48,6 % |
| Primaire ou moins / secondaire ou plus | 17,2 points | 28,6 % contre 45,8 % |
| Hors population active / population active | 45,6 points | 16,6 % contre 62,1 % |
| Rural / urbain | 16,6 points | 30,2 % contre 46,7 % |

### Le message de prudence

Un bandeau et une note rappellent que ces écarts décrivent des groupes observés, pas des effets mesurés. Les sous-groupes ne représentent pas les mêmes personnes. Une différence de 23 points n'autorise pas à dire que le genre « cause » une exclusion de 23 points.

> **En clair :** cette page ne dit pas seulement « il y a des inégalités ». Elle montre lesquelles, de combien, et dans quel sens elles évoluent.

---

## 10.3 Accès et crédit

**Objectif :** décrire l'infrastructure financière et l'équilibre entre l'offre et la demande.

### Les six cartes

| Carte | Valeur illustrative 2024 | Lecture |
|---|---:|---|
| Distributeurs automatiques | 35,44 / 100 000 adultes | Disponibilité des espèces |
| Agences bancaires | 22,37 / 100 000 adultes | Densité du réseau |
| Déposants | 1 063,3 / 1 000 adultes | Base de déposants (2018) |
| Emprunteurs | 253,7 / 1 000 adultes | Base d'emprunteurs |
| Crédits bancaires | 67,8 % du PIB | Poids du crédit dans l'économie |
| Dépôts bancaires | 71,7 % du PIB | Poids de l'épargne bancaire |

### Les trois graphiques

1. **Réseau physique (2015–2024)** : évolution des agences et des distributeurs.
2. **Distributeurs pour 100 000 adultes — comparaison régionale** : situation du pays par rapport aux pairs.
3. **Offre et demande, base 100 en 2017** : évolution relative de l'infrastructure et de l'usage.

### Pourquoi les années diffèrent

Les séries FAS ne sont pas toutes disponibles jusqu'en 2024. Les déposants s'arrêtent en 2018 dans les données actuelles. L'interface affiche l'année de chaque valeur et ne recopie pas une valeur ancienne en la faisant passer pour récente.

> **En clair :** cette page montre le « réseau » (agences, distributeurs) et le « usage » (déposants, emprunteurs, crédits). Un réseau dense ne garantit pas un usage élevé.

---

## 10.4 Pourquoi l'exclusion ?

**Objectif :** exposer les obstacles déclarés et les écarts entre villes et campagnes, sans prétendre expliquer les causes.

### Les cartes

Deux cartes comparent la détention d'un compte en milieu urbain et rural : **46,7 %** contre **30,2 %** pour la Tunisie 2024, soit un écart de 16,6 points.

### La carte des obstacles

Six obstacles sont prévus : trop éloigné, trop cher, documents manquants, fonds insuffisants, un proche en a déjà un, manque de confiance.

Dans l'état actuel des données, ces colonnes détaillées ne sont pas encore chargées dans la base. La carte affiche donc **« En attente de données »** plutôt qu'une valeur vide ou inventée. Une note explique que les obstacles seront affichés dès que la source sera chargée.

### Le panneau d'analyse

Le panneau **« Pourquoi ces écarts ? »** est organisé en trois colonnes :

1. **Ce que montrent les données** : les faits observés.
2. **Comment le lire** : l'interprétation prudente.
3. **Piste à explorer** : une hypothèse à tester, pas une cause prouvée.

Un badge indique **« Lien observé, pas une cause »**.

### Le contexte vérifié

Des cartes de contexte rappellent les références disponibles. Les éléments qui ne proviennent pas de la base (SMIG, pauvreté INS) ont été retirés de l'interface pour ne pas mélanger des sources hétérogènes.

### Ask Finova intégré

Un encadré propose des questions suggérées et rappelle les règles de réponse. Il ouvre le chat docké.

> **En clair :** cette page est la plus prudente. Elle montre ce que les gens déclarent, mais refuse de transformer une corrélation en explication.

---

## 10.5 Sources et qualité

**Objectif :** rendre le pipeline visible et vérifiable.

### La frise des agents

Une timeline affiche les étapes du dernier run : collecte, snapshot, profilage, qualité, ETL, calcul des indicateurs, audit, mise à jour du tableau de bord. Chaque étape a un statut (réussi, en cours, en attente, échec) et une courte description.

### Le schéma du pipeline

Le panneau **« Du fichier source au tableau de bord »** présente deux routes :

- **Étape 1 — Fiabiliser les données** : collecte → version → profilage → qualité → intégration.
- **Étape 2 — Calculer, expliquer, publier** : indicateurs → analyse → tableau de bord.

Une branche montre ce qui se passe en cas d'anomalie : arrêt de la mise à jour, aucune donnée publiée.

### Le contrôle qualité

Un tableau indique, par source : lignes, colonnes, score, résultat. Le seuil requis est affiché. Un résumé donne le nombre de problèmes critiques.

### La base de données

Un panneau indique le nombre de faits, le nombre de pays, la répartition par source, la signature et le nom du fichier. Le badge **« consultation seule »** rappelle que l'interface ne modifie pas la base.

### Les sources utilisées

Un tableau détaillé affiche, pour chaque source : fichier, lignes, signature, date de collecte et lignes écartées avec la raison.

### L'historique

Deux panneaux listent les générations du tableau de bord et les versions archivées. Un compteur indique combien de contrôles de cohérence ont réussi. Les détails techniques sont repliés pour ne pas encombrer la lecture.

> **En clair :** cette page répond à « pourquoi puis-je croire ce chiffre ? ». Elle montre le chemin, les contrôles et les signatures.

---

## 10.6 Mes données

**Objectif :** permettre à un utilisateur d'ajouter ses propres chiffres sans contaminer les données officielles.

### La page d'accueil

La page liste les sources importées sous forme de cartes :

- nom de la source et fichier ;
- statut : incluse, exclue avec raison, en attente ;
- indicateurs et unités ;
- nombre de lignes, plage d'années, pays ;
- score qualité ;
- actions : voir les données, remplacer le fichier, supprimer.

Le bouton **Ajouter un fichier** ouvre un assistant en cinq étapes.

### L'assistant en cinq étapes

| Étape | Ce que fait l'application | Ce que fait l'utilisateur |
|---|---|---|
| **1. Fichier** | Vérifie l'extension, le type, la taille maximale | Dépose un CSV |
| **2. Structure** | Détecte l'encodage, le séparateur, la ligne d'en-tête, la disposition, la virgule décimale | Confirme ou corrige |
| **3. Indicateurs** | Propose les rôles de colonnes (pays, année, indicateur, valeur), demande l'unité | Nomme les indicateurs, choisit l'unité |
| **4. Vérification** | Produit un dry-run : cellules retenues, pays inconnus, années, doublons, aperçu, contrôle qualité | Vérifie le rapport |
| **5. Confirmation** | Enregistre le mapping, copie le fichier, lance le recalcul en arrière-plan | Confirme |

### Les trois dispositions reconnues

| Disposition | Exemple d'en-tête |
|---|---|
| **Long** | `Pays;Année;Indicateur;Valeur` |
| **Années en colonnes** | `iso3,indicator,2021,2022,2023` |
| **Indicateurs en colonnes** | `country,year,bank_agents,atm_count` |

### Les règles de détection

- L'encodage est vérifié sur tout le fichier.
- Le séparateur peut être `;`, `,`, une tabulation ou `|`.
- Une ligne de titre au-dessus de l'en-tête est ignorée.
- La virgule décimale et les milliers en groupes de trois sont reconnus.
- Les pays sont reconnus par code ISO3 ou par nom, avec une correspondance exacte seulement.
- Un pays inconnu ou un agrégat est listé et exclu, jamais deviné.
- L'unité n'est jamais devinée : elle est demandée pour chaque indicateur.
- Une cellule vide reste absente, jamais remplacée par zéro.
- Un mapping confirmé est réutilisé pour un fichier aux mêmes colonnes.

### Le suivi du recalcul

Après confirmation, un écran de progression affiche les huit étapes : collecte, snapshot, profilage, qualité, chargement, calcul, audit, mise à jour du tableau de bord. L'utilisateur peut quitter la page : le job continue et peut être repris.

### La consultation des données

La vue **Voir les données** affiche les séries importées, les indicateurs, les pays et les années. Les valeurs sont marquées **« Vos données »**.

### La suppression

La suppression retire les données de la base et relance le recalcul. La copie du fichier est conservée. Une confirmation explicite est demandée.

> **En clair :** vos chiffres restent vos chiffres. Ils sont visibles à côté des chiffres officiels, mais jamais confondus avec eux.

---

## 10.7 Audit et confiance

**Objectif :** montrer comment chaque valeur publiée est contrôlée et pouvoir remonter à la source.

### Le verdict

Un bandeau affiche le verdict global : **Audit réussi**, **réussi avec avertissements** ou **en échec**, avec le nombre de contrôles réussis, d'avertissements et d'échecs. Il rappelle le run, le snapshot, la version du catalogue et la date.

### La publication

Un panneau compte les valeurs approuvées, approuvées avec réserve et bloquées. Les motifs de réserve sont listés avec le nombre de lignes concernées.

### Les contrôles

Un tableau liste chaque contrôle : identifiant, nom, ce qui est vérifié, résultat, nombre de lignes concernées. Un contrôle peut être filtré sur les sources utilisateur ; un badge le signale.

### L'audit des constats

Chaque constat est accepté, rejeté ou non auditable. Les valeurs citées sont affichées. Un constat rejeté n'est pas publié dans le rapport.

### « Comment un chiffre est vérifié »

L'utilisateur choisit un indicateur, un pays et une année. L'application affiche un tracé en six étapes :

1. valeur publiée ;
2. sources lues (fichier, colonne, texte brut) ;
3. formule et transformation ;
4. valeur recalculée ;
5. contrôles touchant la valeur ;
6. statut de publication.

C'est la vue la plus technique de l'application, mais elle est présentée comme une chaîne lisible, pas comme un journal de logs.

### Le test par injection de fautes

Un tableau liste les fautes introduites, le contrôle attendu, la détection et le verdict obtenu. Il permet de vérifier que l'audit ne se contente pas d'approuver.

### Le rapport PDF

Le bouton **PDF** télécharge le rapport d'évaluation et d'explicabilité, construit à la demande depuis l'état courant. Aucun fichier n'est écrit sur le disque.

> **En clair :** cette page est la garantie de FinOVA. Elle ne demande pas de faire confiance : elle montre les contrôles et la traçabilité.

---

## 10.8 Utilisateurs (administrateur)

**Objectif :** gérer les accès sans inscription publique.

La page permet de :

- inviter un utilisateur par email, avec un nom et un rôle ;
- voir la liste des comptes, leur rôle, leur statut et leur dernière connexion ;
- renvoyer une invitation ;
- changer un rôle ;
- désactiver ou réactiver un compte ;
- protéger le dernier administrateur actif.

Les statuts sont : **Invitation en attente**, **Actif**, **Désactivé**.

> **En clair :** l'accès est contrôlé à l'entrée. Chaque compte a un rôle et peut être révoqué.

---

# 11. Ask Finova

## 11.1 Le principe

Ask Finova est un assistant de lecture, pas un calculateur. Il répond aux questions sur le pays et l'année sélectionnés en utilisant uniquement les faits du tableau de bord.

Le routage des intentions est **déterministe** : une liste fermée de questions reconnues. Un modèle de langage peut reformuler la réponse, mais il ne choisit pas les chiffres et ne fait pas de requête SQL libre.

## 11.2 Ce que l'assistant peut faire

- Donner la valeur d'un indicateur pour le pays et l'année.
- Comparer deux pays ou deux années.
- Expliquer un écart.
- Décrire l'évolution d'un indicateur.
- Répondre à partir des données importées, en le signalant.

## 11.3 Les garde-fous

| Garde-fou | Effet |
|---|---|
| Faits uniquement | Chaque nombre de la réponse doit exister dans les faits |
| Vérification numérique | Les nombres sont comparés aux valeurs autorisées |
| Pas de SQL libre | Aucune requête arbitraire |
| Pas d'appel externe | Aucune donnée envoyée à un service tiers pour calculer |
| Périmètre | Pays et année de la vue courante, sauf relance explicite |
| Données utilisateur | Réponse marquée « Vos données », jamais mélangée |
| Mode simple | Sans LLM, les gabarits déterministes répondent |

## 11.4 L'interface

Le bouton flottant **Ask Finova** ouvre un dock latéral. On y trouve :

- l'historique de la session (conservé dans le navigateur) ;
- des suggestions de questions ;
- les réponses avec les faits cités, le pays, l'année et le mode ;
- un badge **« Chiffres vérifiés »** ou **« Chiffres à vérifier »** ;
- les règles de réponse rappelées en bas.

Les réponses peuvent proposer des relances. Une question sur un autre pays est traitée comme un changement de périmètre explicite, avec un badge indiquant le pays réellement concerné.

> **En clair :** l'assistant ne « sait » rien par lui-même. Il lit les chiffres affichés et répond avec eux. S'il ne peut pas vérifier un nombre, il le dit.

---

# 12. Les rapports PDF

## 12.1 Deux rapports

| Rapport | Point d'entrée | Contenu |
|---|---|---|
| **Évaluation et explicabilité** | Page Audit et confiance | Verdict, contrôles, publication, constats, test par injection de fautes |
| **Constats et pistes de recommandation** | Vue d'ensemble | Constats de la sélection, preuves, recommandations déterministes, annexe optionnelle |

## 12.2 Le rapport de constats

Il est construit à la demande depuis le contrat courant. Il contient :

- la page de couverture avec le pays et l'année ;
- les constats, classés par page ;
- les preuves citées ;
- les recommandations, séparées des constats ;
- une annexe **« Vos données »** si l'utilisateur la demande.

L'annexe est explicitement séparée : les données importées ne sont jamais présentées comme des constats officiels.

## 12.3 Le rapport d'évaluation

Il reprend le rapport d'audit : verdict, contrôles, statuts de publication, constats acceptés ou rejetés, résultats du test par injection de fautes. Il est daté et rattaché au snapshot.

> **En clair :** les PDF ne sont pas des exports figés. Ils sont reconstruits à partir de l'état courant, avec les mêmes garde-fous que l'interface.

---

# 13. Le design et les animations

## 13.1 L'intention

FinOVA devait éviter deux écueils : le tableau de bord administratif froid et la démonstration gadget. Le parti pris est celui d'un **document financier haut de gamme** : fond clair bleuté, marine profond, or discret, cartes nettes, typographie lisible.

## 13.2 Les fondations

| Élément | Choix |
|---|---|
| Couleur principale | Marine `#0c2242` |
| Couleur d'accent | Or `#e8a800`, or clair `#f6c945` |
| Fond | Dégradé bleu très clair, halos radiaux |
| Cartes | Blanc, rayons 18 px, ombres douces, liseré supérieur |
| Typographie | Inter, titres serrés, chiffres tabulaires |
| Bordures | Bleu-gris clair, contraste renforcé au survol |
| Badges | Couleurs par provenance, texte court |

La feuille de style compte plus de **4 000 lignes**. Elle centralise les variables, les composants, les états, le responsive et les animations.

## 13.3 Les composants

- **Cartes KPI** : libellé, valeur, unité, année, delta, provenance, action.
- **Panneaux** : titre, sous-titre, contenu, actions.
- **Badges** : provenance, statut, réserve, donnée utilisateur.
- **Tableaux** : en-têtes discrets, lignes lisibles, colonnes compactes.
- **Graphiques SVG** : courbes, barres, entonnoir, dumbbell, écarts, heatmap.
- **Fiches** : `WhySheet`, preuves, détails techniques repliés.
- **Chat** : dock, bulles, suggestions, indicateur de saisie.
- **Formulaires** : champs avec icône, messages d'erreur, états de chargement.

## 13.4 Les animations

| Animation | Durée | Effet |
|---|---:|---|
| Apparition des cartes | 550 ms | Translation et léger zoom, décalage par carte |
| Entrée des panneaux | 550 ms | Translation verticale douce |
| Navigation | 450 ms | Glissement depuis la gauche, décalage par entrée |
| Tracé des courbes | 1 500 ms | `stroke-dashoffset` de 1 à 0 |
| Croissance des barres | 900 ms | Échelle horizontale depuis la gauche, décalage de 70 ms |
| Entonnoir | 900 ms | Révélation progressive |
| Compteur KPI | 900 ms | Interpolation ease-out, format français |
| Bouton Ask Finova | 3 200 ms | Halo pulsé |
| Ouverture du dock | 300 ms | Glissement et fondu |

Les animations utilisent `animation-fill-mode: backwards` pour ne pas laisser de transformation persistante. C'est important : une transformation persistante sur un conteneur casserait le positionnement des fenêtres modales `position: fixed`.

## 13.5 L'accessibilité

- Toutes les animations décoratives sont désactivées si l'utilisateur active **« Réduire les animations »** (`prefers-reduced-motion`).
- Les compteurs affichent immédiatement la valeur finale dans ce mode.
- Les graphiques ont des libellés, des unités et des textes de remplacement.
- Les boutons ont des libellés explicites, les champs ont des étiquettes.
- Les contrastes respectent la lecture sur écran clair.
- Le dock se ferme avec Échap ou le bouton dédié.

> **En clair :** le design doit inspirer confiance sans intimider. Les animations donnent du rythme, mais elles ne retardent jamais la lecture et peuvent être coupées.

---

# 14. L'API et la sécurité

## 14.1 Les points d'entrée

### Authentification

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/api/auth/login` | Connexion |
| POST | `/api/auth/refresh` | Rotation de session |
| POST | `/api/auth/logout` | Déconnexion |
| GET | `/api/auth/me` | Profil courant |
| POST | `/api/auth/forgot-password` | Demande de réinitialisation |
| POST | `/api/auth/reset-password` | Réinitialisation |
| POST | `/api/auth/activate` | Activation d'un compte invité |
| GET | `/api/auth/admin/users` | Liste des comptes (admin) |
| POST | `/api/auth/admin/users` | Invitation (admin) |
| POST | `/api/auth/admin/users/{id}/resend-invitation` | Renvoi (admin) |
| PATCH | `/api/auth/admin/users/{id}` | Rôle ou statut (admin) |

### Données et tableau de bord

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/health` | Santé du service |
| GET | `/api/spec?iso3=TUN&year=2024` | Contrat de tableau de bord |
| GET | `/api/runs` | Historique des runs |
| POST | `/api/ask` | Question Ask Finova |
| GET | `/api/recommendations` | Pistes déterministes |

### Sources utilisateur

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/api/sources/detect` | Détection d'un CSV |
| POST | `/api/sources/dry-run` | Simulation |
| POST | `/api/sources/confirm` | Enregistrement |
| GET | `/api/sources` | Liste des sources |
| GET | `/api/sources/{name}/data` | Données d'une source |
| GET | `/api/sources/jobs/{job_id}` | Suivi d'un recalcul |
| GET | `/api/sources/comparable-kpis` | Indicateurs comparables |
| GET | `/api/sources/comparisons` | Comparaisons |
| DELETE | `/api/sources/{name}` | Suppression |

### Pipeline, audit et rapports

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/pipeline/agents` | Frise des agents |
| POST | `/api/pipeline/demo` | Relance de démonstration |
| GET | `/api/audit/summary` | Synthèse d'audit |
| GET | `/api/audit/checks` | Contrôles |
| GET | `/api/audit/explain` | Explication d'une valeur |
| GET | `/api/audit/options` | Options de filtre |
| GET | `/api/reports/evaluation.pdf` | PDF d'évaluation |
| GET | `/api/reports/insights.pdf` | PDF de constats |

Toutes les routes métier sont protégées par une session. Les routes d'administration exigent le rôle administrateur.

## 14.2 La politique de sécurité du contenu

L'application applique une CSP stricte :

- scripts et styles uniquement depuis le site ;
- polices depuis Google Fonts ;
- images locales ou `data:` ;
- médias locaux ;
- connexions uniquement vers le site ;
- objets désactivés ;
- cadre interdit (`frame-ancestors 'none'`).

Les pages de documentation FastAPI sont exemptées pour permettre leur fonctionnement en développement.

## 14.3 Les autres protections

- CORS limité aux origines de développement `127.0.0.1:5173` et `localhost:5173`.
- En-tête `X-Content-Type-Options: nosniff`.
- Aucun secret dans le code ni dans le dépôt : les identifiants SMTP et le secret JWT viennent de l'environnement ou d'un fichier local protégé.
- Les mots de passe ne sont jamais journalisés.
- Les échecs de connexion sont journalisés sans révéler si l'adresse existe.
- Les liens d'invitation et de réinitialisation sont à usage unique et hachés en base.

## 14.4 Ce que l'API ne fait pas

- Elle ne calcule pas de valeur à la volée pour l'interface : elle sert un contrat déterministe.
- Elle n'exécute pas de SQL fourni par l'utilisateur.
- Elle n'appelle pas de service externe pour répondre à une question.
- Elle ne mélange pas les sources utilisateur et les sources officielles.
- Elle ne publie pas une valeur bloquée par l'audit.

---

# 15. Exploiter l'application

## 15.1 Prérequis

- Python et l'environnement virtuel du projet ;
- Node.js et npm pour construire l'interface ;
- les fichiers de données dans `data/raw/` ;
- la base préparée dans `data/processed/warehouse.duckdb`.

## 15.2 Construire l'interface

```bash
cd dashboard_app/web
npm ci
npm run build
```

Le build vérifie TypeScript puis produit `dashboard_app/web/dist/`.

## 15.3 Lancer le serveur

```bash
python -m uvicorn dashboard_app.api.app:app --host 127.0.0.1 --port 8000
```

L'application est alors disponible sur `http://127.0.0.1:8000`. La page `/login` est publique ; les données sont protégées.

## 15.4 Créer le premier administrateur

```bash
python -m dashboard_app.auth.cli create-admin --email admin@organisation.tn --name "Administrateur"
```

L'interface d'administration permet ensuite d'inviter les autres comptes.

## 15.5 Variables d'environnement utiles

| Variable | Rôle | Défaut |
|---|---|---|
| `BIFLOW_AUTH_DB` | Base SQLite d'authentification | `data/auth/auth.sqlite3` |
| `BIFLOW_AUTH_SECRET` | Secret JWT | clé locale `data/auth/jwt.key` |
| `BIFLOW_PUBLIC_URL` | URL utilisée dans les liens email | `http://127.0.0.1:8000` |
| `BIFLOW_ACCESS_TOKEN_MINUTES` | Durée du jeton d'accès | 15 |
| `BIFLOW_REFRESH_DAYS` | Durée de la session | 30 |
| `BIFLOW_RESET_MINUTES` | Validité du lien de réinitialisation | 15 |
| `BIFLOW_INVITE_HOURS` | Validité de l'invitation | 168 |
| `BIFLOW_COOKIE_SECURE` | Cookie `Secure` (HTTPS) | `false` en local |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Envoi des emails | — |

## 15.6 Recalculer les données

```bash
python main.py run --from quality --no-llm
```

Cette commande reconstruit la base et la vue publiée sans appeler de modèle de langage. Elle est utile après une correction de mapping ou un changement de source.

## 15.7 Ajouter un fichier utilisateur

```bash
python main.py add-source --file mon_fichier.csv --name ma_source --dry-run
python main.py add-source --file mon_fichier.csv --name ma_source
```

Le parcours est aussi disponible dans la page **Mes données**.

---

# 16. Ce qui a été vérifié

## 16.1 Build et service

- Le build TypeScript et Vite passe.
- Les fichiers produits sont `index-Dfs3fQvX.css` et `index-PwQbbH-B.js`.
- Le serveur répond `200` sur `/login`.
- L'interface construite est servie par l'API.
- Les pages de secours SPA (`/login`, `/forgot-password`, `/reset-password`, `/activate`, `/admin/users`) sont accessibles.

## 16.2 Interface

- La page de connexion a été contrôlée en capture : vidéos, logo, carte, champs.
- Le tableau de bord a été contrôlé à 1440 px : alignement des cartes, tracé de la courbe, révélation de l'entonnoir.
- Les états intermédiaires d'animation ont été vérifiés.
- Le mode « réduire les animations » est pris en charge.
- Les composants fixes (fiche Source et méthode, dock) ne sont pas piégés par les transformations d'animation.

## 16.3 Sécurité et emails

- Le parcours de réinitialisation a été testé avec un envoi Gmail réel.
- Les liens sont à usage unique et expirent.
- Les sessions sont révoquées après réinitialisation.
- Les routes métier refusent une requête sans session.
- Les en-têtes CSP et `nosniff` sont appliqués.

## 16.4 Tests

Le dépôt contient **68 fichiers de tests** couvrant notamment :

- la collecte, le profilage, la qualité et l'ETL ;
- le catalogue, les calculs et les valeurs ;
- l'audit, les explications et l'évaluation ;
- les sources utilisateur, le mapping et les limites ;
- l'API, l'authentification et les PDF ;
- le contrat de tableau de bord et son cache ;
- Ask Finova et les recommandations.

Un test préexistant dépend d'un fichier d'exemple absent (`docs/examples/banque_fictive_exemple.csv`) ; il est sans lien avec l'interface. Les tests ciblés sur l'authentification, l'API, les PDF et le tableau de bord ont été exécutés pendant la préparation.

## 16.5 Rapport

- Le PDF de ce rapport a été généré et contrôlé page par page.
- Le Markdown source est conservé à côté du PDF pour permettre les mises à jour.

---

# 17. Limites et prochaines étapes

## 17.1 Limites actuelles

| Limite | Effet | Piste |
|---|---|---|
| Obstacles détaillés non chargés | Carte des obstacles en attente | Intégrer les colonnes Findex `fin11a`–`fin11f` |
| Déposants jusqu'en 2018 | Une carte plus ancienne que les autres | Le signaler, chercher une source plus récente |
| Vagues d'enquête inégales | Comparaisons annuelles limitées | Afficher les vagues, éviter les fausses continuités |
| Données utilisateur non auditées | Elles ne prouvent rien officiellement | Les garder séparées et étiquetées |
| Pas de limitation de débit sur la connexion | Risque de force brute en exposition publique | Ajouter un throttle et un verrouillage progressif |
| Cookie non `Secure` en local | Normal en HTTP local | Activer `BIFLOW_COOKIE_SECURE` derrière HTTPS |
| Interface pensée pour bureau | Usage mobile moins confortable | Adapter les tableaux et le dock |
| LLM optionnel | Dépend de la configuration | Le mode simple reste disponible |

## 17.2 Prochaines étapes proposées

1. Charger les obstacles déclarés et activer la carte.
2. Ajouter une limitation de débit sur l'authentification.
3. Renforcer l'accessibilité mobile et les tests sur petits écrans.
4. Ajouter un mode comparaison multi-pays explicite.
5. Documenter les sources de chaque indicateur dans une page publique.
6. Mettre en place un déploiement HTTPS avec cookies sécurisés.

---

# 18. Glossaire

| Terme | Définition |
|---|---|
| **Adulte** | Personne de 15 ans et plus, selon la définition Findex |
| **Findex** | Enquête mondiale de la Banque mondiale sur l'inclusion financière |
| **FAS** | Financial Access Survey du FMI |
| **WDI** | World Development Indicators de la Banque mondiale |
| **Snapshot** | Copie horodatée et signée des fichiers sources |
| **Run** | Une exécution complète du pipeline |
| **ETL** | Extraction, transformation, chargement |
| **KPI** | Indicateur clé de performance ; dans FinOVA, un indicateur métier |
| **Point de pourcentage** | Différence arithmétique entre deux pourcentages |
| **Dumbbell** | Graphique à deux points reliés, utilisé pour comparer deux groupes |
| **Entonnoir** | Graphique en étapes décroissantes ; ici, les étapes ne sont pas un parcours individuel |
| **XAI** | Explication d'un constat, en trois temps : faits, lecture, hypothèse |
| **Audit** | Contrôle indépendant des valeurs et de leur traçabilité |
| **Publication** | Statut final d'une valeur : approuvée, avec réserve ou bloquée |
| **Bruit d'enquête** | Variation trop faible pour être interprétée comme un vrai changement |

---

# 19. Annexes

## Annexe A — Carte des fichiers

| Chemin | Rôle |
|---|---|
| `dashboard_app/api/app.py` | Application FastAPI, routes principales, CSP, cache |
| `dashboard_app/api/audit.py` | API d'audit |
| `dashboard_app/api/sources.py` | API des sources utilisateur |
| `dashboard_app/api/pipeline.py` | API de la frise des agents |
| `dashboard_app/api/reports.py` | Recommandations et PDF |
| `dashboard_app/api/pdf_reports.py` | Construction des PDF |
| `dashboard_app/auth/` | Authentification, sessions, emails, CLI |
| `dashboard_app/web/src/App.tsx` | Coque, navigation, sélecteurs, chat |
| `dashboard_app/web/src/pages.tsx` | Composition des pages métier |
| `dashboard_app/web/src/ui.tsx` | Cartes, fiches, constats, pipeline, chat |
| `dashboard_app/web/src/charts.tsx` | Graphiques SVG |
| `dashboard_app/web/src/sources.tsx` | Page Mes données et assistant |
| `dashboard_app/web/src/audit.tsx` | Page Audit et confiance |
| `dashboard_app/web/src/auth_pages.tsx` | Connexion, mot de passe, administration |
| `dashboard_app/web/src/styles.css` | Design system et animations |
| `dashboard_app/web/src/copy.ts` | Traductions et formulations non expertes |
| `dashboard_app/public/data/finova.json` | Contrat publié |
| `src/biflow/tools/dashboard_spec.py` | Modèles et validation du contrat |
| `src/biflow/tools/warehouse_reader.py` | Lecture read-only de la base |
| `config/kpi_catalog.v1.yaml` | Catalogue des indicateurs |
| `config/reference/finova_reference.yaml` | Références statiques |

## Annexe B — Clés de configuration

| Clé | Rôle |
|---|---|
| `countries.name_to_iso3` | Alias de noms de pays |
| `uploads.dir` | Dossier des fichiers utilisateur |
| `uploads.mappings_dir` | Mappings confirmés |
| `uploads.max_file_mb` | Taille maximale d'un fichier |
| `dashboard.spec_output` | Contrat publié |
| `dashboard.history_dir` | Historique des versions |
| `dashboard.reference_path` | Références |
| `paths.processed` | Base DuckDB |
| `paths.quality` | Rapport qualité |
| `paths.audit` | Rapport d'audit |
| `paths.reports` | Rapports de run |
| `llm.routing.*` | Routage des modèles, jamais pour les calculs |

## Annexe C — Exemples de fichiers utilisateur

### Format long

```csv
Pays;Année;Indicateur;Valeur
Tunisie;2024;Clients microfinance (milliers);1 230,75
Maroc;2024;Clients microfinance (milliers);2 104,0
```

### Années en colonnes

```csv
iso3,indicator,2021,2022,2023
TUN,mobile_money_users_pct,12.5,14.0,15.2
MAR,mobile_money_users_pct,9.1,,10.3
```

### Indicateurs en colonnes

```csv
country,year,bank_agents,atm_count
Tunisia,2023,1200,2100
```

---

## Conclusion

FinOVA n'est pas un tableau de bord de plus. C'est une chaîne de confiance : des sources publiques, un pipeline contrôlé, un audit indépendant, une interface qui explique, et des garde-fous qui empêchent les chiffres inventés.

La promesse tient en trois phrases :

1. **Chaque chiffre a une source.**
2. **Chaque limite est visible.**
3. **Chaque utilisateur peut comprendre sans être spécialiste.**

C'est cette combinaison — rigueur des données, prudence du discours, clarté de l'interface — qui a été préparée et qui est aujourd'hui livrée.

---

*Rapport FinOVA — version 1.0 — 6 novembre 2026.*
