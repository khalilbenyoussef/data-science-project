// Traductions de l'interface (français → anglais / arabe) et lecture localisée
// des phrases produites par le pipeline analytique. Aucun chiffre n'est recalculé :
// les motifs ne font que réordonner et traduire les fragments déjà publiés.
import { getLang, type Lang } from "./preferences";

export type { Lang };

const EN: Record<string, string> = {
  // ---------------------------------------------------------------- navigation
  "Vue d'ensemble": "Overview",
  "Inclusion et inégalités": "Inclusion and inequalities",
  "Accès et crédit": "Access and credit",
  "Pourquoi l'exclusion ?": "Why exclusion?",
  "Sources et qualité": "Sources and quality",
  "Mes données": "My data",
  "Audit et confiance": "Audit and trust",
  "Utilisateurs": "Users",
  "Administrateur": "Administrator",
  "Utilisateur": "User",
  "Déconnexion": "Sign out",
  "Pays": "Country",
  "Année": "Year",
  "enquête": "survey",
  "Langue": "Language",
  "Thème": "Theme",
  "Clair": "Light",
  "Sombre": "Dark",
  "Passer en mode sombre": "Switch to dark mode",
  "Passer en mode clair": "Switch to light mode",
  "Choisir la langue": "Choose language",
  "Choisir le thème": "Choose theme",
  "Ouvrir Ask Finova": "Open Ask Finova",
  "Fermer": "Close",
  "Réessayer": "Try again",
  "Retour à la connexion": "Back to sign in",
  "Se connecter": "Sign in",
  "Combien d'adultes ont un compte en Tunisie ?": "How many adults have an account in Tunisia?",
  "Pourquoi l'écart femmes-hommes est-il élevé ?": "Why is the gender gap high?",
  "Les ATMs ont-ils augmenté depuis 2017 ?": "Have ATMs increased since 2017?",
  "Que dit la pauvreté rurale ?": "What do rural poverty figures say?",

  // ------------------------------------------------------------ pages / shell
  "FinOVA": "FinOVA",
  "Le tableau de bord est indisponible.": "The dashboard is unavailable.",
  "Tableau de bord indisponible": "Dashboard unavailable",
  "Les données n'ont pas pu être chargées pour le moment.":
    "The data could not be loaded right now.",
  "Détail technique": "Technical detail",
  "Vérifiez que le service tourne et que la base de données a bien été préparée.":
    "Check that the service is running and that the database has been prepared.",
  "Vérification de votre session…": "Checking your session…",
  "Connexion indisponible": "Sign-in unavailable",
  "Préparation des données…": "Preparing the data…",
  "Préparation des chiffres pour {country} {year}… ({elapsed} s). La vue précédente reste affichée pendant le calcul, puis elle sera remplacée.":
    "Preparing figures for {country} {year}… ({elapsed} s). The previous view stays on screen during the calculation, then it will be replaced.",
  "La première ouverture de ce pays peut prendre 20 à 40 secondes.":
    "Opening this country for the first time can take 20 to 40 seconds.",
  "Toujours en cours ({elapsed} s) : les séries annuelles sont recalculées depuis la base, sans estimation.":
    "Still running ({elapsed} s): annual series are being rebuilt from the database, with no estimation.",
  "lecture de la base locale et vérification des sources.":
    "reading the local database and checking the sources.",
  "Années d'enquête Findex pour {country} : {years}. Les autres années reprennent la dernière enquête antérieure ; les indicateurs bancaires restent ceux de l'année.":
    "Findex survey years for {country}: {years}. Other years reuse the latest earlier survey; banking indicators remain those of the selected year.",
  "Pas d'enquête Findex en {year} : les chiffres viennent de l'enquête {used}.":
    "No Findex survey in {year}: figures come from the {used} survey.",
  "Cette vue a été préparée à la demande pour ce pays et cette année, à partir de la même base de données. Elle peut différer de la vue publiée par défaut.":
    "This view was prepared on request for this country and year from the same database. It may differ from the published default view.",
  "Mise à jour du {date}": "Updated {date}",
  "Aucune valeur inventée · {count} données sourcées":
    "No invented value · {count} sourced data points",
  "Page non disponible pour cette sélection":
    "Page unavailable for this selection",
  "Les données de cette page ne sont pas disponibles pour ce pays et cette année.":
    "This page's data is not available for this country and year.",

  // -------------------------------------------------------------------- meters
  "Chiffres clés": "Key figures",
  "Chaque chiffre peut être rattaché à sa source":
    "Every figure can be traced back to its source",
  "Année : {year}": "Year: {year}",
  "Année : {year} · dernière enquête": "Year: {year} · latest survey",
  "Source et méthode": "Source and method",
  "Pourquoi ?": "Why?",
  "Comprendre ce chiffre": "Understand this figure",
  "Comprendre cette donnée": "Understand this data point",
  "Comprendre ce graphique": "Understand this chart",
  "Ce que dit la valeur": "What the value says",
  "Lecture simple": "Plain-language reading",
  "À quoi sert ce chiffre": "What this figure is for",
  "Ce que le chiffre ne dit pas": "What the figure does not say",
  "Analyse expliquée": "Explained analysis",
  "Ce que montrent les données": "What the data shows",
  "Piste à explorer": "Area to explore",
  "Demander à Finova": "Ask Finova",
  "Cette explication utilise uniquement les chiffres publiés ; elle ne recalcule rien.":
    "This explanation uses only published figures; it recalculates nothing.",
  "Aucun facteur explicatif n'est déduit : l'analyse relie seulement des observations issues des mêmes données.":
    "No explanatory factor is inferred: the analysis only links observations from the same data.",
  "Lecture des données": "Reading the data",
  "Année de référence": "Reference year",
  "Année de référence : {year}": "Reference year: {year}",
  "Année : {year} · {provider}": "Year: {year} · {provider}",
  "Pourquoi ce chiffre est-il à ce niveau ?": "Why is this figure at this level?",
  "Pourquoi {label} est-il à ce niveau ?": "Why is {label} at this level?",
  "Pourquoi ce graphique évolue-t-il ainsi ?": "Why does this chart evolve this way?",
  "Que signifie {label} dans ce tableau de bord ?":
    "What does {label} mean in this dashboard?",
  "Ce chiffre n'est pas disponible pour cette sélection.":
    "This figure is not available for this selection.",
  "En {year}, {label} s'élève à {value}.": "In {year}, {label} stands at {value}.",
  "{label} : {value} en {year}.": "{label}: {value} in {year}.",
  "Évolution : {delta}.": "Change: {delta}.",
  "La valeur affichée est {value} pour l'année {year}.":
    "The displayed value is {value} for {year}.",
  "Entre {from} et {to}, {label} passe de {start} à {end}.":
    "Between {from} and {to}, {label} goes from {start} to {end}.",
  "La valeur la plus élevée est {value} ({label}).":
    "The highest value is {value} ({label}).",
  "La valeur la plus basse est {value} ({label}).":
    "The lowest value is {value} ({label}).",
  "{label} : {value}.": "{label}: {value}.",
  "L'écart le plus marqué concerne {group} : {value} points.":
    "The widest gap concerns {group}: {value} points.",
  "{label} : l'écart passe de {start} à {end} points entre {from} et {to}.":
    "{label}: the gap moves from {start} to {end} points between {from} and {to}.",
  "Le maximum observé est {value}, pour {label}.":
    "The highest observed value is {value}, for {label}.",
  "Ce que montre ce graphique": "What this chart shows",
  "Graphique sans donnée pour cette sélection.": "Chart with no data for this selection.",
  "Aucune précaution particulière n'est signalée pour ce graphique.":
    "No particular precaution is flagged for this chart.",
  "Source : {source}": "Source: {source}",
  "En attente de données": "Awaiting data",
  "Indisponible": "Unavailable",
  "À vérifier": "To review",
  " · à vérifier": " · to review",
  "Vos données": "Your data",
  "dont le contenu": "whose content",
  "année utilisée : {year} · {provider}": "year used: {year} · {provider}",
  "D'où vient ce chiffre ?": "Where does this figure come from?",
  "Ce que mesure l'indicateur": "What the indicator measures",
  "Source": "Source",
  "consulter la source": "view the source",
  "Périmètre": "Scope",
  "Fiabilité de la définition": "Definition reliability",
  "Année réellement utilisée": "Year actually used",
  "Repère de provenance": "Provenance marker",
  "Points à vérifier": "Points to review",
  "Aucun chiffre n'est recalculé dans l'interface : la valeur et l'année proviennent directement des données source.":
    "No figure is recalculated in the interface: the value and year come directly from the source data.",
  "Détails techniques (pour vérification)": "Technical details (for verification)",
  "Identifiant": "Identifier",
  "Définition d'origine": "Original definition",
  "Source d'origine": "Original source",
  "Filtre d'origine": "Original filter",
  "Statut d'origine": "Original status",
  "Valeur importée par l'utilisateur, hors chiffres officiels : BIFlow ne la vérifie pas":
    "Value imported by the user, outside official figures: not verified by BIFlow",

  // ------------------------------------------------------------ insights / XAI
  "À retenir": "Key takeaways",
  "Chaque constat renvoie aux chiffres utilisés":
    "Each insight points to the figures used",
  "Voir les données sources": "View source data",
  "Aucun constat pour cette page.": "No insight for this page.",
  "Analyse du constat": "Insight analysis",
  "Pourquoi ces écarts ?": "Why these gaps?",
  "Lien observé, pas une cause": "Observed link, not a cause",
  "1 · Ce que montrent les données": "1 · What the data shows",
  "2 · Comment le lire": "2 · How to read it",
  "3 · Piste à explorer": "3 · Area to explore",
  "Hypothèse à tester": "Hypothesis to test",
  "Ces écarts décrivent des groupes observés : ils ne prouvent pas un lien de cause à effet.":
    "These gaps describe observed groups: they do not prove a causal link.",

  // ---------------------------------------------------------------- changes
  "Évolutions depuis la précédente mise à jour":
    "Changes since the previous update",
  "Aucune mise à jour antérieure comparable : l'historique démarre avec cette version.":
    "No comparable earlier update: the history starts with this version.",
  "Aucun indicateur n'a changé depuis la mise à jour du {date}{rest}":
    "No indicator has changed since the {date} update{rest}",
  " : les {count} indicateurs suivis restent identiques.":
    ": all {count} tracked indicators remain identical.",
  "Les {count} autres indicateurs suivis sont restés identiques.":
    "The other {count} tracked indicators remained identical.",
  "Indicateur": "Indicator",
  "Avant": "Before",
  "Maintenant": "Now",
  "Écart": "Change",
  "État": "Status",

  // ----------------------------------------------------------------- notices
  "Précautions de lecture": "Reading precautions",
  "Ce qu'il faut savoir avant de citer ces chiffres.":
    "What to know before citing these figures.",
  "{count} remarque": "{count} note",
  "{count} remarques": "{count} notes",

  // ---------------------------------------------------------------- pipeline
  "Du fichier source au tableau de bord": "From source file to dashboard",
  "Chaque étape est contrôlée automatiquement avant la publication.":
    "Every step is checked automatically before publication.",
  "Qualité : {state}": "Quality: {state}",
  "validée": "passed",
  "à corriger": "to fix",
  "Étape 1 — Fiabiliser les données": "Step 1 — Make the data reliable",
  "Étape 2 — Calculer, expliquer, publier": "Step 2 — Calculate, explain, publish",
  "Validé": "Passed",
  "Anomalie": "Anomaly",
  "→ les données rejoignent la base centrale": "→ the data joins the central database",
  "→ arrêt de la mise à jour, aucune donnée publiée":
    "→ update stops, no data is published",
  "Contrôle qualité": "Quality control",
  "score {score} / {threshold} requis": "score {score} / {threshold} required",
  "Résultat": "Result",
  "Lignes": "Rows",
  "Colonnes": "Columns",
  "Score": "Score",
  "À corriger": "To fix",
  "Résultat global : {state} · {count} problème(s) critique(s).":
    "Overall result: {state} · {count} critical issue(s).",
  "Base de données": "Database",
  "consultation seule": "read-only",
  "Données enregistrées": "Stored data",
  "Pays couverts": "Countries covered",
  "Par source": "By source",
  "Signature": "Signature",
  "Fichier": "File",
  "Sources utilisées": "Sources used",
  "Signatures et dates de collecte réelles":
    "Real signatures and collection dates",
  "Collecté le": "Collected on",
  "Lignes écartées": "Discarded rows",
  "Dernière collecte": "Latest collection",
  "Date": "Date",
  "Période couverte": "Period covered",
  "Historique indisponible.": "History unavailable.",
  "Traitements appliqués": "Applied processing",
  "Historique des mises à jour": "Update history",
  "Générations du tableau de bord": "Dashboard generations",
  "{count} génération(s) enregistrée(s).": "{count} saved generation(s).",
  "Voir les identifiants": "View identifiers",
  "Versions archivées": "Archived versions",
  "aucune version archivée": "no archived version",
  "{count} version(s) archivée(s).": "{count} archived version(s).",
  "Voir les versions": "View versions",
  "Contrôles de cohérence": "Consistency checks",
  "{passed} contrôle(s) automatique(s) réussi(s) sur {total}.":
    "{passed} automatic check(s) passed out of {total}.",
  "Détails techniques des contrôles": "Technical check details",
  "{count} valeurs": "{count} values",
  "non fournie": "not provided",
  "écart": "mismatch",

  // -------------------------------------------------------------------- ask
  "Ask Finova": "Ask Finova",
  "Réponses fondées sur les chiffres du tableau de bord":
    "Answers grounded in the dashboard's figures",
  "Fermer le chat": "Close chat",
  "Posez une question sur le pays et l'année sélectionnés. Les réponses n'utilisent que les chiffres vérifiés du tableau de bord.":
    "Ask a question about the selected country and year. Answers only use the dashboard's verified figures.",
  "Chiffres vérifiés": "Figures verified",
  "Chiffres à vérifier": "Figures to review",
  "Vos données · ": "Your data · ",
  "Écrire une question…": "Write a question…",
  "Envoyer": "Send",
  "Ask Finova écrit…": "Ask Finova is writing…",
  "Réponse automatique": "Automatic answer",
  "Réponse indisponible : {detail}": "Answer unavailable: {detail}",
  "Impossible de charger le contrat Finova.": "The FinOVA data contract could not be loaded.",

  // ----------------------------------------------------------------- charts
  "Formule de calcul": "Calculation formula",
  "Aucune observation.": "No observation.",
  "Aucune valeur.": "No value.",
  "Aucune étape.": "No step.",
  "Aucun groupe.": "No group.",
  "Aucun écart.": "No gap.",
  "Chaque point est un chiffre publié{unit} ; aucune valeur estimée.":
    "Each point is a published figure{unit}; no value is estimated.",
  " (nombre pour 100 000 adultes)": " (number per 100,000 adults)",
  " (nombre pour 1 000 adultes)": " (number per 1,000 adults)",
  " (valeur en %)": " (value in %)",
  " (en pourcentage du PIB)": " (as a share of GDP)",
  " (en dinars par mois)": " (in dinars per month)",
  " (en dinars par dollar)": " (in dinars per dollar)",
  "Chaque question est posée séparément : la baisse d'une étape à l'autre ne signifie pas que les mêmes personnes quittent le système.":
    "Each question is asked separately: a drop from one step to the next does not mean the same people leave the system.",
  "Groupe le moins équipé": "Least served group",
  "Groupe le plus équipé": "Most served group",
  "écart {value}": "gap {value}",
  "{value} pts": "{value} pts",
  "{value} points": "{value} points",
  "{value} points par rapport à l'étape précédente":
    "{value} points versus the previous step",
  "Les raisons de ne pas avoir de compte ne sont mesurées que depuis l'enquête {year}.":
    "Reasons for not having an account have only been measured since the {year} survey.",
  "Aucune observation de ces raisons pour ce pays dans les enquêtes disponibles.":
    "No observation of these reasons for this country in the available surveys.",
  "Type de graphique inconnu : {kind}": "Unknown chart type: {kind}",
  "Groupe": "Group",
  "Valeur": "Value",
  "Année observée": "Observed year",
  "Évolution des écarts entre {from} et {to}":
    "Gap trends between {from} and {to}",
  "Chaque marche est une question Findex distincte, année {year}.":
    "Each step is a separate Findex question, year {year}.",
  "Chaque point est une observation observée; aucune interpolation.":
    "Each point is a published figure; no value is estimated.",
  "Écart en points de pourcentage, année observée {year}.":
    "Gap in percentage points, observed year {year}.",
  "Variation de l'écart entre deux groupes, en points de pourcentage.":
    "Change in the gap between two groups, in percentage points.",
  "mise à jour du {date}": "updated {date}",
  "Années observées : {years}": "Observed years: {years}",

  // ------------------------------------------------------------------- auth
  "Les chiffres d'abord.": "Figures first.",
  "Les sources toujours.": "Sources always.",
  "FinOVA rassemble des chiffres publics sur les services financiers — compte bancaire, épargne, crédit — les vérifie, puis vous les explique simplement.":
    "FinOVA brings together public figures on financial services — bank accounts, savings, credit — verifies them and explains them simply.",
  "Pas besoin d'être spécialiste : chaque page dit ce que le chiffre signifie, d'où il vient et ce qu'il ne permet pas de conclure.":
    "No expertise needed: every page says what the figure means, where it comes from and what it cannot prove.",
  "Connexion": "Sign in",
  "Accès réservé aux comptes autorisés.": "Access restricted to authorised accounts.",
  "Adresse email": "Email address",
  "Mot de passe": "Password",
  "Connexion…": "Signing in…",
  "S'authentifier": "Sign in",
  "Mot de passe oublié ?": "Forgot your password?",
  "Mot de passe oublié": "Forgot password",
  "Indiquez l'adresse associée à votre compte. Pour des raisons de sécurité, la réponse est toujours la même.":
    "Enter the address linked to your account. For security reasons, the response is always the same.",
  "Si un compte correspond à cette adresse, un lien de réinitialisation vient d'être envoyé. Il est valable 15 minutes et ne peut être utilisé qu'une seule fois.":
    "If an account matches this address, a reset link has just been sent. It is valid for 15 minutes and can only be used once.",
  "Pensez à vérifier les indésirables. Sans SMTP configuré, le lien est écrit par le serveur dans data/auth/outbox/.":
    "Remember to check your spam folder. Without SMTP configured, the link is written by the server in data/auth/outbox/.",
  "Envoi…": "Sending…",
  "Envoyer le lien": "Send the link",
  "Nouveau mot de passe": "New password",
  "Confirmer le mot de passe": "Confirm password",
  "10 caractères minimum, avec au moins une lettre et un chiffre.":
    "At least 10 characters, including at least one letter and one digit.",
  "Les deux mots de passe ne correspondent pas.": "The two passwords do not match.",
  "Lien invalide": "Invalid link",
  "Ce lien de réinitialisation est incomplet.": "This reset link is incomplete.",
  "Ouvrez le lien reçu par email, ou demandez-en un nouveau.":
    "Open the link you received by email, or request a new one.",
  "Demander un nouveau lien": "Request a new link",
  "Choisissez un mot de passe robuste. Toutes vos sessions seront déconnectées après validation.":
    "Choose a strong password. All your sessions will be signed out after validation.",
  "Votre mot de passe a été réinitialisé. Vous pouvez vous connecter.":
    "Your password has been reset. You can now sign in.",
  "Validation…": "Validating…",
  "Réinitialiser le mot de passe": "Reset password",
  "Invitation invalide": "Invalid invitation",
  "Ce lien d'activation est incomplet.": "This activation link is incomplete.",
  "Ouvrez le lien reçu par email. S'il a expiré, demandez à un administrateur de renvoyer l'invitation.":
    "Open the link you received by email. If it has expired, ask an administrator to resend the invitation.",
  "Activer votre compte": "Activate your account",
  "Choisissez votre mot de passe pour finaliser la création de votre compte FinOVA.":
    "Choose your password to finish creating your FinOVA account.",
  "Votre compte est activé. Vous pouvez vous connecter.":
    "Your account is activated. You can now sign in.",
  "Activation…": "Activating…",
  "Activer mon compte": "Activate my account",
  "Service indisponible. Vérifiez votre connexion puis réessayez.":
    "Service unavailable. Check your connection and try again.",
  "Invitation en attente": "Invitation pending",
  "Actif": "Active",
  "Désactivé": "Disabled",
  "Administration": "Administration",
  "Les comptes sont créés uniquement sur invitation. Aucune inscription publique n'est possible.":
    "Accounts are created by invitation only. No public sign-up is possible.",
  "{count} compte(s)": "{count} account(s)",
  "Email": "Email",
  "Nom complet": "Full name",
  "Prénom Nom": "First Last",
  "Rôle": "Role",
  "Inviter": "Invite",
  "Chargement des comptes…": "Loading accounts…",
  "Dernière connexion": "Last sign-in",
  "Actions": "Actions",
  " · vous": " · you",
  "Renvoyer": "Resend",
  "Désactiver": "Disable",
  "Réactiver": "Reactivate",
  "Aucun compte pour le moment. Invitez le premier utilisateur.":
    "No account yet. Invite the first user.",
  "Invitation envoyée à {email}.": "Invitation sent to {email}.",
  "Compte créé pour {email}, mais l'email n'a pas pu être envoyé. Vérifiez la configuration SMTP puis utilisez « Renvoyer ».":
    "Account created for {email}, but the email could not be sent. Check the SMTP configuration, then use “Resend”.",
  "Rôle de {email} mis à jour.": "Role of {email} updated.",
  "Invitation renvoyée à {email}.": "Invitation resent to {email}.",
  "{email} désactivé, sessions révoquées.": "{email} disabled, sessions revoked.",
  "{email} réactivé.": "{email} reactivated.",

  // ------------------------------------------------------------------ sources
  "Sources utilisateur": "User sources",
  "Ajouter un fichier": "Add a file",
  "Chargement des sources…": "Loading sources…",
  "Incluse": "Included",
  "En attente": "Pending",
  "Données officielles uniquement": "Official data only",

  // -------------------------------------------------------------------- audit
  "Chargement du rapport d'audit…": "Loading the audit report…",
  "Verdict": "Verdict",
  "Comment chaque chiffre publié est vérifié : contrôles indépendants, publication, constats et test de l'Auditor par injection de fautes. Les sources utilisateur ne sont pas comptées ici.":
    "How every published figure is verified: independent checks, publication, insights and the Auditor's fault-injection test. User sources are not counted here.",
  "Rapport d'évaluation et d'explicabilité, construit à partir des données courantes":
    "Evaluation and explainability report, built from the current data",
  "{count} réussis": "{count} passed",
  "{count} avertissements": "{count} warnings",
  "{count} échec": "{count} failure",
  "Run": "Run",
  "Run {id}": "Run {id}",
  "snapshot {id}": "snapshot {id}",
  "Version des données": "Data version",
  "Catalogue": "Catalogue",
  "Publication des valeurs": "Value publication",
  "Statut attribué par l'Auditor à chaque valeur d'indicateur (pays × année).":
    "Status assigned by the Auditor to each indicator value (country × year).",
  "Approuvé": "Approved",
  "Approuvé avec réserve": "Approved with reservation",
  "Bloqué": "Blocked",
  "Motifs des réserves :": "Reservation reasons:",
  "Contrôles de l'Auditor": "Auditor checks",
  "Chaque contrôle est recalculé indépendamment du pipeline.":
    "Each check is recalculated independently of the pipeline.",
  "{count} contrôles": "{count} checks",
  "Contrôle": "Check",
  "Ce qui est vérifié": "What is checked",
  "Détail": "Detail",
  "Détail et lignes concernées ({count})": "Detail and affected rows ({count})",
  "Liste limitée aux 200 premières lignes.": "List limited to the first 200 rows.",
  "Audit des constats": "Insight audit",
  "Chaque nombre d'un constat doit être une valeur publiée, son année ou un écart entre deux valeurs du même indicateur.":
    "Every number in an insight must be a published value, its year or a gap between two values of the same indicator.",
  "Audités": "Audited",
  "Acceptés": "Accepted",
  "Rejetés": "Rejected",
  "Non auditables": "Not auditable",
  "Accepté": "Accepted",
  "Rejeté": "Rejected",
  "Non auditable": "Not auditable",
  "Comment un chiffre est vérifié": "How a figure is verified",
  "Choisissez un indicateur, un pays et une année : la valeur est retracée jusqu'au fichier source.":
    "Choose an indicator, a country and a year: the value is traced back to the source file.",
  "Valeur publiée": "Published value",
  "indisponible ({reason})": "unavailable ({reason})",
  "non observée": "not observed",
  "Sources lues": "Sources read",
  "Aucune observation : la valeur reste vide.": "No observation: the value remains empty.",
  "{source} · fichier {file} · colonne {column} · texte brut « {text} »":
    "{source} · file {file} · column {column} · raw text “{text}”",
  "Formule": "Formula",
  "Valeur recalculée": "Recalculated value",
  "version des données {id}": "data version {id}",
  "catalogue {version}": "catalogue {version}",
  "Contrôles": "Checks",
  "{passed} contrôles réussis sur cette valeur": "{passed} checks passed on this value",
  "à noter : {list}": "note: {list}",
  "Publication": "Publication",
  "Valeur {status}": "Value {status}",
  "Test de l'Auditor par injection de fautes": "Auditor fault-injection test",
  "Des erreurs sont introduites dans une copie des données ; l'Auditor doit les détecter. Évaluation du {date}.":
    "Errors are introduced into a copy of the data; the Auditor must detect them. Evaluation of {date}.",
  "{detected} / {total} détectées": "{detected} / {total} detected",
  "Résultat antérieur au dernier audit : relancez scripts/evaluate_auditor.py pour le mettre à jour.":
    "Result predates the latest audit: rerun scripts/evaluate_auditor.py to update it.",
  "Aucune évaluation enregistrée.": "No evaluation recorded.",
  "Faute injectée": "Injected fault",
  "Contrôle attendu": "Expected check",
  "Détectée": "Detected",
  "Verdict obtenu": "Verdict obtained",
  "Oui": "Yes",
  "Non": "No",
  "Erreur HTTP {status}": "HTTP error {status}",
  "Statut": "Status",
  "Audit réussi": "Audit passed",
  "Audit réussi avec avertissements": "Audit passed with warnings",
  "Audit en échec": "Audit failed",
  "Avertissement": "Warning",
  "bloquée": "blocked",
  "non évaluée": "not evaluated",

  // -------------------------------------------------------------- mes données
  "Structure": "Structure",
  "Vérification": "Review",
  "Confirmation": "Confirmation",
  "Étapes": "Steps",
  "Annuler": "Cancel",
  "Retour": "Back",
  "Continuer": "Continue",
  "Traitement…": "Processing…",
  "Années": "Years",
  "Indicateurs": "Indicators",
  "Mise à jour": "Updated",
  "Score qualité": "Quality score",
  "Exclue": "Excluded",
  "Aucune source ajoutée": "No source added",
  "Ajoutez un fichier CSV pour comparer vos propres chiffres, à côté du tableau de bord officiel.":
    "Add a CSV file to compare your own figures alongside the official dashboard.",
  "Ajoutez vos propres fichiers CSV. Ils restent séparés des chiffres officiels : jamais mélangés aux cartes, à l'audit officiel ni aux réponses d'Ask Finova.":
    "Add your own CSV files. They stay separate from official figures: never mixed with the cards, the official audit or Ask Finova answers.",
  "Voir les données": "View data",
  "Remplacer le fichier": "Replace file",
  "Supprimer": "Delete",
  "Supprimer {name}": "Delete {name}",
  "Supprimer « {name} » ? Ses données seront retirées de l'entrepôt et le tableau de bord sera recalculé. La copie du fichier est conservée.":
    "Delete “{name}”? Its data will be removed from the warehouse and the dashboard will be recalculated. The file copy is kept.",
  "Supprimer et recalculer": "Delete and recalculate",
  "Colonne d'année": "Year column",
  "Colonne d'indicateur": "Indicator column",
  "Ignorer": "Ignore",
  "Format long : une ligne par observation": "Long format: one row per observation",
  "Années en colonnes": "Years in columns",
  "Indicateurs en colonnes": "Indicators in columns",
  "fraction (0 à 1)": "fraction (0 to 1)",
  "par 100 000 adultes": "per 100,000 adults",
  "par 1 000 adultes": "per 1,000 adults",
  "nombre": "number",
  "monnaie": "currency",
  "monnaie ({code})": "currency ({code})",
  "Collecte des sources": "Source collection",
  "Profil des colonnes": "Column profiling",
  "Chargement dans l'entrepôt": "Loading into the warehouse",
  "Calcul des indicateurs": "Indicator calculation",
  "Audit indépendant": "Independent audit",
  "Mise à jour du tableau de bord": "Dashboard update",
  "point-virgule (;)": "semicolon (;)",
  "virgule (,)": "comma (,)",
  "tabulation": "tab",
  "barre verticale (|)": "vertical bar (|)",
  "Remplacement du fichier de la source « {name} ».":
    "Replacing the file of source “{name}”.",
  "Remplacement du fichier de la source « {name} »":
    "Replacing the file of source “{name}”",
  "Choisissez une unité pour chaque indicateur": "Choose a unit for each indicator",
  "Ajouter et recalculer": "Add and recalculate",
  "Glissez votre fichier CSV ici": "Drag your CSV file here",
  "ou": "or",
  "Choisir un fichier": "Choose a file",
  "Format accepté : CSV (séparateur ; , tabulation ou |) · {size} Mo maximum · le fichier n'est jamais exécuté ni ouvert par un tableur.":
    "Accepted format: CSV (separator ; , tab or |) · {size} MB maximum · the file is never executed or opened by a spreadsheet.",
  "Trois dispositions reconnues": "Three recognised layouts",
  "Format long": "Long format",
  "Une configuration enregistrée correspond à ces colonnes (« {name} »).":
    "A saved configuration matches these columns (“{name}”).",
  "Réutiliser la configuration enregistrée": "Reuse the saved configuration",
  "Fichier : {name} · {rows} ligne(s)": "File: {name} · {rows} row(s)",
  "Séparateur : {value}": "Separator: {value}",
  "Décimale : {value}": "Decimal: {value}",
  "virgule": "comma",
  "point": "dot",
  "Disposition à préciser": "Layout to specify",
  "Pays : {kind} ({share} % reconnus)": "Countries: {kind} ({share}% recognised)",
  "codes ISO3": "ISO3 codes",
  "noms de pays": "country names",
  "Nom de la source": "Source name",
  "Minuscules, chiffres et _ (ex. clients_microfinance).":
    "Lowercase letters, digits and _ (e.g. clients_microfinance).",
  "Colonne": "Column",
  "Exemples": "Examples",
  "Preuve": "Evidence",
  "Rôle de la colonne {name}": "Role of column {name}",
  "L'unité n'est jamais devinée : choisissez celle des valeurs telles qu'elles sont écrites dans le fichier. Aucune conversion n'est faite sauf si vous la demandez.":
    "The unit is never guessed: choose the one of the values as written in the file. No conversion is done unless you ask for it.",
  "Code": "Code",
  "Libellé": "Label",
  "Unité (obligatoire)": "Unit (required)",
  "Conversion": "Conversion",
  "Libellé de {code}": "Label for {code}",
  "Unité de {code}": "Unit for {code}",
  "Monnaie de {code}": "Currency of {code}",
  "ex. TND": "e.g. TND",
  "— à choisir —": "— choose —",
  "aucune": "none",
  "pourcentage → fraction": "percentage → fraction",
  "Indicateur officiel comparable (facultatif)": "Comparable official indicator (optional)",
  "choisissez d'abord l'unité": "choose the unit first",
  "chargement…": "loading…",
  "aucun indicateur officiel dans cette unité": "no official indicator in this unit",
  "Indicateur officiel comparable à {code}": "Official indicator comparable to {code}",
  "aucun": "none",
  "Définition officielle : {value}": "Official definition: {value}",
  "Dénominateur : {value}": "Denominator: {value}",
  "Mon indicateur mesure la même chose (même population, même définition)":
    "My indicator measures the same thing (same population, same definition)",
  "Case non cochée : l'indicateur comparable ne sera pas enregistré.":
    "Box unchecked: the comparable indicator will not be saved.",
  "« {name} » · {count} valeur(s)": "“{name}” · {count} value(s)",
  "Lignes retenues": "Rows kept",
  "{count} valeur(s)": "{count} value(s)",
  "Pays reconnus": "Recognised countries",
  "Réussi": "Passed",
  "Échec": "Failed",
  "score {score}": "score {score}",
  "Pays non reconnus": "Unrecognised countries",
  "Indiquez un code ISO3 (ex. MRT) ou laissez vide pour ignorer ces lignes.":
    "Enter an ISO3 code (e.g. MRT) or leave empty to ignore these rows.",
  "ISO3 ou vide = ignorer": "ISO3 or empty = ignore",
  "Appliquer et revérifier": "Apply and re-check",
  "Aperçu (10 premières valeurs)": "Preview (first 10 values)",
  "Unité": "Unit",
  "Texte du fichier": "File text",
  "Ligne": "Row",
  "ligne {line} « {text} »": "row {line} “{text}”",
  "{count} valeur(s) non numérique(s) ignorée(s) : {examples}":
    "{count} non-numeric value(s) ignored: {examples}",
  "{count} doublon(s) identique(s) retiré(s).": "{count} identical duplicate(s) removed.",
  "{count} année(s) invalide(s) ignorée(s).": "{count} invalid year(s) ignored.",
  "Contrôle qualité : {message}": "Quality control: {message}",
  "Configuration enregistrée réutilisée : « {name} ».":
    "Saved configuration reused: “{name}”.",
  "Indicateurs : {list}.": "Indicators: {list}.",
  "{values} valeur(s), {countries} pays, années {range}.":
    "{values} value(s), {countries} countries, years {range}.",
  "Ajouter la source « {name} »": "Add source “{name}”",
  "Remplacer le fichier de la source « {name} »":
    "Replace the file of source “{name}”",
  "Recalcul hors ligne": "Offline recalculation",
  "Recalcul hors ligne en cours (sources officielles reprises du snapshot publié) — étape : {step}":
    "Offline recalculation in progress (official sources reused from the published snapshot) — step: {step}",
  "Suppression et recalcul": "Deletion and recalculation",
  "Ajout et recalcul": "Addition and recalculation",
  "L'opération continue même si vous rechargez la page.":
    "The operation continues even if you reload the page.",
  "{seconds} s": "{seconds} s",
  "Source intégrée à l'entrepôt": "Source integrated into the warehouse",
  "Recalcul terminé": "Recalculation complete",
  "Aucune donnée nouvelle": "No new data",
  "Source retirée": "Source removed",
  "Source exclue par le contrôle qualité": "Source excluded by quality control",
  "Audit en échec : version précédente conservée":
    "Audit failed: previous version kept",
  "Le recalcul a échoué": "Recalculation failed",
  "Voir mes sources": "View my sources",
  "← Mes sources": "← My sources",
  "Aucune valeur publiée": "No published value",
  "La source n'est pas (ou plus) intégrée à l'entrepôt : voir son statut dans la liste.":
    "The source is not (or no longer) integrated into the warehouse: see its status in the list.",
  "Provenance": "Provenance",
  "Valeurs importées par l'utilisateur, publiées telles quelles : elles ne sont pas des chiffres officiels.":
    "Values imported by the user, published as-is: they are not official figures.",
  "Le fichier est copié dans data/uploads/, puis le pipeline est recalculé (contrôle qualité, entrepôt, audit, tableau de bord). Les sources officielles ne sont pas retéléchargées.":
    "The file is copied to data/uploads/, then the pipeline is recalculated (quality control, warehouse, audit, dashboard). Official sources are not downloaded again.",
  "Les chiffres officiels du tableau de bord ne changent pas : vos données restent séparées des chiffres officiels (cette page, le bloc « Vos indicateurs face aux données officielles », Ask Finova en mode local).":
    "Official dashboard figures do not change: your data stays separate from official figures (this page, the “Your indicators versus official data” block, Ask Finova in local mode).",

  // --------------------------------------------------------------- agents / divers
  "Agents": "Agents",
  "Route 2 {id}": "Route 2 {id}",
  "Route 2 non exécutée": "Route 2 not run",
  "Chargement du dernier run…": "Loading the latest run…",
  "Recalcul en cours…": "Recalculation in progress…",
  "Recalculer les données": "Recalculate data",
  "démarrage": "starting",
  "Aucune donnée nouvelle : le contenu est identique à la version publiée. Les agents suivants sont ignorés.":
    "No new data: the content is identical to the published version. The following agents are skipped.",
  "terminé {date} ({seconds} s)": "completed {date} ({seconds} s)",
  "LLM optionnel": "Optional LLM",
  "déterministe": "deterministic",
  "appels LLM : {count}": "LLM calls: {count}",
  "terminé": "done",
  "en cours…": "running…",
  "ignoré": "skipped",
  "erreur": "error",
  "réussi": "successful",
  "à la demande": "on demand",
  "non exécuté": "not run",
  "Route 1 — fiabiliser les données": "Route 1 — make the data reliable",
  "Route 2 — analyser et publier": "Route 2 — analyse and publish",
  "Interface": "Interface",
  "Vos indicateurs face aux données officielles": "Your indicators versus official data",
  "Votre indicateur": "Your indicator",
  "Indicateur officiel": "Official indicator",
  "aucune valeur": "no value",
  "aucune valeur approuvée": "no approved value",
  "Définition officielle : {definition}": "Official definition: {definition}",
  "Pistes de recommandation": "Recommendation leads",
  "Règles fixes appliquées aux valeurs auditées · association, pas causalité":
    "Fixed rules applied to audited values · association, not causation",
  "{count} piste": "{count} lead",
  "{count} pistes": "{count} leads",
  "{count} comparaisons": "{count} comparisons",
  "Pistes indisponibles : {detail}": "Leads unavailable: {detail}",
  "Chargement des pistes…": "Loading leads…",
  "Aucune règle déclenchée pour {country} en {year} : aucun écart ne dépasse les seuils.":
    "No rule triggered for {country} in {year}: no gap exceeds the thresholds.",
  "Groupe cible : {group}": "Target group: {group}",
  "Règle : {rule}": "Rule: {rule}",
  "Sources": "Sources",
  "approuvée": "approved",
  "approuvée avec réserve": "approved with reservation",
  "moyenne des pairs": "peer average",
  "avec réserve": "with reservation",
  "À partir de vos données": "From your data",
  "Même logique de règles fixes, appliquée à vos indicateurs déclarés comparables, seulement quand votre année est celle de la valeur officielle. Comparaison indicative.":
    "Same fixed-rule logic, applied to your indicators declared comparable, only when your year matches the official value. Indicative comparison.",
  "Préparation du PDF…": "Preparing the PDF…",
  "Télécharger le rapport (PDF)": "Download the report (PDF)",
  "Ajoute une annexe séparée avec vos données.": "Adds a separate appendix with your data.",
  "Inclure l'annexe : vos données": "Include the appendix: your data",
  "Session expirée : reconnectez-vous pour télécharger le rapport.":
    "Session expired: sign in again to download the report.",
  "Téléchargement impossible (HTTP {status}).": "Download failed (HTTP {status}).",
  "Téléchargement impossible.": "Download failed.",
  "validé": "passed",
  "Constats et pistes de recommandation — {country}, {year}":
    "Insights and recommendation leads — {country}, {year}",
  "Combien d'adultes ont un compte ?": "How many adults have an account?",
};

const AR: Record<string, string> = {
  // ---------------------------------------------------------------- navigation
  "Vue d'ensemble": "نظرة عامة",
  "Inclusion et inégalités": "الإدماج المالي والتفاوتات",
  "Accès et crédit": "الوصول والائتمان",
  "Pourquoi l'exclusion ?": "لماذا الإقصاء؟",
  "Sources et qualité": "المصادر والجودة",
  "Mes données": "بياناتي",
  "Audit et confiance": "التدقيق والثقة",
  "Utilisateurs": "المستخدمون",
  "Administrateur": "مسؤول",
  "Utilisateur": "مستخدم",
  "Déconnexion": "تسجيل الخروج",
  "Pays": "البلد",
  "Année": "السنة",
  "enquête": "استقصاء",
  "Langue": "اللغة",
  "Thème": "السمة",
  "Clair": "فاتح",
  "Sombre": "داكن",
  "Passer en mode sombre": "التبديل إلى الوضع الداكن",
  "Passer en mode clair": "التبديل إلى الوضع الفاتح",
  "Choisir la langue": "اختيار اللغة",
  "Choisir le thème": "اختيار السمة",
  "Ouvrir Ask Finova": "فتح Ask Finova",
  "Fermer": "إغلاق",
  "Réessayer": "إعادة المحاولة",
  "Retour à la connexion": "العودة إلى تسجيل الدخول",
  "Se connecter": "تسجيل الدخول",
  "Combien d'adultes ont un compte en Tunisie ?": "كم عدد البالغين الذين يمتلكون حسابًا في تونس؟",
  "Pourquoi l'écart femmes-hommes est-il élevé ?": "لماذا الفجوة بين الجنسين مرتفعة؟",
  "Les ATMs ont-ils augmenté depuis 2017 ?": "هل زاد عدد الصرافات الآلية منذ 2017؟",
  "Que dit la pauvreté rurale ?": "ماذا تقول بيانات الفقر الريفي؟",

  // ------------------------------------------------------------ pages / shell
  "Le tableau de bord est indisponible.": "لوحة المعلومات غير متاحة.",
  "Tableau de bord indisponible": "لوحة المعلومات غير متاحة",
  "Les données n'ont pas pu être chargées pour le moment.":
    "تعذّر تحميل البيانات في الوقت الحالي.",
  "Détail technique": "تفاصيل تقنية",
  "Vérifiez que le service tourne et que la base de données a bien été préparée.":
    "تحقق من تشغيل الخدمة ومن إعداد قاعدة البيانات.",
  "Vérification de votre session…": "جارٍ التحقق من جلستك…",
  "Connexion indisponible": "تسجيل الدخول غير متاح",
  "Préparation des données…": "جارٍ إعداد البيانات…",
  "Préparation des chiffres pour {country} {year}… ({elapsed} s). La vue précédente reste affichée pendant le calcul, puis elle sera remplacée.":
    "جارٍ إعداد الأرقام لـ {country} {year}… ({elapsed} ث). تبقى الواجهة السابقة معروضة أثناء الحساب ثم تُستبدل.",
  "La première ouverture de ce pays peut prendre 20 à 40 secondes.":
    "قد يستغرق فتح هذا البلد لأول مرة من 20 إلى 40 ثانية.",
  "Toujours en cours ({elapsed} s) : les séries annuelles sont recalculées depuis la base, sans estimation.":
    "لا يزال قيد التنفيذ ({elapsed} ث): تُعاد السلاسل السنوية من قاعدة البيانات دون أي تقدير.",
  "lecture de la base locale et vérification des sources.":
    "قراءة قاعدة البيانات المحلية والتحقق من المصادر.",
  "Années d'enquête Findex pour {country} : {years}. Les autres années reprennent la dernière enquête antérieure ; les indicateurs bancaires restent ceux de l'année.":
    "سنوات استقصاء Findex لـ {country}: {years}. تستخدم السنوات الأخرى آخر استقصاء سابق؛ وتبقى المؤشرات المصرفية الخاصة بالسنة المختارة.",
  "Pas d'enquête Findex en {year} : les chiffres viennent de l'enquête {used}.":
    "لا يوجد استقصاء Findex في {year}: الأرقام مأخوذة من استقصاء {used}.",
  "Cette vue a été préparée à la demande pour ce pays et cette année, à partir de la même base de données. Elle peut différer de la vue publiée par défaut.":
    "أُعدّت هذه الواجهة عند الطلب لهذا البلد وهذه السنة من قاعدة البيانات نفسها، وقد تختلف عن الواجهة المنشورة افتراضيًا.",
  "Mise à jour du {date}": "تحديث {date}",
  "Aucune valeur inventée · {count} données sourcées":
    "لا قيمة مُختلقة · {count} بيانات موثّقة المصدر",
  "Page non disponible pour cette sélection": "الصفحة غير متاحة لهذا الاختيار",
  "Les données de cette page ne sont pas disponibles pour ce pays et cette année.":
    "بيانات هذه الصفحة غير متاحة لهذا البلد وهذه السنة.",

  // -------------------------------------------------------------------- meters
  "Chiffres clés": "أرقام رئيسية",
  "Chaque chiffre peut être rattaché à sa source":
    "كل رقم يمكن ربطه بمصدره",
  "Année : {year}": "السنة: {year}",
  "Année : {year} · dernière enquête": "السنة: {year} · آخر استقصاء",
  "Source et méthode": "المصدر والمنهج",
  "Pourquoi ?": "لماذا؟",
  "Comprendre ce chiffre": "فهم هذا الرقم",
  "Comprendre cette donnée": "فهم هذه المعطيات",
  "Comprendre ce graphique": "فهم هذا الرسم البياني",
  "Ce que dit la valeur": "ماذا تعني القيمة",
  "Lecture simple": "قراءة مبسطة",
  "À quoi sert ce chiffre": "فيمَ يُستخدم هذا الرقم",
  "Ce que le chiffre ne dit pas": "ما لا يقوله هذا الرقم",
  "Analyse expliquée": "التحليل المشروح",
  "Ce que montrent les données": "ما تُظهره البيانات",
  "Piste à explorer": "مسار للاستكشاف",
  "Demander à Finova": "اسأل Finova",
  "Cette explication utilise uniquement les chiffres publiés ; elle ne recalcule rien.":
    "هذا الشرح يستخدم الأرقام المنشورة فقط؛ ولا يعيد حساب أي قيمة.",
  "Aucun facteur explicatif n'est déduit : l'analyse relie seulement des observations issues des mêmes données.":
    "لا يُستنتج أي عامل تفسيري: التحليل يربط فقط ملاحظات مستمدة من البيانات نفسها.",
  "Lecture des données": "قراءة البيانات",
  "Année de référence": "سنة المرجع",
  "Année de référence : {year}": "سنة المرجع: {year}",
  "Année : {year} · {provider}": "السنة: {year} · {provider}",
  "Pourquoi ce chiffre est-il à ce niveau ?": "لماذا هذا الرقم عند هذا المستوى؟",
  "Pourquoi {label} est-il à ce niveau ?": "لماذا {label} عند هذا المستوى؟",
  "Pourquoi ce graphique évolue-t-il ainsi ?": "لماذا يتطور هذا الرسم البياني بهذه الطريقة؟",
  "Que signifie {label} dans ce tableau de bord ?":
    "ماذا يعني {label} في لوحة المعلومات هذه؟",
  "Ce chiffre n'est pas disponible pour cette sélection.":
    "هذا الرقم غير متاح لهذا الاختيار.",
  "En {year}, {label} s'élève à {value}.": "في {year}، يبلغ {label} {value}.",
  "{label} : {value} en {year}.": "{label}: {value} في {year}.",
  "Évolution : {delta}.": "التطور: {delta}.",
  "La valeur affichée est {value} pour l'année {year}.":
    "القيمة المعروضة هي {value} لسنة {year}.",
  "Entre {from} et {to}, {label} passe de {start} à {end}.":
    "بين {from} و{to}، ينتقل {label} من {start} إلى {end}.",
  "La valeur la plus élevée est {value} ({label}).":
    "أعلى قيمة هي {value} ({label}).",
  "La valeur la plus basse est {value} ({label}).":
    "أدنى قيمة هي {value} ({label}).",
  "{label} : {value}.": "{label}: {value}.",
  "L'écart le plus marqué concerne {group} : {value} points.":
    "أكبر فجوة تخص {group}: {value} نقطة.",
  "{label} : l'écart passe de {start} à {end} points entre {from} et {to}.":
    "{label}: تنتقل الفجوة من {start} إلى {end} نقطة بين {from} و{to}.",
  "Le maximum observé est {value}, pour {label}.":
    "أعلى قيمة ملاحظة هي {value} لـ {label}.",
  "Ce que montre ce graphique": "ما يُظهره هذا الرسم البياني",
  "Graphique sans donnée pour cette sélection.":
    "رسم بياني بلا بيانات لهذا الاختيار.",
  "Aucune précaution particulière n'est signalée pour ce graphique.":
    "لا توجد احتياطات خاصة مُشار إليها لهذا الرسم البياني.",
  "Source : {source}": "المصدر: {source}",
  "En attente de données": "في انتظار البيانات",
  "Indisponible": "غير متاح",
  "À vérifier": "بحاجة إلى تحقق",
  " · à vérifier": " · بحاجة إلى تحقق",
  "Vos données": "بياناتك",
  "année utilisée : {year} · {provider}": "السنة المستخدمة: {year} · {provider}",
  "D'où vient ce chiffre ?": "من أين جاء هذا الرقم؟",
  "Ce que mesure l'indicateur": "ما يقيسه المؤشر",
  "Source": "المصدر",
  "consulter la source": "عرض المصدر",
  "Périmètre": "النطاق",
  "Fiabilité de la définition": "موثوقية التعريف",
  "Année réellement utilisée": "السنة المستخدمة فعليًا",
  "Repère de provenance": "علامة المصدر",
  "Points à vérifier": "نقاط تستوجب التحقق",
  "Aucun chiffre n'est recalculé dans l'interface : la valeur et l'année proviennent directement des données source.":
    "لا يُعاد حساب أي رقم في الواجهة: القيمة والسنة مأخوذتان مباشرة من بيانات المصدر.",
  "Détails techniques (pour vérification)": "تفاصيل تقنية (للتحقق)",
  "Identifiant": "المعرّف",
  "Définition d'origine": "التعريف الأصلي",
  "Source d'origine": "المصدر الأصلي",
  "Filtre d'origine": "المرشح الأصلي",
  "Statut d'origine": "الحالة الأصلية",
  "Valeur importée par l'utilisateur, hors chiffres officiels : BIFlow ne la vérifie pas":
    "قيمة أدخلها المستخدم خارج الأرقام الرسمية: لا يتحقق منها BIFlow",

  // ------------------------------------------------------------ insights / XAI
  "À retenir": "أبرز النقاط",
  "Chaque constat renvoie aux chiffres utilisés":
    "كل استنتاج يحيل إلى الأرقام المستخدمة",
  "Voir les données sources": "عرض بيانات المصدر",
  "Analyse du constat": "تحليل الاستنتاج",
  "Pourquoi ces écarts ?": "لماذا هذه الفجوات؟",
  "Lien observé, pas une cause": "علاقة ملحوظة وليست سببًا",
  "1 · Ce que montrent les données": "1 · ما تُظهره البيانات",
  "2 · Comment le lire": "2 · كيف نقرأها",
  "3 · Piste à explorer": "3 · مجال للاستكشاف",
  "Hypothèse à tester": "فرضية قابلة للاختبار",
  "Ces écarts décrivent des groupes observés : ils ne prouvent pas un lien de cause à effet.":
    "تصف هذه الفجوات مجموعات ملحوظة ولا تثبت وجود علاقة سببية.",

  // ---------------------------------------------------------------- changes
  "Évolutions depuis la précédente mise à jour": "التغيّرات منذ التحديث السابق",
  "Aucune mise à jour antérieure comparable : l'historique démarre avec cette version.":
    "لا يوجد تحديث سابق قابل للمقارنة: يبدأ السجل مع هذا الإصدار.",
  "Aucun indicateur n'a changé depuis la mise à jour du {date}{rest}":
    "لم يتغيّر أي مؤشر منذ تحديث {date}{rest}",
  " : les {count} indicateurs suivis restent identiques.":
    ": تبقى المؤشرات {count} المتابعة كما هي.",
  "Les {count} autres indicateurs suivis sont restés identiques.":
    "بقيت المؤشرات {count} الأخرى المتابعة كما هي.",
  "Indicateur": "المؤشر",
  "Avant": "قبل",
  "Maintenant": "الآن",
  "Écart": "الفارق",
  "État": "الحالة",

  // ----------------------------------------------------------------- notices
  "Précautions de lecture": "احتياطات القراءة",
  "Ce qu'il faut savoir avant de citer ces chiffres.":
    "ما ينبغي معرفته قبل الاستشهاد بهذه الأرقام.",
  "{count} remarque": "ملاحظة {count}",
  "{count} remarques": "{count} ملاحظات",

  // ---------------------------------------------------------------- pipeline
  "Du fichier source au tableau de bord": "من الملف المصدر إلى لوحة المعلومات",
  "Chaque étape est contrôlée automatiquement avant la publication.":
    "تُراقَب كل خطوة آليًا قبل النشر.",
  "Qualité : {state}": "الجودة: {state}",
  "validée": "مقبولة",
  "à corriger": "تحتاج إلى تصحيح",
  "Étape 1 — Fiabiliser les données": "الخطوة 1 — تعزيز موثوقية البيانات",
  "Étape 2 — Calculer, expliquer, publier": "الخطوة 2 — الحساب والشرح والنشر",
  "Validé": "مقبول",
  "Anomalie": "خلل",
  "→ les données rejoignent la base centrale": "← تنضم البيانات إلى القاعدة المركزية",
  "→ arrêt de la mise à jour, aucune donnée publiée": "← توقف التحديث ولا تُنشر أي بيانات",
  "Contrôle qualité": "مراقبة الجودة",
  "score {score} / {threshold} requis": "النتيجة {score} / {threshold} المطلوبة",
  "Résultat": "النتيجة",
  "Lignes": "الأسطر",
  "Colonnes": "الأعمدة",
  "Score": "النتيجة",
  "À corriger": "تحتاج إلى تصحيح",
  "Résultat global : {state} · {count} problème(s) critique(s).":
    "النتيجة الإجمالية: {state} · {count} مشكلة حرجة.",
  "Base de données": "قاعدة البيانات",
  "consultation seule": "قراءة فقط",
  "Données enregistrées": "البيانات المسجلة",
  "Pays couverts": "البلدان المشمولة",
  "Par source": "حسب المصدر",
  "Signature": "البصمة",
  "Fichier": "الملف",
  "Sources utilisées": "المصادر المستخدمة",
  "Signatures et dates de collecte réelles": "بصمات وتواريخ جمع فعلية",
  "Collecté le": "تاريخ الجمع",
  "Lignes écartées": "الأسطر المستبعدة",
  "Dernière collecte": "آخر جمع",
  "Date": "التاريخ",
  "Période couverte": "الفترة المشمولة",
  "Historique indisponible.": "السجل غير متاح.",
  "Traitements appliqués": "المعالجات المطبقة",
  "Historique des mises à jour": "سجل التحديثات",
  "Générations du tableau de bord": "إصدارات لوحة المعلومات",
  "{count} génération(s) enregistrée(s).": "{count} إصدار محفوظ.",
  "Voir les identifiants": "عرض المعرّفات",
  "Versions archivées": "الإصدارات المؤرشفة",
  "aucune version archivée": "لا يوجد إصدار مؤرشف",
  "{count} version(s) archivée(s).": "{count} إصدار مؤرشف.",
  "Voir les versions": "عرض الإصدارات",
  "Contrôles de cohérence": "فحوص الاتساق",
  "{passed} contrôle(s) automatique(s) réussi(s) sur {total}.":
    "{passed} فحص آلي ناجح من أصل {total}.",
  "Détails techniques des contrôles": "تفاصيل تقنية للفحوص",
  "{count} valeurs": "{count} قيم",
  "non fournie": "غير مقدمة",
  "écart": "تباين",

  // -------------------------------------------------------------------- ask
  "Ask Finova": "Ask Finova",
  "Réponses fondées sur les chiffres du tableau de bord":
    "أجوبة مبنية على أرقام لوحة المعلومات",
  "Fermer le chat": "إغلاق المحادثة",
  "Posez une question sur le pays et l'année sélectionnés. Les réponses n'utilisent que les chiffres vérifiés du tableau de bord.":
    "اطرح سؤالًا عن البلد والسنة المختارين. لا تستخدم الأجوبة سوى الأرقام المتحققة في لوحة المعلومات.",
  "Chiffres vérifiés": "أرقام متحقق منها",
  "Chiffres à vérifier": "أرقام بحاجة إلى تحقق",
  "Vos données · ": "بياناتك · ",
  "Écrire une question…": "اكتب سؤالًا…",
  "Envoyer": "إرسال",
  "Ask Finova écrit…": "Ask Finova يكتب…",
  "Réponse automatique": "جواب آلي",
  "Réponse indisponible : {detail}": "الجواب غير متاح: {detail}",
  "Impossible de charger le contrat Finova.": "تعذّر تحميل عقد بيانات FinOVA.",

  // ----------------------------------------------------------------- charts
  "Formule de calcul": "صيغة الحساب",
  "Aucune observation.": "لا توجد ملاحظة.",
  "Aucune valeur.": "لا توجد قيمة.",
  "Aucune étape.": "لا توجد خطوة.",
  "Aucun groupe.": "لا توجد مجموعة.",
  "Aucun écart.": "لا توجد فجوة.",
  "Chaque point est un chiffre publié{unit} ; aucune valeur estimée.":
    "كل نقطة رقم منشور{unit}؛ ولا توجد قيمة مقدّرة.",
  " (nombre pour 100 000 adultes)": " (عدد لكل 100 ألف بالغ)",
  " (nombre pour 1 000 adultes)": " (عدد لكل 1000 بالغ)",
  " (valeur en %)": " (قيمة بالنسبة المئوية)",
  " (en pourcentage du PIB)": " (كنسبة من الناتج المحلي)",
  " (en dinars par mois)": " (بالدينار شهريًا)",
  " (en dinars par dollar)": " (بالدينار لكل دولار)",
  "Chaque question est posée séparément : la baisse d'une étape à l'autre ne signifie pas que les mêmes personnes quittent le système.":
    "يُطرح كل سؤال على حدة: انخفاض الانتقال من خطوة إلى أخرى لا يعني أن الأشخاص أنفسهم يغادرون المنظومة.",
  "Groupe le moins équipé": "المجموعة الأقل تجهيزًا",
  "Groupe le plus équipé": "المجموعة الأكثر تجهيزًا",
  "{value} points par rapport à l'étape précédente":
    "{value} نقطة مقارنة بالخطوة السابقة",
  "écart {value}": "الفجوة {value}",
  "{value} pts": "{value} نقطة",
  "{value} points": "{value} نقطة",
  "Les raisons de ne pas avoir de compte ne sont mesurées que depuis l'enquête {year}.":
    "لا تُقاس أسباب عدم امتلاك حساب إلا منذ استقصاء {year}.",
  "Aucune observation de ces raisons pour ce pays dans les enquêtes disponibles.":
    "لا توجد ملاحظة لهذه الأسباب لهذا البلد في الاستقصاءات المتاحة.",
  "Type de graphique inconnu : {kind}": "نوع رسم بياني غير معروف: {kind}",
  "Groupe": "المجموعة",
  "Valeur": "القيمة",
  "Évolution des écarts entre {from} et {to}": "تطور الفجوات بين {from} و{to}",
  "Chaque marche est une question Findex distincte, année {year}.":
    "كل درجة سؤال Findex مستقل، سنة {year}.",
  "Chaque point est une observation observée; aucune interpolation.":
    "كل نقطة رقم منشور؛ ولا توجد قيمة مقدّرة.",
  "Écart en points de pourcentage, année observée {year}.":
    "الفجوة بنقاط مئوية، السنة المرصودة {year}.",
  "Variation de l'écart entre deux groupes, en points de pourcentage.":
    "تغيّر الفجوة بين مجموعتين بنقاط مئوية.",
  "mise à jour du {date}": "تحديث {date}",
  "Années observées : {years}": "السنوات المرصودة: {years}",

  // ------------------------------------------------------------------- auth
  "Les chiffres d'abord.": "الأرقام أولًا.",
  "Les sources toujours.": "المصادر دائمًا.",
  "FinOVA rassemble des chiffres publics sur les services financiers — compte bancaire, épargne, crédit — les vérifie, puis vous les explique simplement.":
    "يجمع FinOVA أرقامًا عامة عن الخدمات المالية — الحساب البنكي والادخار والائتمان — ويتحقق منها ثم يشرحها ببساطة.",
  "Pas besoin d'être spécialiste : chaque page dit ce que le chiffre signifie, d'où il vient et ce qu'il ne permet pas de conclure.":
    "لا حاجة إلى التخصص: كل صفحة تبيّن معنى الرقم ومصدره وما لا يمكن استنتاجه منه.",
  "Connexion": "تسجيل الدخول",
  "Accès réservé aux comptes autorisés.": "الوصول مقصور على الحسابات المصرح لها.",
  "Adresse email": "البريد الإلكتروني",
  "Mot de passe": "كلمة المرور",
  "Connexion…": "جارٍ تسجيل الدخول…",
  "S'authentifier": "تسجيل الدخول",
  "Mot de passe oublié ?": "هل نسيت كلمة المرور؟",
  "Mot de passe oublié": "نسيت كلمة المرور",
  "Indiquez l'adresse associée à votre compte. Pour des raisons de sécurité, la réponse est toujours la même.":
    "أدخل العنوان المرتبط بحسابك. لأسباب أمنية يكون الرد دائمًا واحدًا.",
  "Si un compte correspond à cette adresse, un lien de réinitialisation vient d'être envoyé. Il est valable 15 minutes et ne peut être utilisé qu'une seule fois.":
    "إذا وُجد حساب مطابق لهذا العنوان فقد أُرسل رابط إعادة التعيين. صلاحيته 15 دقيقة ولا يُستخدم إلا مرة واحدة.",
  "Pensez à vérifier les indésirables. Sans SMTP configuré, le lien est écrit par le serveur dans data/auth/outbox/.":
    "تحقق من مجلد البريد غير المرغوب. في حال عدم إعداد SMTP يكتب الخادم الرابط في data/auth/outbox/.",
  "Envoi…": "جارٍ الإرسال…",
  "Envoyer le lien": "إرسال الرابط",
  "Nouveau mot de passe": "كلمة مرور جديدة",
  "Confirmer le mot de passe": "تأكيد كلمة المرور",
  "10 caractères minimum, avec au moins une lettre et un chiffre.":
    "10 أحرف على الأقل، تتضمن حرفًا واحدًا ورقمًا واحدًا على الأقل.",
  "Les deux mots de passe ne correspondent pas.": "كلمتا المرور غير متطابقتين.",
  "Lien invalide": "رابط غير صالح",
  "Ce lien de réinitialisation est incomplet.": "رابط إعادة التعيين غير مكتمل.",
  "Ouvrez le lien reçu par email, ou demandez-en un nouveau.":
    "افتح الرابط المستلم بالبريد أو اطلب رابطًا جديدًا.",
  "Demander un nouveau lien": "طلب رابط جديد",
  "Choisissez un mot de passe robuste. Toutes vos sessions seront déconnectées après validation.":
    "اختر كلمة مرور قوية. ستُغلق كل جلساتك بعد التأكيد.",
  "Votre mot de passe a été réinitialisé. Vous pouvez vous connecter.":
    "أُعيد تعيين كلمة المرور. يمكنك تسجيل الدخول.",
  "Validation…": "جارٍ التحقق…",
  "Réinitialiser le mot de passe": "إعادة تعيين كلمة المرور",
  "Invitation invalide": "دعوة غير صالحة",
  "Ce lien d'activation est incomplet.": "رابط التفعيل غير مكتمل.",
  "Ouvrez le lien reçu par email. S'il a expiré, demandez à un administrateur de renvoyer l'invitation.":
    "افتح الرابط المستلم بالبريد. إذا انتهت صلاحيته فاطلب من المسؤول إعادة إرسال الدعوة.",
  "Activer votre compte": "تفعيل حسابك",
  "Choisissez votre mot de passe pour finaliser la création de votre compte FinOVA.":
    "اختر كلمة المرور لإتمام إنشاء حسابك في FinOVA.",
  "Votre compte est activé. Vous pouvez vous connecter.":
    "تم تفعيل حسابك. يمكنك تسجيل الدخول.",
  "Activation…": "جارٍ التفعيل…",
  "Activer mon compte": "تفعيل حسابي",
  "Service indisponible. Vérifiez votre connexion puis réessayez.":
    "الخدمة غير متاحة. تحقق من اتصالك ثم أعد المحاولة.",
  "Invitation en attente": "دعوة معلّقة",
  "Actif": "نشط",
  "Désactivé": "معطّل",
  "Administration": "الإدارة",
  "Les comptes sont créés uniquement sur invitation. Aucune inscription publique n'est possible.":
    "تُنشأ الحسابات بدعوة فقط. لا يمكن التسجيل العام.",
  "{count} compte(s)": "{count} حساب",
  "Email": "البريد الإلكتروني",
  "Nom complet": "الاسم الكامل",
  "Prénom Nom": "الاسم واللقب",
  "Rôle": "الدور",
  "Inviter": "دعوة",
  "Chargement des comptes…": "جارٍ تحميل الحسابات…",
  "Dernière connexion": "آخر دخول",
  "Actions": "الإجراءات",
  " · vous": " · أنت",
  "Renvoyer": "إعادة الإرسال",
  "Désactiver": "تعطيل",
  "Réactiver": "إعادة التفعيل",
  "Aucun compte pour le moment. Invitez le premier utilisateur.":
    "لا يوجد حساب بعد. ادعُ أول مستخدم.",
  "Invitation envoyée à {email}.": "أُرسلت الدعوة إلى {email}.",
  "Compte créé pour {email}, mais l'email n'a pas pu être envoyé. Vérifiez la configuration SMTP puis utilisez « Renvoyer ».":
    "أُنشئ حساب لـ {email}، لكن تعذّر إرسال البريد. تحقق من إعداد SMTP ثم استخدم «إعادة الإرسال».",
  "Rôle de {email} mis à jour.": "حُدّث دور {email}.",
  "Invitation renvoyée à {email}.": "أُعيد إرسال الدعوة إلى {email}.",
  "{email} désactivé, sessions révoquées.": "عُطّل {email} وأُلغيت جلساته.",
  "{email} réactivé.": "أُعيد تفعيل {email}.",

  // ------------------------------------------------------------------ sources
  "Sources utilisateur": "مصادر المستخدم",
  "Ajouter un fichier": "إضافة ملف",
  "Chargement des sources…": "جارٍ تحميل المصادر…",
  "Incluse": "مشمولة",
  "En attente": "قيد الانتظار",
  "Données officielles uniquement": "بيانات رسمية فقط",

  // -------------------------------------------------------------------- audit
  "Chargement du rapport d'audit…": "جارٍ تحميل تقرير التدقيق…",
  "Verdict": "الحكم",
  "Comment chaque chiffre publié est vérifié : contrôles indépendants, publication, constats et test de l'Auditor par injection de fautes. Les sources utilisateur ne sont pas comptées ici.":
    "كيف يُتحقق من كل رقم منشور: فحوص مستقلة، النشر، الاستنتاجات واختبار المدقق بحقن الأخطاء. لا تُحتسب مصادر المستخدم هنا.",
  "Rapport d'évaluation et d'explicabilité, construit à partir des données courantes":
    "تقرير التقييم والقابلية للتفسير، مبني على البيانات الحالية",
  "{count} réussis": "{count} ناجح",
  "{count} avertissements": "{count} تحذير",
  "{count} échec": "{count} فشل",
  "Run": "التشغيل",
  "Run {id}": "تشغيل {id}",
  "snapshot {id}": "لقطة {id}",
  "Version des données": "إصدار البيانات",
  "Catalogue": "الكتالوج",
  "Publication des valeurs": "نشر القيم",
  "Statut attribué par l'Auditor à chaque valeur d'indicateur (pays × année).":
    "الحالة التي يمنحها المدقق لكل قيمة مؤشر (بلد × سنة).",
  "Approuvé": "معتمد",
  "Approuvé avec réserve": "معتمد مع تحفظ",
  "Bloqué": "محجوب",
  "Motifs des réserves :": "أسباب التحفظ:",
  "Contrôles de l'Auditor": "فحوص المدقق",
  "Chaque contrôle est recalculé indépendamment du pipeline.":
    "يُعاد حساب كل فحص بشكل مستقل عن المسار.",
  "{count} contrôles": "{count} فحص",
  "Contrôle": "الفحص",
  "Ce qui est vérifié": "ما يُتحقق منه",
  "Détail": "التفاصيل",
  "Détail et lignes concernées ({count})": "التفاصيل والأسطر المعنية ({count})",
  "Liste limitée aux 200 premières lignes.": "القائمة محدودة بأول 200 سطر.",
  "Audit des constats": "تدقيق الاستنتاجات",
  "Chaque nombre d'un constat doit être une valeur publiée, son année ou un écart entre deux valeurs du même indicateur.":
    "كل رقم في استنتاج يجب أن يكون قيمة منشورة أو سنتها أو فجوة بين قيمتين للمؤشر نفسه.",
  "Audités": "مدقَّقة",
  "Acceptés": "مقبولة",
  "Rejetés": "مرفوضة",
  "Non auditables": "غير قابلة للتدقيق",
  "Accepté": "مقبول",
  "Rejeté": "مرفوض",
  "Non auditable": "غير قابل للتدقيق",
  "Comment un chiffre est vérifié": "كيف يُتحقق من رقم",
  "Choisissez un indicateur, un pays et une année : la valeur est retracée jusqu'au fichier source.":
    "اختر مؤشرًا وبلدًا وسنة: تُتتبَّع القيمة حتى الملف المصدر.",
  "Valeur publiée": "القيمة المنشورة",
  "indisponible ({reason})": "غير متاح ({reason})",
  "non observée": "غير مرصودة",
  "Sources lues": "المصادر المقروءة",
  "Aucune observation : la valeur reste vide.": "لا توجد ملاحظة: تبقى القيمة فارغة.",
  "{source} · fichier {file} · colonne {column} · texte brut « {text} »":
    "{source} · الملف {file} · العمود {column} · النص الخام «{text}»",
  "Formule": "الصيغة",
  "Valeur recalculée": "القيمة المعاد حسابها",
  "version des données {id}": "إصدار البيانات {id}",
  "catalogue {version}": "الكتالوج {version}",
  "Contrôles": "الفحوص",
  "{passed} contrôles réussis sur cette valeur": "{passed} فحص ناجح على هذه القيمة",
  "à noter : {list}": "للملاحظة: {list}",
  "Publication": "النشر",
  "Valeur {status}": "القيمة {status}",
  "Test de l'Auditor par injection de fautes": "اختبار المدقق بحقن الأخطاء",
  "Des erreurs sont introduites dans une copie des données ; l'Auditor doit les détecter. Évaluation du {date}.":
    "تُحقن أخطاء في نسخة من البيانات ويجب على المدقق اكتشافها. تقييم بتاريخ {date}.",
  "{detected} / {total} détectées": "{detected} / {total} مكتشفة",
  "Résultat antérieur au dernier audit : relancez scripts/evaluate_auditor.py pour le mettre à jour.":
    "النتيجة أقدم من آخر تدقيق: أعد تشغيل scripts/evaluate_auditor.py لتحديثها.",
  "Aucune évaluation enregistrée.": "لا يوجد تقييم مسجل.",
  "Faute injectée": "الخطأ المحقون",
  "Contrôle attendu": "الفحص المتوقع",
  "Détectée": "مكتشف",
  "Verdict obtenu": "الحكم المحصل عليه",
  "Oui": "نعم",
  "Non": "لا",
  "Erreur HTTP {status}": "خطأ HTTP {status}",
  "Statut": "الحالة",
  "Audit réussi": "نجح التدقيق",
  "Audit réussi avec avertissements": "نجح التدقيق مع تحذيرات",
  "Audit en échec": "فشل التدقيق",
  "Avertissement": "تحذير",
  "bloquée": "محجوبة",
  "non évaluée": "غير مقيمة",

  // -------------------------------------------------------------- mes données
  "Structure": "البنية",
  "Vérification": "التحقق",
  "Confirmation": "التأكيد",
  "Étapes": "الخطوات",
  "Annuler": "إلغاء",
  "Retour": "رجوع",
  "Continuer": "متابعة",
  "Traitement…": "جارٍ المعالجة…",
  "Années": "السنوات",
  "Indicateurs": "المؤشرات",
  "Mise à jour": "آخر تحديث",
  "Score qualité": "درجة الجودة",
  "Exclue": "مستبعدة",
  "Aucune source ajoutée": "لم يُضف أي مصدر",
  "Ajoutez un fichier CSV pour comparer vos propres chiffres, à côté du tableau de bord officiel.":
    "أضف ملف CSV لمقارنة أرقامك إلى جانب لوحة المعلومات الرسمية.",
  "Ajoutez vos propres fichiers CSV. Ils restent séparés des chiffres officiels : jamais mélangés aux cartes, à l'audit officiel ni aux réponses d'Ask Finova.":
    "أضف ملفات CSV الخاصة بك. تبقى منفصلة عن الأرقام الرسمية: لا تُخلط أبدًا بالبطاقات أو التدقيق الرسمي أو أجوبة Ask Finova.",
  "Voir les données": "عرض البيانات",
  "Remplacer le fichier": "استبدال الملف",
  "Supprimer": "حذف",
  "Supprimer {name}": "حذف {name}",
  "Supprimer « {name} » ? Ses données seront retirées de l'entrepôt et le tableau de bord sera recalculé. La copie du fichier est conservée.":
    "حذف «{name}»؟ ستُزال بياناته من المستودع وستُعاد لوحة المعلومات. تُحفظ نسخة الملف.",
  "Supprimer et recalculer": "حذف وإعادة الحساب",
  "Colonne d'année": "عمود السنة",
  "Colonne d'indicateur": "عمود المؤشر",
  "Ignorer": "تجاهل",
  "Format long : une ligne par observation": "تنسيق طويل: سطر لكل ملاحظة",
  "Années en colonnes": "السنوات في أعمدة",
  "Indicateurs en colonnes": "المؤشرات في أعمدة",
  "fraction (0 à 1)": "كسر (من 0 إلى 1)",
  "par 100 000 adultes": "لكل 100 ألف بالغ",
  "par 1 000 adultes": "لكل 1000 بالغ",
  "nombre": "عدد",
  "monnaie": "عملة",
  "monnaie ({code})": "عملة ({code})",
  "Collecte des sources": "جمع المصادر",
  "Profil des colonnes": "تحليل الأعمدة",
  "Chargement dans l'entrepôt": "التحميل في المستودع",
  "Calcul des indicateurs": "حساب المؤشرات",
  "Audit indépendant": "تدقيق مستقل",
  "Mise à jour du tableau de bord": "تحديث لوحة المعلومات",
  "point-virgule (;)": "فاصلة منقوطة (;)",
  "virgule (,)": "فاصلة (,)",
  "tabulation": "جدولة",
  "barre verticale (|)": "شريط عمودي (|)",
  "Remplacement du fichier de la source « {name} ».":
    "استبدال ملف المصدر «{name}».",
  "Remplacement du fichier de la source « {name} »":
    "استبدال ملف المصدر «{name}»",
  "Choisissez une unité pour chaque indicateur": "اختر وحدة لكل مؤشر",
  "Ajouter et recalculer": "إضافة وإعادة الحساب",
  "Glissez votre fichier CSV ici": "اسحب ملف CSV هنا",
  "ou": "أو",
  "Choisir un fichier": "اختيار ملف",
  "Format accepté : CSV (séparateur ; , tabulation ou |) · {size} Mo maximum · le fichier n'est jamais exécuté ni ouvert par un tableur.":
    "الصيغة المقبولة: CSV (فاصل ; أو , أو جدولة أو |) · {size} ميغابايت كحد أقصى · لا يُنفَّذ الملف ولا يُفتح بجدول بيانات.",
  "Trois dispositions reconnues": "ثلاثة تنسيقات معروفة",
  "Format long": "تنسيق طويل",
  "Une configuration enregistrée correspond à ces colonnes (« {name} »).":
    "يوجد إعداد محفوظ يطابق هذه الأعمدة («{name}»).",
  "Réutiliser la configuration enregistrée": "إعادة استخدام الإعداد المحفوظ",
  "Fichier : {name} · {rows} ligne(s)": "الملف: {name} · {rows} سطر",
  "Séparateur : {value}": "الفاصل: {value}",
  "Décimale : {value}": "الفاصلة العشرية: {value}",
  "virgule": "فاصلة",
  "point": "نقطة",
  "Disposition à préciser": "التنسيق غير محدد",
  "Pays : {kind} ({share} % reconnus)": "البلدان: {kind} ({share}% معروفة)",
  "codes ISO3": "رموز ISO3",
  "noms de pays": "أسماء البلدان",
  "Nom de la source": "اسم المصدر",
  "Minuscules, chiffres et _ (ex. clients_microfinance).":
    "أحرف صغيرة وأرقام و _ (مثال clients_microfinance).",
  "Colonne": "العمود",
  "Exemples": "أمثلة",
  "Preuve": "الدليل",
  "Rôle de la colonne {name}": "دور العمود {name}",
  "L'unité n'est jamais devinée : choisissez celle des valeurs telles qu'elles sont écrites dans le fichier. Aucune conversion n'est faite sauf si vous la demandez.":
    "لا تُخمَّن الوحدة أبدًا: اختر وحدة القيم كما كُتبت في الملف. لا يتم أي تحويل إلا إذا طلبته.",
  "Code": "الرمز",
  "Libellé": "التسمية",
  "Unité (obligatoire)": "الوحدة (إلزامية)",
  "Conversion": "التحويل",
  "Libellé de {code}": "تسمية {code}",
  "Unité de {code}": "وحدة {code}",
  "Monnaie de {code}": "عملة {code}",
  "ex. TND": "مثال TND",
  "— à choisir —": "— اختر —",
  "aucune": "لا شيء",
  "pourcentage → fraction": "نسبة مئوية → كسر",
  "Indicateur officiel comparable (facultatif)": "مؤشر رسمي قابل للمقارنة (اختياري)",
  "choisissez d'abord l'unité": "اختر الوحدة أولًا",
  "chargement…": "جارٍ التحميل…",
  "aucun indicateur officiel dans cette unité": "لا يوجد مؤشر رسمي بهذه الوحدة",
  "Indicateur officiel comparable à {code}": "مؤشر رسمي قابل للمقارنة بـ {code}",
  "aucun": "لا يوجد",
  "Définition officielle : {value}": "التعريف الرسمي: {value}",
  "Dénominateur : {value}": "المقام: {value}",
  "Mon indicateur mesure la même chose (même population, même définition)":
    "مؤشري يقيس الشيء نفسه (نفس السكان، نفس التعريف)",
  "Case non cochée : l'indicateur comparable ne sera pas enregistré.":
    "المربع غير محدد: لن يُحفظ المؤشر القابل للمقارنة.",
  "« {name} » · {count} valeur(s)": "«{name}» · {count} قيمة",
  "Lignes retenues": "الأسطر المحتفظ بها",
  "{count} valeur(s)": "{count} قيمة",
  "Pays reconnus": "بلدان معروفة",
  "Réussi": "ناجح",
  "Échec": "فاشل",
  "score {score}": "النتيجة {score}",
  "Pays non reconnus": "بلدان غير معروفة",
  "Indiquez un code ISO3 (ex. MRT) ou laissez vide pour ignorer ces lignes.":
    "أدخل رمز ISO3 (مثال MRT) أو اتركه فارغًا لتجاهل هذه الأسطر.",
  "ISO3 ou vide = ignorer": "ISO3 أو فارغ = تجاهل",
  "Appliquer et revérifier": "تطبيق وإعادة التحقق",
  "Aperçu (10 premières valeurs)": "معاينة (أول 10 قيم)",
  "Unité": "الوحدة",
  "Texte du fichier": "نص الملف",
  "Ligne": "السطر",
  "ligne {line} « {text} »": "السطر {line} «{text}»",
  "{count} valeur(s) non numérique(s) ignorée(s) : {examples}":
    "تم تجاهل {count} قيمة غير رقمية: {examples}",
  "{count} doublon(s) identique(s) retiré(s).": "أُزيل {count} تكرار مطابق.",
  "{count} année(s) invalide(s) ignorée(s).": "تم تجاهل {count} سنة غير صالحة.",
  "Contrôle qualité : {message}": "مراقبة الجودة: {message}",
  "Configuration enregistrée réutilisée : « {name} ».":
    "أُعيد استخدام الإعداد المحفوظ: «{name}».",
  "Indicateurs : {list}.": "المؤشرات: {list}.",
  "{values} valeur(s), {countries} pays, années {range}.":
    "{values} قيمة، {countries} بلدًا، السنوات {range}.",
  "Ajouter la source « {name} »": "إضافة المصدر «{name}»",
  "Remplacer le fichier de la source « {name} »":
    "استبدال ملف المصدر «{name}»",
  "Recalcul hors ligne": "إعادة حساب دون اتصال",
  "Recalcul hors ligne en cours (sources officielles reprises du snapshot publié) — étape : {step}":
    "إعادة حساب دون اتصال جارية (المصادر الرسمية مأخوذة من اللقطة المنشورة) — الخطوة: {step}",
  "Suppression et recalcul": "حذف وإعادة حساب",
  "Ajout et recalcul": "إضافة وإعادة حساب",
  "L'opération continue même si vous rechargez la page.":
    "تستمر العملية حتى لو أعدت تحميل الصفحة.",
  "{seconds} s": "{seconds} ث",
  "Source intégrée à l'entrepôt": "المصدر مدمج في المستودع",
  "Recalcul terminé": "اكتملت إعادة الحساب",
  "Aucune donnée nouvelle": "لا توجد بيانات جديدة",
  "Source retirée": "أُزيل المصدر",
  "Source exclue par le contrôle qualité": "استُبعد المصدر بمراقبة الجودة",
  "Audit en échec : version précédente conservée":
    "فشل التدقيق: احتُفظ بالإصدار السابق",
  "Le recalcul a échoué": "فشلت إعادة الحساب",
  "Voir mes sources": "عرض مصادري",
  "← Mes sources": "← بياناتي",
  "Aucune valeur publiée": "لا توجد قيمة منشورة",
  "La source n'est pas (ou plus) intégrée à l'entrepôt : voir son statut dans la liste.":
    "المصدر غير مدمج (أو لم يعد مدمجًا) في المستودع: راجع حالته في القائمة.",
  "Provenance": "المصدر",
  "Valeurs importées par l'utilisateur, publiées telles quelles : elles ne sont pas des chiffres officiels.":
    "قيم أدخلها المستخدم ونُشرت كما هي: ليست أرقامًا رسمية.",
  "Le fichier est copié dans data/uploads/, puis le pipeline est recalculé (contrôle qualité, entrepôt, audit, tableau de bord). Les sources officielles ne sont pas retéléchargées.":
    "يُنسخ الملف إلى data/uploads/، ثم تُعاد معالجة المسار (مراقبة الجودة، المستودع، التدقيق، لوحة المعلومات). لا تُنزَّل المصادر الرسمية مرة أخرى.",
  "Les chiffres officiels du tableau de bord ne changent pas : vos données restent séparées des chiffres officiels (cette page, le bloc « Vos indicateurs face aux données officielles », Ask Finova en mode local).":
    "لا تتغير أرقام لوحة المعلومات الرسمية: تبقى بياناتك منفصلة عن الأرقام الرسمية (هذه الصفحة، كتلة «مؤشراتك مقابل البيانات الرسمية»، Ask Finova في الوضع المحلي).",

  // --------------------------------------------------------------- agents / divers
  "Agents": "الوكلاء",
  "Route 2 {id}": "المسار 2 {id}",
  "Route 2 non exécutée": "المسار 2 لم يُنفَّذ",
  "Chargement du dernier run…": "جارٍ تحميل آخر تشغيل…",
  "Recalcul en cours…": "جارٍ إعادة الحساب…",
  "Recalculer les données": "إعادة حساب البيانات",
  "démarrage": "البدء",
  "Aucune donnée nouvelle : le contenu est identique à la version publiée. Les agents suivants sont ignorés.":
    "لا توجد بيانات جديدة: المحتوى مطابق للإصدار المنشور. يتم تجاهل الوكلاء التالين.",
  "terminé {date} ({seconds} s)": "اكتمل {date} ({seconds} ث)",
  "LLM optionnel": "LLM اختياري",
  "déterministe": "حتمي",
  "appels LLM : {count}": "استدعاءات LLM: {count}",
  "terminé": "مكتمل",
  "en cours…": "جارٍ…",
  "ignoré": "متجاهل",
  "erreur": "خطأ",
  "réussi": "ناجح",
  "à la demande": "عند الطلب",
  "non exécuté": "لم يُنفَّذ",
  "Route 1 — fiabiliser les données": "المسار 1 — تعزيز موثوقية البيانات",
  "Route 2 — analyser et publier": "المسار 2 — التحليل والنشر",
  "Interface": "الواجهة",
  "Vos indicateurs face aux données officielles": "مؤشراتك مقابل البيانات الرسمية",
  "Votre indicateur": "مؤشرك",
  "Indicateur officiel": "المؤشر الرسمي",
  "aucune valeur": "لا توجد قيمة",
  "aucune valeur approuvée": "لا توجد قيمة معتمدة",
  "Définition officielle : {definition}": "التعريف الرسمي: {definition}",
  "Pistes de recommandation": "مسارات التوصية",
  "Règles fixes appliquées aux valeurs auditées · association, pas causalité":
    "قواعد ثابتة مطبقة على القيم المدققة · ارتباط وليس سببية",
  "{count} piste": "{count} مسار",
  "{count} pistes": "{count} مسارات",
  "{count} comparaisons": "{count} مقارنة",
  "Pistes indisponibles : {detail}": "المسارات غير متاحة: {detail}",
  "Chargement des pistes…": "جارٍ تحميل المسارات…",
  "Aucune règle déclenchée pour {country} en {year} : aucun écart ne dépasse les seuils.":
    "لم تُفعَّل أي قاعدة لـ {country} في {year}: لا تتجاوز أي فجوة العتبات.",
  "Groupe cible : {group}": "المجموعة المستهدفة: {group}",
  "Règle : {rule}": "القاعدة: {rule}",
  "Sources": "المصادر",
  "approuvée": "معتمدة",
  "approuvée avec réserve": "معتمدة مع تحفظ",
  "moyenne des pairs": "متوسط الأقران",
  "avec réserve": "مع تحفظ",
  "À partir de vos données": "انطلاقًا من بياناتك",
  "Même logique de règles fixes, appliquée à vos indicateurs déclarés comparables, seulement quand votre année est celle de la valeur officielle. Comparaison indicative.":
    "المنطق نفسه للقواعد الثابتة، مطبقًا على مؤشراتك المعلنة قابلة للمقارنة، فقط عندما تكون سنتك سنة القيمة الرسمية. مقارنة إرشادية.",
  "Préparation du PDF…": "جارٍ إعداد PDF…",
  "Télécharger le rapport (PDF)": "تنزيل التقرير (PDF)",
  "Ajoute une annexe séparée avec vos données.": "يضيف ملحقًا منفصلًا ببياناتك.",
  "Inclure l'annexe : vos données": "تضمين الملحق: بياناتك",
  "Session expirée : reconnectez-vous pour télécharger le rapport.":
    "انتهت الجلسة: أعد تسجيل الدخول لتنزيل التقرير.",
  "Téléchargement impossible (HTTP {status}).": "تعذّر التنزيل (HTTP {status}).",
  "Téléchargement impossible.": "تعذّر التنزيل.",
  "validé": "مقبول",
  "Constats et pistes de recommandation — {country}, {year}":
    "الاستنتاجات ومسارات التوصية — {country}، {year}",
  "Combien d'adultes ont un compte ?": "كم عدد البالغين الذين يمتلكون حسابًا؟",
};

export function t(
  fr: string,
  vars?: Record<string, string | number | null | undefined>,
): string {
  const lang = getLang();
  const dict = lang === "en" ? EN : lang === "ar" ? AR : null;
  let out = (dict && dict[fr]) || fr;
  if (vars) {
    for (const [key, value] of Object.entries(vars)) {
      out = out.split(`{${key}}`).join(
        value === null || value === undefined ? "—" : String(value),
      );
    }
  }
  return out;
}

// Libellés de données (pays, séries, axes) : traduction exacte, sans toucher aux nombres.
const DATA_EN: Record<string, string> = {
  "Tunisie": "Tunisia",
  "Algérie": "Algeria",
  "Égypte": "Egypt",
  "Jordanie": "Jordan",
  "Maroc": "Morocco",
  "Tunisia": "Tunisia",
  "Monde": "World",
  "MENA hors revenu eleve": "MENA excluding high income",
  "MENA hors revenu élevé": "MENA excluding high income",
  "Revenu intermediaire inferieur": "Lower middle income",
  "Revenu intermédiaire inférieur": "Lower middle income",
  "Moyenne des pairs (DZA, EGY, JOR, MAR)": "Peer average (DZA, EGY, JOR, MAR)",
  "Pairs régionaux — détention d'un compte": "Regional peers — account ownership",
  "Tunisia — détention d'un compte": "Tunisia — account ownership",
  "Part des adultes (%)": "Share of adults (%)",
  "Année Findex": "Findex year",
  "Indice (2017 = 100)": "Index (2017 = 100)",
  "Écart (points de pourcentage)": "Gap (percentage points)",
  "Écart en points de pourcentage, année observée 2024.":
    "Gap in percentage points, observed year 2024.",
  "TND par mois": "TND per month",
  "Pour 100 000 adultes": "Per 100,000 adults",
  "ATMs / 100k adultes": "ATMs / 100k adults",
  "ATMs (offre)": "ATMs (supply)",
  "Paiements numériques (demande)": "Digital payments (demand)",
  "Compte": "Account",
  "Paiement numérique": "Digital payment",
  "Épargne formelle (fin17a)": "Formal savings",
  "Emprunt formel (fin22a)": "Formal borrowing",
  "Épargne — toute forme": "Savings — any form",
  "Emprunt — toute forme": "Borrowing — any form",
  "Détention d'un compte": "Account ownership",
  "Paiement numérique effectué ou reçu": "Digital payment made or received",
  "Agences bancaires": "Bank branches",
  "Distributeurs automatiques": "ATMs",
  "Habitat": "Housing",
  "Genre": "Gender",
  "Revenu": "Income",
  "Éducation": "Education",
  "Milieu": "Location",
  "Âge": "Age",
  "Marché du travail": "Labour market",
  "Femmes": "Women",
  "Hommes": "Men",
  "Rural": "Rural",
  "Urbain": "Urban",
  "Taux de détention d'un compte": "Account ownership rate",
  "Détention d'un compte par groupe": "Account ownership by group",
  "Détention d'un compte par vague Findex": "Account ownership by Findex wave",
  "Détention d'un compte : urbain vs rural": "Account ownership: urban vs rural",
  "Du compte à l'usage formel": "From account to formal use",
  "Usage formel et usage informel": "Formal and informal use",
  "Formel vs tout moyen confondu": "Formal vs any means",
  "Réseau physique (2015-2024)": "Physical network (2015-2024)",
  "Offre et demande, base 100 en 2017": "Supply and demand, 2017 = 100",
  "Obstacles à l'ouverture d'un compte": "Barriers to opening an account",
  "Barrières à l'ouverture d'un compte": "Barriers to opening an account",
  "Trop éloigné": "Too far",
  "Trop cher": "Too expensive",
  "Documents manquants": "Missing documents",
  "Fonds insuffisants": "Insufficient funds",
  "Un proche en a déjà un": "A relative already has one",
  "Manque de confiance": "Lack of trust",
  "Écart femmes-hommes": "Gender gap",
  "Écart de revenu": "Income gap",
  "Écart d'éducation": "Education gap",
  "Écart de marché du travail": "Labour market gap",
  "Écart entre milieux": "Urban–rural gap",
  "Ordres de grandeur : contexte, pas des KPI d'inclusion.":
    "Orders of magnitude: context, not inclusion indicators.",
  "Contexte macro": "Macro context",
  "Contexte de revenu": "Income context",
  "Contexte INS 2021": "INS context 2021",
  "Contexte vérifié": "Verified context",
  "PIB par habitant": "GDP per capita",
  "Taux de change officiel moyen 2024": "Official average exchange rate 2024",
  "Ordre de grandeur mensuel (dérivé)": "Monthly order of magnitude (derived)",
  "Population active": "Labour force",
  "Hors population active": "Outside the labour force",
  "Primaire ou moins": "Primary or less",
  "Secondaire ou plus": "Secondary or more",
  "40 % les plus pauvres": "Poorest 40%",
  "60 % les plus riches": "Richest 60%",
  "Compte — Genre : Femmes": "Account — Gender: Women",
  "Compte — Genre : Hommes": "Account — Gender: Men",
  "Compte — Revenu : 40 % les plus pauvres": "Account — Income: poorest 40%",
  "Compte — Revenu : 60 % les plus riches": "Account — Income: richest 60%",
  "Compte — Éducation : Primaire ou moins": "Account — Education: primary or less",
  "Compte — Éducation : Secondaire ou plus": "Account — Education: secondary or more",
  "Compte — Marché du travail : Hors population active": "Account — Labour market: outside the labour force",
  "Compte — Marché du travail : Population active": "Account — Labour market: labour force",
  "Compte — Âge : 15-24 ans": "Account — Age: 15–24",
  "Compte — Âge : 25 ans et +": "Account — Age: 25+",
  "Compte — Milieu : Rural": "Account — Location: Rural",
  "Compte — Milieu : Urbain": "Account — Location: Urban",
  "Compte — milieu rural": "Account — rural area",
  "Compte — milieu urbain": "Account — urban area",
  "Écart femmes-hommes de détention d'un compte": "Account ownership gender gap",
  "Écart de revenu de détention d'un compte": "Account ownership income gap",
  "Écart d'éducation de détention d'un compte": "Account ownership education gap",
  "Écart d'activité de détention d'un compte": "Account ownership labour market gap",
  "Écart d'âge de détention d'un compte": "Account ownership age gap",
  "Écart entre milieux de détention d'un compte": "Account ownership urban–rural gap",
  "Détention d'un compte - hommes": "Account ownership - men",
  "Détention d'un compte - femmes": "Account ownership - women",
  "Détention d'un compte - 60 % des ménages les plus riches":
    "Account ownership - richest 60% of households",
  "Détention d'un compte - 40 % des ménages les plus pauvres":
    "Account ownership - poorest 40% of households",
  "Détention d'un compte - niveau secondaire ou plus":
    "Account ownership - secondary education or more",
  "Détention d'un compte - niveau primaire ou moins":
    "Account ownership - primary education or less",
  "Détention d'un compte - population active": "Account ownership - labour force",
  "Détention d'un compte - hors population active":
    "Account ownership - outside the labour force",
  "Détention d'un compte - adultes de 25 ans et plus": "Account ownership - adults aged 25+",
  "Détention d'un compte - adultes de 15 à 24 ans": "Account ownership - adults aged 15–24",
  "Détention d'un compte - adultes ruraux": "Account ownership - rural adults",
  "Détention d'un compte - adultes urbains": "Account ownership - urban adults",
  "Mesure": "Measure",
  "femmes": "women",
  "adultes du primaire ou moins": "adults with primary education or less",
  "adultes hors population active": "adults outside the labour force",
  "adultes ruraux": "rural adults",
  "adultes de 15 à 24 ans": "adults aged 15 to 24",
  "jeunes de 15 à 24 ans": "young people aged 15 to 24",
  "adultes sans compte dont un proche en possède un":
    "unbanked adults whose relative already has one",
  "adultes sans compte méfiants envers les institutions financières":
    "unbanked adults who distrust financial institutions",
  "adultes qui ne paient pas encore par voie numérique":
    "adults who do not pay digitally yet",
  "Écart urbain-rural de détention d'un compte": "Account ownership urban–rural gap",
  "Détention d'un compte - milieu urbain": "Account ownership - urban area",
  "Détention d'un compte - milieu rural": "Account ownership - rural area",
  "Pas de compte : un membre de la famille en a déjà un":
    "No account: a family member already has one",
  "Pas de compte : manque de confiance dans les institutions financières":
    "No account: lack of trust in financial institutions",
  "paiement numérique effectué ou reçu": "digital payment made or received",
  "Densité des distributeurs automatiques": "Automated teller machine density",
  "Densité des agences des banques commerciales": "Commercial bank branch density",
  "Déposants des banques commerciales": "Commercial bank depositors",
  "Emprunteurs des banques commerciales": "Commercial bank borrowers",
  "Encours des prêts des banques commerciales": "Commercial bank loans outstanding",
  "Encours des dépôts des banques commerciales": "Commercial bank deposits outstanding",
  "Comptes de dépôt des banques commerciales": "Commercial bank deposit accounts",
  "Épargne (toute forme)": "Savings (any form)",
  "Emprunt (toute forme)": "Borrowing (any form)",
  "Épargne auprès d'une institution financière": "Savings at a financial institution",
  "Emprunt auprès d'une institution financière": "Borrowing from a financial institution",
  "Fonds d'urgence mobilisables en 30 jours": "Emergency funds available within 30 days",
  "Pas de compte : pas assez d'argent": "No account: not enough money",
  "Pas de compte : documents requis manquants": "No account: missing required documents",
  "Pas de compte : services financiers trop chers": "No account: financial services too expensive",
  "Pas de compte : institutions financières trop éloignées": "No account: financial institutions too far away",
  "Source principale des fonds d'urgence : prêt (banque, employeur ou prêteur privé)":
    "Main source of emergency funds: loan (bank, employer or private lender)",
  "Source principale des fonds d'urgence : épargne": "Main source of emergency funds: savings",
  "Compte inactif": "Inactive account",
  "Comptes de prêt des banques commerciales": "Commercial bank loan accounts",
  "Compte de monnaie mobile": "Mobile money account",
  "Adultes sans compte": "Unbanked adults",
  "Ask Finova": "Ask Finova",
};

const DATA_AR: Record<string, string> = {
  "Tunisie": "تونس",
  "Algérie": "الجزائر",
  "Égypte": "مصر",
  "Jordanie": "الأردن",
  "Maroc": "المغرب",
  "Tunisia": "تونس",
  "Monde": "العالم",
  "MENA hors revenu eleve": "الشرق الأوسط وشمال إفريقيا دون الدخل المرتفع",
  "MENA hors revenu élevé": "الشرق الأوسط وشمال إفريقيا دون الدخل المرتفع",
  "Revenu intermediaire inferieur": "الدخل المتوسط الأدنى",
  "Revenu intermédiaire inférieur": "الدخل المتوسط الأدنى",
  "Moyenne des pairs (DZA, EGY, JOR, MAR)": "متوسط الأقران (DZA, EGY, JOR, MAR)",
  "Pairs régionaux — détention d'un compte": "الأقران الإقليميون — ملكية حساب",
  "Tunisia — détention d'un compte": "تونس — ملكية حساب",
  "Part des adultes (%)": "نسبة البالغين (%)",
  "Année Findex": "سنة Findex",
  "Indice (2017 = 100)": "المؤشر (2017 = 100)",
  "Écart (points de pourcentage)": "الفجوة (نقاط مئوية)",
  "Écart en points de pourcentage, année observée 2024.":
    "الفجوة بنقاط مئوية، السنة المرصودة 2024.",
  "TND par mois": "دينار شهريًا",
  "Pour 100 000 adultes": "لكل 100 ألف بالغ",
  "ATMs / 100k adultes": "صرافات آلية / 100 ألف بالغ",
  "ATMs (offre)": "الصرافات (العرض)",
  "Paiements numériques (demande)": "المدفوعات الرقمية (الطلب)",
  "Compte": "حساب",
  "Paiement numérique": "دفع رقمي",
  "Épargne formelle (fin17a)": "ادخار رسمي",
  "Emprunt formel (fin22a)": "اقتراض رسمي",
  "Épargne — toute forme": "ادخار — بأي شكل",
  "Emprunt — toute forme": "اقتراض — بأي شكل",
  "Détention d'un compte": "ملكية حساب",
  "Paiement numérique effectué ou reçu": "دفع رقمي أُجري أو استُلم",
  "Agences bancaires": "الفروع البنكية",
  "Distributeurs automatiques": "الصرافات الآلية",
  "Genre": "الجنس",
  "Revenu": "الدخل",
  "Éducation": "التعليم",
  "Milieu": "بيئة الإقامة",
  "Âge": "العمر",
  "Marché du travail": "سوق العمل",
  "Femmes": "النساء",
  "Hommes": "الرجال",
  "Rural": "الريف",
  "Urbain": "المدن",
  "Taux de détention d'un compte": "معدل ملكية الحساب",
  "Détention d'un compte par groupe": "ملكية الحساب حسب المجموعة",
  "Détention d'un compte par vague Findex": "ملكية الحساب حسب موجة Findex",
  "Détention d'un compte : urbain vs rural": "ملكية الحساب: المدن مقابل الريف",
  "Du compte à l'usage formel": "من الحساب إلى الاستخدام الرسمي",
  "Usage formel et usage informel": "الاستخدام الرسمي وغير الرسمي",
  "Formel vs tout moyen confondu": "الرسمي مقابل كل الوسائل",
  "Réseau physique (2015-2024)": "الشبكة الفيزيائية (2015-2024)",
  "Offre et demande, base 100 en 2017": "العرض والطلب، أساس 100 في 2017",
  "Obstacles à l'ouverture d'un compte": "عوائق فتح حساب",
  "Barrières à l'ouverture d'un compte": "عوائق فتح حساب",
  "Trop éloigné": "بعيد جدًا",
  "Trop cher": "مكلف جدًا",
  "Documents manquants": "وثائق ناقصة",
  "Fonds insuffisants": "أموال غير كافية",
  "Un proche en a déjà un": "أحد الأقارب لديه حساب",
  "Manque de confiance": "غياب الثقة",
  "Écart femmes-hommes": "الفجوة بين الجنسين",
  "Écart de revenu": "فجوة الدخل",
  "Écart d'éducation": "فجوة التعليم",
  "Écart de marché du travail": "فجوة سوق العمل",
  "Écart entre milieux": "الفجوة بين المدن والأرياف",
  "Ordres de grandeur : contexte, pas des KPI d'inclusion.":
    "أحجام تقريبية: سياق وليست مؤشرات إدماج مالي.",
  "Contexte macro": "السياق الكلي",
  "Contexte de revenu": "سياق الدخل",
  "Contexte INS 2021": "سياق المعهد الوطني للإحصاء 2021",
  "Contexte vérifié": "سياق متحقق منه",
  "PIB par habitant": "الناتج المحلي للفرد",
  "Taux de change officiel moyen 2024": "سعر الصرف الرسمي المتوسط 2024",
  "Ordre de grandeur mensuel (dérivé)": "حجم شهري تقريبي (محسوب)",
  "Population active": "القوى العاملة",
  "Hors population active": "خارج القوى العاملة",
  "Primaire ou moins": "ابتدائي أو أقل",
  "Secondaire ou plus": "ثانوي أو أكثر",
  "40 % les plus pauvres": "أفقر 40%",
  "60 % les plus riches": "أغنى 60%",
  "Compte — Genre : Femmes": "حساب — الجنس: النساء",
  "Compte — Genre : Hommes": "حساب — الجنس: الرجال",
  "Compte — Revenu : 40 % les plus pauvres": "حساب — الدخل: أفقر 40%",
  "Compte — Revenu : 60 % les plus riches": "حساب — الدخل: أغنى 60%",
  "Compte — Éducation : Primaire ou moins": "حساب — التعليم: ابتدائي أو أقل",
  "Compte — Éducation : Secondaire ou plus": "حساب — التعليم: ثانوي أو أكثر",
  "Compte — Marché du travail : Hors population active": "حساب — سوق العمل: خارج القوى العاملة",
  "Compte — Marché du travail : Population active": "حساب — سوق العمل: القوى العاملة",
  "Compte — Âge : 15-24 ans": "حساب — العمر: 15-24",
  "Compte — Âge : 25 ans et +": "حساب — العمر: 25 سنة فأكثر",
  "Compte — Milieu : Rural": "حساب — بيئة الإقامة: الريف",
  "Compte — Milieu : Urbain": "حساب — بيئة الإقامة: المدن",
  "Compte — milieu rural": "حساب — الريف",
  "Compte — milieu urbain": "حساب — المدن",
  "Écart femmes-hommes de détention d'un compte": "فجوة ملكية الحساب بين الجنسين",
  "Écart de revenu de détention d'un compte": "فجوة ملكية الحساب حسب الدخل",
  "Écart d'éducation de détention d'un compte": "فجوة ملكية الحساب حسب التعليم",
  "Écart d'activité de détention d'un compte": "فجوة ملكية الحساب حسب سوق العمل",
  "Écart d'âge de détention d'un compte": "فجوة ملكية الحساب حسب العمر",
  "Écart entre milieux de détention d'un compte": "فجوة ملكية الحساب بين المدن والأرياف",
  "Détention d'un compte - hommes": "ملكية الحساب - الرجال",
  "Détention d'un compte - femmes": "ملكية الحساب - النساء",
  "Détention d'un compte - 60 % des ménages les plus riches":
    "ملكية الحساب - أغنى 60% من الأسر",
  "Détention d'un compte - 40 % des ménages les plus pauvres":
    "ملكية الحساب - أفقر 40% من الأسر",
  "Détention d'un compte - niveau secondaire ou plus":
    "ملكية الحساب - تعليم ثانوي أو أكثر",
  "Détention d'un compte - niveau primaire ou moins":
    "ملكية الحساب - تعليم ابتدائي أو أقل",
  "Détention d'un compte - population active": "ملكية الحساب - القوى العاملة",
  "Détention d'un compte - hors population active":
    "ملكية الحساب - خارج القوى العاملة",
  "Détention d'un compte - adultes de 25 ans et plus": "ملكية الحساب - البالغون 25 سنة فأكثر",
  "Détention d'un compte - adultes de 15 à 24 ans": "ملكية الحساب - البالغون 15-24 سنة",
  "Détention d'un compte - adultes ruraux": "ملكية الحساب - البالغون في الريف",
  "Détention d'un compte - adultes urbains": "ملكية الحساب - البالغون في المدن",
  "Mesure": "مقياس",
  "femmes": "النساء",
  "adultes du primaire ou moins": "البالغون بتعليم ابتدائي أو أقل",
  "adultes hors population active": "البالغون خارج القوى العاملة",
  "adultes ruraux": "البالغون في الريف",
  "adultes de 15 à 24 ans": "البالغون من 15 إلى 24 سنة",
  "jeunes de 15 à 24 ans": "الشباب من 15 إلى 24 سنة",
  "adultes sans compte dont un proche en possède un":
    "البالغون بلا حساب ممن لديه قريب يملك حسابًا",
  "adultes sans compte méfiants envers les institutions financières":
    "البالغون بلا حساب الذين لا يثقون بالمؤسسات المالية",
  "adultes qui ne paient pas encore par voie numérique":
    "البالغون الذين لا يدفعون رقميًا بعد",
  "Écart urbain-rural de détention d'un compte": "فجوة ملكية الحساب بين المدن والأرياف",
  "Détention d'un compte - milieu urbain": "ملكية الحساب - المدن",
  "Détention d'un compte - milieu rural": "ملكية الحساب - الريف",
  "Pas de compte : un membre de la famille en a déjà un":
    "بلا حساب: أحد أفراد الأسرة لديه حساب بالفعل",
  "Pas de compte : manque de confiance dans les institutions financières":
    "بلا حساب: انعدام الثقة في المؤسسات المالية",
  "paiement numérique effectué ou reçu": "دفع رقمي أُجري أو استُلم",
  "Densité des distributeurs automatiques": "كثافة الصرافات الآلية",
  "Densité des agences des banques commerciales": "كثافة فروع البنوك التجارية",
  "Déposants des banques commerciales": "المودعون في البنوك التجارية",
  "Emprunteurs des banques commerciales": "المقترضون من البنوك التجارية",
  "Encours des prêts des banques commerciales": "قروض البنوك التجارية القائمة",
  "Encours des dépôts des banques commerciales": "ودائع البنوك التجارية القائمة",
  "Comptes de dépôt des banques commerciales": "حسابات الودائع في البنوك التجارية",
  "Épargne (toute forme)": "الادخار (بأي شكل)",
  "Emprunt (toute forme)": "الاقتراض (بأي شكل)",
  "Épargne auprès d'une institution financière": "الادخار لدى مؤسسة مالية",
  "Emprunt auprès d'une institution financière": "الاقتراض من مؤسسة مالية",
  "Fonds d'urgence mobilisables en 30 jours": "أموال طارئة متاحة في غضون 30 يومًا",
  "Pas de compte : pas assez d'argent": "بلا حساب: لا يوجد مال كافٍ",
  "Pas de compte : documents requis manquants": "بلا حساب: الوثائق المطلوبة ناقصة",
  "Pas de compte : services financiers trop chers": "بلا حساب: الخدمات المالية باهظة الثمن",
  "Pas de compte : institutions financières trop éloignées": "بلا حساب: المؤسسات المالية بعيدة جدًا",
  "Source principale des fonds d'urgence : prêt (banque, employeur ou prêteur privé)":
    "المصدر الرئيسي لأموال الطوارئ: قرض (بنك أو صاحب عمل أو مُقرض خاص)",
  "Source principale des fonds d'urgence : épargne": "المصدر الرئيسي لأموال الطوارئ: ادخار",
  "Compte inactif": "حساب غير نشط",
  "Comptes de prêt des banques commerciales": "حسابات القروض في البنوك التجارية",
  "Compte de monnaie mobile": "حساب نقود الهاتف المحمول",
  "Adultes sans compte": "البالغون بلا حساب",
};

export function tr(text: string): string {
  const lang = getLang();
  if (lang === "en") return DATA_EN[text] ?? EN[text] ?? text;
  if (lang === "ar") return DATA_AR[text] ?? AR[text] ?? text;
  return text;
}

const COUNTRY_RE: [RegExp, string, string][] = [
  [/\bTunisie\b/g, "Tunisia", "تونس"],
  [/\bAlgérie\b/g, "Algeria", "الجزائر"],
  [/Égypte/g, "Egypt", "مصر"],
  [/\bJordanie\b/g, "Jordan", "الأردن"],
  [/\bMaroc\b/g, "Morocco", "المغرب"],
];

export function translateCountryNames(text: string, lang: Lang): string {
  if (lang === "fr") return text;
  let out = text;
  for (const [pattern, en, ar] of COUNTRY_RE) {
    out = out.replace(pattern, lang === "en" ? en : ar);
  }
  return out;
}

function groupPhrase(text: string, lang: Lang): string {
  const map: Record<string, [string, string]> = {
    "des femmes": ["women", "النساء"],
    "des hommes": ["men", "الرجال"],
    "des quarante pour cent des ménages les plus pauvres":
      ["the poorest 40% of households", "أفقر 40% من الأسر"],
    "des soixante pour cent des ménages les plus riches":
      ["the richest 60% of households", "أغنى 60% من الأسر"],
    "des 40 % les plus pauvres": ["the poorest 40%", "أفقر 40%"],
    "des 60 % les plus riches": ["the richest 60%", "أغنى 60%"],
    "des adultes de 25 ans et plus": ["adults aged 25 and over", "البالغون من عمر 25 سنة وأكثر"],
    "des adultes de 15 à 24 ans": ["adults aged 15 to 24", "البالغون من عمر 15 إلى 24 سنة"],
    "des adultes de niveau primaire ou moins":
      ["adults with primary education or less", "البالغون بمستوى ابتدائي أو أقل"],
    "des adultes de niveau secondaire ou plus":
      ["adults with secondary education or more", "البالغون بمستوى ثانوي أو أعلى"],
    "des adultes hors population active":
      ["adults outside the labour force", "البالغون خارج القوى العاملة"],
    "des adultes de la population active":
      ["adults in the labour force", "البالغون ضمن القوى العاملة"],
    "des adultes ruraux": ["rural adults", "البالغون في الريف"],
    "des adultes urbains": ["urban adults", "البالغون في المدن"],
  };
  const entry = map[text];
  if (!entry) return translateCountryNames(text, lang);
  return lang === "ar" ? entry[1] : entry[0];
}

// Groupes nommés dans les pistes de recommandation.
const RECO_GROUPS: Record<string, [string, string]> = {
  "hommes": ["men", "الرجال"],
  "femmes": ["women", "النساء"],
  "60 % les plus riches": ["the richest 60%", "أغنى 60%"],
  "40 % les plus pauvres": ["the poorest 40%", "أفقر 40%"],
  "adultes de niveau secondaire ou plus":
    ["adults with secondary education or more", "البالغون بتعليم ثانوي أو أكثر"],
  "adultes de niveau primaire ou moins":
    ["adults with primary education or less", "البالغون بتعليم ابتدائي أو أقل"],
  "adultes du secondaire ou plus":
    ["adults with secondary education or more", "البالغون بتعليم ثانوي أو أكثر"],
  "adultes du primaire ou moins":
    ["adults with primary education or less", "البالغون بتعليم ابتدائي أو أقل"],
  "actifs": ["people in the labour force", "العاملون"],
  "jeunes de 15 à 24 ans": ["young people aged 15 to 24", "الشباب من 15 إلى 24 سنة"],
  "adultes de la population active":
    ["adults in the labour force", "البالغون ضمن القوى العاملة"],
  "adultes hors population active":
    ["adults outside the labour force", "البالغون خارج القوى العاملة"],
  "adultes de 25 ans et plus": ["adults aged 25 and over", "البالغون من 25 سنة فأكثر"],
  "adultes de 15 à 24 ans": ["adults aged 15 to 24", "البالغون من 15 إلى 24 سنة"],
  "adultes urbains": ["urban adults", "البالغون في المدن"],
  "adultes ruraux": ["rural adults", "البالغون في الريف"],
};

// Raisons déclarées citées dans les pistes de recommandation.
const REASONS_LOCAL: Record<string, [string, string]> = {
  "un membre de la famille en a déjà un": [
    "a family member already has one",
    "أحد أفراد الأسرة لديه حساب بالفعل",
  ],
  "manque de confiance dans les institutions financières": [
    "lack of trust in financial institutions",
    "انعدام الثقة في المؤسسات المالية",
  ],
};

function recoGroup(text: string, lang: Lang): string {
  const entry = RECO_GROUPS[text];
  if (!entry) return translateCountryNames(text, lang);
  return lang === "ar" ? entry[1] : entry[0];
}

// « adultes de 25 ans et plus et jeunes de 15 à 24 ans » : choisit la coupure
// qui donne deux groupes connus, sans casser un « et plus » interne.
function splitRecoGroups(clause: string): [string, string] {
  const parts = clause.split(" et ");
  for (let index = 1; index < parts.length; index += 1) {
    const left = parts.slice(0, index).join(" et ");
    const right = parts.slice(index).join(" et ");
    if (RECO_GROUPS[left] && RECO_GROUPS[right]) return [left, right];
  }
  return parts.length > 1 ? [parts[0], parts.slice(1).join(" et ")] : [clause, clause];
}

function gapTitle(text: string, lang: Lang): string {
  const map: Record<string, [string, string]> = {
    "femmes-hommes": ["gender", "بين الجنسين"],
    "de revenu": ["income", "الدخل"],
    "d'éducation": ["education", "التعليم"],
    "de marché du travail": ["labour market", "سوق العمل"],
    "d'activité": ["labour market", "سوق العمل"],
    "d'âge": ["age", "العمر"],
    "entre milieux": ["urban–rural", "بين المدن والأرياف"],
  };
  const entry = map[text];
  if (!entry) return text;
  return lang === "ar" ? entry[1] : entry[0];
}

// « 35,44 pour cent mille adultes » → « 35.44 per 100,000 adults » (anglais)
function spoken(value: string, lang: Lang): string {
  if (lang === "en")
    return value
      .replace(/\s*pour cent mille adultes/i, " per 100,000 adults")
      .replace(/\s*pour mille adultes/i, " per 1,000 adults");
  if (lang === "ar")
    return value
      .replace(/\s*pour cent mille adultes/i, " لكل 100 ألف بالغ")
      .replace(/\s*pour mille adultes/i, " لكل 1000 بالغ");
  return value;
}

function deltaText(value: string, lang: Lang): string {
  if (lang === "en") return value.replace(/\bpt\b/g, "pp").replace(/\bvs\b/g, "vs");
  if (lang === "ar") return value.replace(/\bpt\b/g, "نقطة").replace(/\bvs\b/g, "مقابل");
  return value;
}

type Pattern = [RegExp, (match: RegExpMatchArray, lang: Lang) => string | null];

// Traduction des phrases du pipeline analytique. Les captures (chiffres, années,
// libellés) sont réutilisées telles quelles : aucune valeur n'est recalculée.
const PATTERNS: Pattern[] = [
  // « En 2024, 37,8 % des adultes en Tunisie détiennent un compte. (+1,0 pt vs 2021) »
  [
    /^En (\d{4}), (.+?) des adultes en (.+?) détiennent un compte\.(?: \((.+?)\))?$/,
    (m, lang) => {
      const [, year, value, country, delta] = m;
      if (lang === "en") {
        return `In ${year}, ${value} of adults in ${translateCountryNames(country, lang)} hold an account.${delta ? ` (${deltaText(delta, lang)})` : ""}`;
      }
      if (lang === "ar") {
        return `في ${year}، ${value} من البالغين في ${translateCountryNames(country, lang)} لديهم حساب.${delta ? ` (${deltaText(delta, lang)})` : ""}`;
      }
      return null;
    },
  ],
  // « Les paiements numériques concernent … »
  [
    /^Les paiements numériques concernent (.+?) des adultes en (.+?) en (\d{4}) ; ce n'est pas une mesure de détention de compte\.$/,
    (m, lang) => {
      const [, value, country, year] = m;
      const place = translateCountryNames(country, lang);
      if (lang === "en") {
        return `Digital payments involve ${value} of adults in ${place} in ${year}; this is not a measure of account ownership.`;
      }
      if (lang === "ar") {
        return `تشمل المدفوعات الرقمية ${value} من البالغين في ${place} في ${year}؛ وهذا ليس مقياسًا لملكية الحساب.`;
      }
      return null;
    },
  ],
  // « L'épargne, toutes formes confondues, est estimée à … »
  [
    /^L'épargne, toutes formes confondues, est estimée à (.+?) en (\d{4})( ; cet indicateur du catalogue est provisoire)?\.$/,
    (m, lang) => {
      const [, value, year, provisional] = m;
      if (lang === "en") {
        return `Savings, in any form, are estimated at ${value} in ${year}${provisional ? "; this catalogue indicator is provisional" : ""}.`;
      }
      if (lang === "ar") {
        return `يُقدّر الادخار، بأي شكل، بـ ${value} في ${year}${provisional ? "؛ وهذا المؤشر في الكتالوج مؤقت" : ""}.`;
      }
      return null;
    },
  ],
  // « 88,4 % des adultes déclarent pouvoir obtenir de l'argent en urgence (2024). »
  [
    /^(.+?) des adultes déclarent pouvoir obtenir de l'argent en urgence \((\d{4})\)( ; .*)?\.$/,
    (m, lang) => {
      const [, value, year, warning] = m;
      const suffix = warning
        ? (lang === "en"
          ? "; the dictionary label does not match the expected Findex definition, the raw value still needs review"
          : lang === "ar"
            ? "؛ لا يتطابق وصف القاموس مع تعريف Findex المتوقع، والقيمة الخام تحتاج إلى مراجعة"
            : "")
        : "";
      if (lang === "en") return `${value} of adults say they could raise emergency money (${year})${suffix}.`;
      if (lang === "ar") return `${value} من البالغين يقولون إنهم يستطيعون تدبير مال طارئ (${year})${suffix}.`;
      return null;
    },
  ],
  // « Détention d'un compte en 2024 : Tunisie 37,8 %, contre … »
  [
    /^Détention d'un compte en (\d{4}) : (.+)\.$/,
    (m, lang) => {
      const [, year, listing] = m;
      let rest = listing;
      if (lang === "en") {
        rest = translateCountryNames(rest, lang).replace(/, contre /g, ", compared with ");
        return `Account ownership in ${year}: ${rest}.`;
      }
      if (lang === "ar") {
        rest = translateCountryNames(rest, lang).replace(/, contre /g, "، مقابل ");
        return `ملكية حساب في ${year}: ${rest}.`;
      }
      return null;
    },
  ],
  // « Les questions Findex sont distinctes : … »
  [
    /^Les questions Findex sont distinctes : (.+?) détiennent un compte, (.+?) ont effectué un paiement numérique, (.+?) épargnent à une institution formelle(?: et (.+?) y empruntent)?\.$/,
    (m, lang) => {
      const [, account, digital, saving, borrow] = m;
      if (lang === "en") {
        return `Findex questions are separate: ${account} hold an account, ${digital} made a digital payment, ${saving} save at a formal institution${borrow ? ` and ${borrow} borrow from one` : ""}.`;
      }
      if (lang === "ar") {
        return `أسئلة Findex مستقلة: ${account} لديهم حساب، و${digital} أجروا دفعًا رقميًا، و${saving} يدّخرون لدى مؤسسة رسمية${borrow ? `، و${borrow} يقترضون منها` : ""}.`;
      }
      return null;
    },
  ],
  // Même phrase, valeurs en tête : « … : 37,8 % détiennent un compte, … »
  [
    /^Les questions Findex sont distinctes : ([\d.,\u202f\u00a0 ]+%) détiennent un compte, ([\d.,\u202f\u00a0 ]+%) ont effectué un paiement numérique, ([\d.,\u202f\u00a0 ]+%) épargnent à une institution formelle(?: et ([\d.,\u202f\u00a0 ]+%) y empruntent)?\.$/,
    (m, lang) => {
      const [, account, digital, saving, borrow] = m;
      if (lang === "en") {
        return `Findex questions are separate: ${account} hold an account, ${digital} made a digital payment, ${saving} save at a formal institution${borrow ? ` and ${borrow} borrow from one` : ""}.`;
      }
      if (lang === "ar") {
        return `أسئلة Findex مستقلة: ${account} لديهم حساب، و${digital} أجروا دفعًا رقميًا، و${saving} يدّخرون لدى مؤسسة رسمية${borrow ? `، و${borrow} يقترضون منها` : ""}.`;
      }
      return null;
    },
  ],
  // « Écart femmes-hommes en 2024 : … »
  [
    /^Écart (.+?) en (\d{4}) : ([\d.,\u202f\u00a0 ]+%) (des .+?) contre ([\d.,\u202f\u00a0 ]+%) (des .+?), soit (.+?)\.(?: Variation depuis l'année antérieure observée : (.+?)\.)?$/,
    (m, lang) => {
      const [, title, year, leftValue, leftGroup, rightValue, rightGroup, rawGap, change] = m;
      const gapTitleText = gapTitle(title, lang);
      const lg = groupPhrase(leftGroup, lang);
      const rg = groupPhrase(rightGroup, lang);
      const gap = lang === "en" ? rawGap.replace(/\bpts\b/g, "pp") : rawGap;
      if (lang === "en") {
        return `${gapTitleText.charAt(0).toUpperCase() + gapTitleText.slice(1)} gap in ${year}: ${leftValue} for ${lg} versus ${rightValue} for ${rg}, i.e. ${gap}.${change ? ` Change since the previous observed year: ${change.replace(/\bpts\b/g, "pp")}.` : ""}`;
      }
      if (lang === "ar") {
        return `فجوة ${gapTitleText} في ${year}: ${leftValue} بين ${lg} مقابل ${rightValue} بين ${rg}، أي ${gap}.${change ? ` التغيّر منذ السنة المرصودة السابقة: ${change}.` : ""}`;
      }
      return null;
    },
  ],
  // « Le parc de distributeurs atteint … »
  [
    /^Le parc de distributeurs atteint (.+?) en (\d{4})( \(.+?\))?(?:, contre (.+?) en (\d{4}))?\.$/,
    (m, lang) => {
      const [, value, year, delta, base, baseYear] = m;
      const suffix = base
        ? lang === "en"
          ? `, against ${spoken(base, lang)} in ${baseYear}`
          : `، مقابل ${spoken(base, lang)} في ${baseYear}`
        : "";
      const change = delta ? deltaText(delta.replace(/[()]/g, "").trim(), lang) : "";
      if (lang === "en") return `The ATM network reaches ${spoken(value, lang)} in ${year}${change ? ` (${change})` : ""}${suffix}.`;
      if (lang === "ar") return `تصل شبكة الصرافات الآلية إلى ${spoken(value, lang)} في ${year}${change ? ` (${change})` : ""}${suffix}.`;
      return null;
    },
  ],
  // « Le réseau d'agences est de … »
  [
    /^Le réseau d'agences est de (.+?) en (\d{4})\.$/,
    (m, lang) => {
      const [, value, year] = m;
      if (lang === "en") return `The branch network stands at ${spoken(value, lang)} in ${year}.`;
      if (lang === "ar") return `تبلغ شبكة الفروع ${spoken(value, lang)} في ${year}.`;
      return null;
    },
  ],
  // « Déposants … ; Emprunteurs … »
  [
    /^(?:Déposants (.+?) en (\d{4}) ; )?(?:Emprunteurs (.+?) en (\d{4}))?\.$/,
    (m, lang) => {
      const [, dep, depYear, bor, borYear] = m;
      if (!dep && !bor) return null;
      const parts: string[] = [];
      if (dep) parts.push(lang === "en" ? `Depositors ${spoken(dep, lang)} in ${depYear}` : `المودعون ${spoken(dep, lang)} في ${depYear}`);
      if (bor) parts.push(lang === "en" ? `borrowers ${spoken(bor, lang)} in ${borYear}` : `المقترضون ${spoken(bor, lang)} في ${borYear}`);
      return lang === "en" ? `${parts.join("; ")}.` : `${parts.join("؛ ")}.`;
    },
  ],
  // « Encours de crédits … ; Encours de dépôts … »
  [
    /^(?:Encours de crédits (.+?) en (\d{4}) ; )?(?:Encours de dépôts (.+?) en (\d{4}))?\.$/,
    (m, lang) => {
      const [, loans, loansYear, deposits, depositsYear] = m;
      if (!loans && !deposits) return null;
      const gdp = (value: string) =>
        lang === "en" ? value.replace(/du PIB/g, "of GDP") : value.replace(/du PIB/g, "من الناتج المحلي الإجمالي");
      if (lang === "en") {
        const parts: string[] = [];
        if (loans) parts.push(`Bank credit ${gdp(loans)} in ${loansYear}`);
        if (deposits) parts.push(`bank deposits ${gdp(deposits)} in ${depositsYear}`);
        return `${parts.join("; ")}.`;
      }
      if (lang === "ar") {
        const parts: string[] = [];
        if (loans) parts.push(`الائتمان البنكي ${gdp(loans)} في ${loansYear}`);
        if (deposits) parts.push(`الودائع البنكية ${gdp(deposits)} في ${depositsYear}`);
        return `${parts.join("؛ ")}.`;
      }
      return null;
    },
  ],
  // XAI — écart femmes-hommes
  [
    /^En (\d{4}), (.+?) des femmes détiennent un compte contre (.+?) des hommes, un écart de (.+?)\.$/,
    (m, lang) => {
      const [, year, women, men, gap] = m;
      if (lang === "en") return `In ${year}, ${women} of women hold an account versus ${men} of men, a gap of ${gap}.`;
      if (lang === "ar") return `في ${year}، ${women} من النساء لديهن حساب مقابل ${men} من الرجال، أي فجوة ${gap}.`;
      return null;
    },
  ],
  // XAI — écart villes / campagnes
  [
    /^En (\d{4}), (.+?) des adultes urbains détiennent un compte contre (.+?) des adultes ruraux\.$/,
    (m, lang) => {
      const [, year, urban, rural] = m;
      if (lang === "en") return `In ${year}, ${urban} of urban adults hold an account versus ${rural} of rural adults.`;
      if (lang === "ar") return `في ${year}، ${urban} من البالغين في المدن لديهم حساب مقابل ${rural} من البالغين في الريف.`;
      return null;
    },
  ],
  // XAI — association
  [
    /^L'écart femmes-hommes \((.+?)\) et l'écart entre milieux \((.+?)\) sont des associations observées sur des sous-groupes distincts\.$/,
    (m, lang) => {
      const [, gender, place] = m;
      if (lang === "en") return `The gender gap (${gender}) and the urban–rural gap (${place}) are associations observed across distinct subgroups.`;
      if (lang === "ar") return `الفجوة بين الجنسين (${gender}) والفجوة بين المدن والأرياف (${place}) علاقتان ملحوظتان لدى مجموعات مختلفة.`;
      return null;
    },
  ],
  // « Écart calculé Maroc − Tunisie : +6,5 pt (différence de deux observations, même année). »
  [
    /^Écart calculé (.+?) [−–-] (.+?) : (.+?) pt \(différence de deux observations, même année\)\.$/,
    (m, lang) => {
      const [, left, right, value] = m;
      const a = translateCountryNames(left, lang);
      const b = translateCountryNames(right, lang);
      if (lang === "en") {
        return `Computed gap ${a} – ${b}: ${value} percentage points (difference between two observations, same year).`;
      }
      if (lang === "ar") {
        return `الفجوة المحسوبة ${a} – ${b}: ${value} نقطة مئوية (فرق بين ملاحظتين، السنة نفسها).`;
      }
      return null;
    },
  ],
  // « Piste à explorer : … Constat : … Association, pas causalité. »
  [
    /^Piste à explorer : (.+?)\. Constat : en (\d{4}), en (.+?), l'écart de détention d'un compte entre (.+?) est de (.+?) pts \((.+?) % contre (.+?) %\)\. Association, pas causalité\.$/,
    (m, lang) => {
      const [, action, year, country, clause, gap, leftValue, rightValue] = m;
      const place = translateCountryNames(country, lang);
      const [leftGroup, rightGroup] = splitRecoGroups(clause);
      const lg = recoGroup(leftGroup, lang);
      const rg = recoGroup(rightGroup, lang);
      if (lang === "en") {
        return `Area to explore: ${PROSE_EN[action] ?? action}. Finding: in ${year}, in ${place}, the account ownership gap between ${lg} and ${rg} is ${gap} pts (${leftValue}% versus ${rightValue}%). Observed link, not a cause.`;
      }
      if (lang === "ar") {
        return `مسار للاستكشاف: ${PROSE_AR[action] ?? action}. المعطى: في ${year}، في ${place}، فجوة ملكية الحساب بين ${lg} و${rg} تبلغ ${gap} نقطة (${leftValue}% مقابل ${rightValue}%). علاقة ملحوظة وليست سببًا.`;
      }
      return null;
    },
  ],
  // Diagnostics qualité et traitements techniques (page Sources)
  [
    /^\[(\w+)\] ([\d.,]+) % de cellules vides$/,
    (m, lang) => (lang === "en"
      ? `[${m[1]}] ${m[2]}% empty cells`
      : `[${m[1]}] ${m[2].replace(".", ",")} % خلايا فارغة`),
  ],
  [
    /^\[(\w+)\] (\d+) colonnes remplies a moins de ([\d.,]+) %$/,
    (m, lang) => (lang === "en"
      ? `[${m[1]}] ${m[2]} columns filled at less than ${m[3]}%`
      : `[${m[1]}] ${m[2]} عمودًا مملوءًا بأقل من ${m[3].replace(".", ",")} %`),
  ],
  [
    /^World Bank WDI - PA\.NUS\.FCRF \(taux de change officiel, moyenne annuelle\)$/,
    (m, lang) => (lang === "en"
      ? "World Bank WDI – PA.NUS.FCRF (official exchange rate, annual average)"
      : "البنك الدولي WDI – PA.NUS.FCRF (سعر الصرف الرسمي، المتوسط السنوي)"),
  ],
  [
    /^FAS: selection des series configurees, annees -> lignes$/,
    (m, lang) => (lang === "en"
      ? "FAS: selected configured series, years → rows"
      : "FAS: السلاسل المضبوطة المختارة، السنوات ← الصفوف"),
  ],
  [
    /^WDI: indicateurs PIB -> lignes ; croissance NY\.GDP\.MKTP\.KD\.ZG conservee meme negative$/,
    (_m, lang) => (lang === "en"
      ? "WDI: GDP indicators → rows; growth NY.GDP.MKTP.KD.ZG kept even when negative"
      : "WDI: مؤشرات الناتج المحلي ← الصفوف؛ نمو NY.GDP.MKTP.KD.ZG محتفظ به حتى إذا كان سالبًا"),
  ],
  [
    /^Sources utilisateur : mapping confirme -> observations canoniques, source user:<nom>, code prefixe, unite declaree, valeurs inchangees$/,
    (_m, lang) => (lang === "en"
      ? "User sources: confirmed mapping → canonical observations, source user:<name>, prefixed code, declared unit, unchanged values"
      : "مصادر المستخدم: ربط مؤكَّد ← ملاحظات قانونية، المصدر user:<name>، رمز بادئة، وحدة معلنة، قيم دون تغيير"),
  ],
  [
    /^Pivot par pays x annee, croissance du PIB = (.+?) \(prix constants\), jointure dimension pays$/,
    (m, lang) => (lang === "en"
      ? `Pivot by country × year, GDP growth = ${m[1]} (constant prices), country dimension join`
      : `تقاطع حسب البلد × السنة، نمو الناتج المحلي = ${m[1]} (أسعار ثابتة)، ربط ببعد البلد`),
  ],
  [
    /^Ecarts de detention de compte \(points de ?%\) : (.+)$/,
    (m, lang) => (lang === "en"
      ? "Account ownership gaps (percentage points): men − women, richest 60% − poorest 40%, 25+ − 15–24; same year, NULL if a subgroup is missing"
      : `فجوات ملكية الحساب (نقاط مئوية): الرجال − النساء، أغنى 60% − أفقر 40%، 25 سنة فأكثر − 15-24؛ السنة نفسها، NULL إذا غابت مجموعة`),
  ],
  [
    /^fraction Findex x 100 \(part des adultes en ?%\)$/,
    (_m, lang) => (lang === "en"
      ? "Findex fraction × 100 (share of adults, in %)"
      : "نسبة Findex × 100 (حصة البالغين، %)"),
  ],
  [
    /^100 \* value [—–-] fraction Findex x 100 \(part des adultes en ?%\)$/,
    (_m, lang) => (lang === "en"
      ? "100 × value — Findex fraction × 100 (share of adults, in %)"
      : "100 × القيمة — نسبة Findex × 100 (حصة البالغين، %)"),
  ],
  // Constats de contexte (SMIG, pauvreté) repris dans l'audit
  [
    /^Le SMIG mensuel brut est de (.+?) en (\d{4}) et le barème publié prévoit (.+?) en (\d{4}) ; les revalorisations restent à confirmer au JORT\.$/,
    (m, lang) => {
      const en = (value: string) => value.replace("TND/mois", "TND/month");
      const ar = (value: string) => value.replace("TND/mois", "دينار شهريًا");
      return lang === "en"
        ? `The gross monthly minimum wage is ${en(m[1])} in ${m[2]} and the published scale schedules ${en(m[3])} in ${m[4]}; increases remain to be confirmed in the Official Gazette.`
        : `الحد الأدنى للأجر الشهري الإجمالي هو ${ar(m[1])} في ${m[2]}، ويحدد الجدول المنشور ${ar(m[3])} في ${m[4]}؛ وتبقى الزيادات بحاجة إلى تأكيد في الجريدة الرسمية.`;
    },
  ],
  [
    /^Le taux de pauvreté national était de (.+?) en (\d{4}) \(INS\) : c'est un contexte socio-économique, pas une mesure d'exclusion financière\.$/,
    (m, lang) => (lang === "en"
      ? `The national poverty rate was ${m[1]} in ${m[2]} (INS): this is socio-economic context, not a measure of financial exclusion.`
      : `كان معدل الفقر الوطني ${m[1]} في ${m[2]} (المعهد الوطني للإحصاء): وهو سياق اجتماعي واقتصادي، وليس مقياسًا للإقصاء المالي.`),
  ],
  // « Piste … » — barrière déclarée au-dessus de la moyenne des pairs
  [
    /^Piste à explorer : (.+?)\. Constat : en (\d{4}), (.+?) % des adultes en (.+?) n'ont pas de compte et citent « (.+?) », contre (.+?) % en moyenne chez les pairs \(moyenne partielle, sans (.+?)\), soit (.+?) pts de plus\. Association, pas causalité\.$/,
    (m, lang) => {
      const [, action, year, value, country, reason, peer, missing, gap] = m;
      const place = translateCountryNames(country, lang);
      const excluded = translateCountryNames(missing, lang);
      const why = REASONS_LOCAL[reason];
      if (lang === "en") {
        return `Area to explore: ${PROSE_EN[action] ?? action}. Finding: in ${year}, ${value}% of adults in ${place} have no account and cite “${why?.[0] ?? reason}”, versus ${peer}% on average among peers (partial average, excluding ${excluded}), i.e. ${gap} pts more. Observed link, not a cause.`;
      }
      if (lang === "ar") {
        return `مسار للاستكشاف: ${PROSE_AR[action] ?? action}. المعطى: في ${year}، ${value}% من البالغين في ${place} بلا حساب ويذكرون «${why?.[1] ?? reason}»، مقابل ${peer}% في المتوسط لدى الأقران (متوسط جزئي، دون ${excluded})، أي بزيادة ${gap} نقطة. علاقة ملحوظة وليست سببًا.`;
      }
      return null;
    },
  ],
  // « Piste … » — usage inférieur à la moyenne des pairs
  [
    /^Piste à explorer : (.+?)\. Constat : en (\d{4}), paiement numérique effectué ou reçu : (.+?) % en (.+?), contre (.+?) % en moyenne chez les pairs, soit (.+?) pts de moins\. Association, pas causalité\.$/,
    (m, lang) => {
      const [, action, year, value, country, peer, gap] = m;
      const place = translateCountryNames(country, lang);
      if (lang === "en") {
        return `Area to explore: ${PROSE_EN[action] ?? action}. Finding: in ${year}, digital payment made or received: ${value}% in ${place}, versus ${peer}% on average among peers, i.e. ${gap} pts less. Observed link, not a cause.`;
      }
      if (lang === "ar") {
        return `مسار للاستكشاف: ${PROSE_AR[action] ?? action}. المعطى: في ${year}، دفع رقمي أُجري أو استُلم: ${value}% في ${place}، مقابل ${peer}% في المتوسط لدى الأقران، أي بانخفاض ${gap} نقطة. علاقة ملحوظة وليست سببًا.`;
      }
      return null;
    },
  ],
  // Sorties chiffrées des agents
  [
    /^(\d+) source\(s\) collectée\(s\)$/,
    (m, lang) => (lang === "en" ? `${m[1]} source(s) collected` : `${m[1]} مصدر/مصادر جُمعت`),
  ],
  [
    /^score ([\d.,]+), gate réussi$/,
    (m, lang) => (lang === "en" ? `score ${m[1]}, gate passed` : `الدرجة ${m[1]}، اجتازت البوابة`),
  ],
  [
    /^([\d\s\u202f]+) lignes fact, (\d+) pays$/,
    (m, lang) => (lang === "en" ? `${m[1]} fact rows, ${m[2]} countries` : `${m[1]} سجل وقائع، ${m[2]} بلدًا`),
  ],
  [
    /^(\d+) KPI, ([\d\s\u202f]+) lignes kpi_values \(([\d\s\u202f]+) disponibles, (\d+) avec revue\)$/,
    (m, lang) => (lang === "en"
      ? `${m[1]} KPIs, ${m[2]} kpi_values rows (${m[3]} available, ${m[4]} under review)`
      : `${m[1]} مؤشرًا، ${m[2]} سجل kpi_values (${m[3]} متاحة، ${m[4]} قيد المراجعة)`),
  ],
  [
    /^verdict (.+?) \((\d+) réussis, (\d+) avertissements, (\d+) échecs\)$/,
    (m, lang) => {
      const verdictEn = m[1] === "pass_with_warnings" ? "pass with warnings" : m[1];
      const verdictAr = m[1] === "pass_with_warnings" ? "نجاح مع تحذيرات" : m[1];
      return lang === "en"
        ? `verdict ${verdictEn} (${m[2]} passed, ${m[3]} warnings, ${m[4]} failures)`
        : `الحكم ${verdictAr} (${m[2]} ناجح، ${m[3]} تحذير، ${m[4]} فشل)`;
    },
  ],
  [
    /^(\d+) constats sur (\d+) faits, carte XAI (oui|non)$/,
    (m, lang) => {
      const yes = m[3] === "oui";
      return lang === "en"
        ? `${m[1]} insights across ${m[2]} facts, XAI map ${yes ? "yes" : "no"}`
        : `${m[1]} استنتاجًا من ${m[2]} واقعة، خريطة XAI ${yes ? "نعم" : "لا"}`;
    },
  ],
  [
    /^(\d+) pages, (\d+) faits, publication (.+)$/,
    (m, lang) => {
      if (lang === "ar") {
        const status = m[3] === "approved" ? "معتمد"
          : m[3] === "approved_with_review_note" ? "معتمد مع تحفظ"
            : m[3] === "blocked" ? "محجوب" : m[3];
        return `${m[1]} صفحات، ${m[2]} واقعة، النشر ${status}`;
      }
      return `${m[1]} pages, ${m[2]} facts, publication ${m[3]}`;
    },
  ],
  [
    /^(\d+) appel$/,
    (m, lang) => (lang === "en" ? `${m[1]} calls` : `${m[1]} نداء`),
  ],
  [
    /^(snapshot .+?) \((new)\)$/,
    (m, lang) => (lang === "en" ? `${m[1]} (new)` : `${m[1].replace(/^snapshot/, "لقطة")} (جديدة)`),
  ],
  // Notes dynamiques des graphiques
  [
    /^Chaque marche est une question Findex distincte, année (\d{4})\.$/,
    (m, lang) => (lang === "en"
      ? `Each step is a separate Findex question, year ${m[1]}.`
      : `كل خطوة سؤال Findex مستقل، سنة ${m[1]}.`),
  ],
  [
    /^Raisons déclarées de ne pas avoir de compte bancaire, année (\d{4}) \(Findex\)\.$/,
    (m, lang) => (lang === "en"
      ? `Stated reasons for not having a bank account, year ${m[1]} (Findex).`
      : `الأسباب المعلنة لعدم امتلاك حساب بنكي، سنة ${m[1]} (Findex).`),
  ],
  [
    /^Année observée (\d{4}) \((?:Findex, dimension urbanicity|enquête Findex, milieu de résidence)\)\.$/,
    (m, lang) => (lang === "en"
      ? `Observed year ${m[1]} (Findex survey, location breakdown).`
      : `السنة المرصودة ${m[1]} (استقصاء Findex، حسب بيئة الإقامة).`),
  ],
  [
    /^Moyenne des pairs partielle : (.+?) sans observation en (\d{4})\.$/,
    (m, lang) => {
      const place = translateCountryNames(m[1], lang);
      return lang === "en"
        ? `Partial peer average: ${place} has no observation in ${m[2]}.`
        : `متوسط أقران جزئي: ${place} بلا ملاحظة في ${m[2]}.`;
    },
  ],
  [
    /^Écart urbain [−–-] rural : (.+?)\.$/,
    (m, lang) => (lang === "en"
      ? `Urban–rural gap: ${m[1]}.`
      : `الفجوة بين المدن والأرياف: ${m[1]}.`),
  ],
  [
    /^Écart (épargne|emprunt) tout [−–-] formel : (.+?)\.$/,
    (m, lang) => {
      if (lang === "en") {
        return `${m[1] === "épargne" ? "Savings" : "Borrowing"} gap (any − formal): ${m[2]}.`;
      }
      return `${m[1] === "épargne" ? "فجوة الادخار" : "فجوة الاقتراض"} (أي شكل − رسمي): ${m[2]}.`;
    },
  ],
  [
    /^Indice — (.+) \((\d{4}) = 100\)$/,
    (m, lang) => (lang === "en"
      ? `Index — ${tr(m[1])} (${m[2]} = 100)`
      : `المؤشر — ${tr(m[1])} (${m[2]} = 100)`),
  ],
  [
    /^Variation de l'écart — (.+)$/,
    (m, lang) => (lang === "en"
      ? `Gap change — ${gapTitle(m[1], lang)}`
      : `تغيّر الفجوة — ${gapTitle(m[1], lang)}`),
  ],
  [
    /^Écart de compte — (.+)$/,
    (m, lang) => (lang === "en"
      ? `Account gap — ${gapTitle(m[1], lang)}`
      : `فجوة الحساب — ${gapTitle(m[1], lang)}`),
  ],
  [
    /^Écart — (.+)$/,
    (m, lang) => (lang === "en"
      ? `Gap — ${gapTitle(m[1], lang)}`
      : `الفجوة — ${gapTitle(m[1], lang)}`),
  ],
  // « Sans compte : services financiers trop chers — Tunisie » (libellés du pipeline)
  [
    /^(Sans compte : .+?)(?: — (.+))?$/,
    (m, lang) => {
      const [, rawLabel, suffix] = m;
      const key = rawLabel
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase();
      const entry = BARRIER_LABELS[key];
      if (!entry) return null;
      const label = lang === "en" ? entry[0] : entry[1];
      if (!suffix) return label;
      const where = tr(suffix) !== suffix ? tr(suffix) : translateCountryNames(suffix, lang);
      return `${label} — ${where}`;
    },
  ],
];

// Barrières déclarées (libellés bruts du pipeline, sans accents) : anglais, arabe.
const BARRIER_LABELS: Record<string, [string, string]> = {
  "sans compte : institution financiere trop eloignee": [
    "No account: financial institution too far",
    "بلا حساب: المؤسسة المالية بعيدة جدًا",
  ],
  "sans compte : services financiers trop chers": [
    "No account: financial services too expensive",
    "بلا حساب: الخدمات المالية مكلفة جدًا",
  ],
  "sans compte : documents requis manquants": [
    "No account: required documents missing",
    "بلا حساب: الوثائق المطلوبة ناقصة",
  ],
  "sans compte : fonds insuffisants": [
    "No account: insufficient funds",
    "بلا حساب: أموال غير كافية",
  ],
  "sans compte : un membre de la famille en possede deja un": [
    "No account: a family member already has one",
    "بلا حساب: أحد أفراد الأسرة لديه حساب بالفعل",
  ],
  "sans compte : manque de confiance dans les institutions financieres": [
    "No account: lack of trust in financial institutions",
    "بلا حساب: انعدام الثقة في المؤسسات المالية",
  ],
};

const PROSE_EN: Record<string, string> = {
  "Findex mesure les raisons déclarées de ne pas avoir de compte : une même personne peut en citer plusieurs, et ces raisons décrivent l'exclusion sans en mesurer la cause.":
    "Findex records the stated reasons for not having an account: one person may cite several, and these reasons describe exclusion without measuring its cause.",
  "Les barrières déclarées ne sont pas chargées dans le warehouse : aucune explication par ces barrières n'est mesurée dans ce run.":
    "Reported barriers are not loaded in the database: no explanation based on them is measured in this run.",
  "Hypothèse à tester : des actions ciblant les femmes et les zones rurales pourraient réduire les écarts observés ; aucun effet causal n'est estimé ici.":
    "Hypothesis to test: actions targeting women and rural areas could reduce the observed gaps; no causal effect is estimated here.",
  "Association, pas causalité : les écarts décrivent des sous-groupes observés et ne démontrent aucun effet causal.":
    "Association, not causation: the gaps describe observed subgroups and demonstrate no causal effect.",
  "Ordres de grandeur : contexte, pas des KPI d'inclusion.":
    "Orders of magnitude: context, not inclusion indicators.",
  "Contexte macro, pas un indicateur d'inclusion.":
    "Macro context, not an inclusion indicator.",
  "Chaque point est une observation observée; aucune interpolation.":
    "Each point is a published figure; no value is estimated.",
  "Les sous-groupes ne sont pas des populations appariées.":
    "The subgroups are not the same people.",
  "Les repères statiques sont des agrégats Findex 2025 (vague 2024), pas des observations du pays.":
    "Reference markers are Findex 2025 aggregates (2024 wave), not observations of this country.",
  "DZA, EGY, JOR, MAR, TUN; le pays sélectionné est mis en évidence.":
    "DZA, EGY, JOR, MAR, TUN; the selected country is highlighted.",
  "Comparaison des détentions de compte à l'année sélectionnée.":
    "Comparison of account ownership in the selected year.",
  "ATMs et agences pour 100 000 adultes.": "ATMs and branches per 100,000 adults.",
  "ATMs pour 100 000 adultes — pairs": "ATMs per 100,000 adults — peers",
  "Dernière année disponible au plus tard à l'année sélectionnée.":
    "Latest year available up to the selected year.",
  "Indice calculé en code à partir des séries affichées.":
    "Index computed in code from the displayed series.",
  "Indice = valeur / valeur 2017 × 100; une année sans observation reste vide.":
    "Index = value / 2017 value × 100; a year without an observation stays empty.",
  "L'offre (ATMs) et la demande (paiements numériques) ont des définitions distinctes.":
    "Supply (ATMs) and demand (digital payments) have distinct definitions.",
  "Deux échelles comparables (même unité). Aucune donnée annuelle inventée.":
    "Two comparable scales (same unit). No annual data is invented.",
  "Plusieurs raisons peuvent être citées : les parts ne s'additionnent pas à 100 %.":
    "Several reasons may be cited: the shares do not add up to 100%.",
  "Part de tous les adultes (15 ans et plus) ; comptes bancaires uniquement (hors mobile money).":
    "Share of all adults (15 and over); bank accounts only (excluding mobile money).",
  "Aucune barre n'est dessinée à partir d'une valeur inventée.":
    "No bar is drawn from an invented value.",
  "Réponses déterministes, chiffres vérifiés dans les faits.":
    "Deterministic answers, figures checked against the facts.",
  "Ce n'est pas un entonnoir de cohorte : les questions Findex sont posées séparément, la baisse n'est pas un taux de conversion individuel.":
    "This is not a cohort funnel: Findex questions are asked separately, and the drop is not an individual conversion rate.",
  "Aucune année n'est substituée : une marche non observée reste vide.":
    "No year is substituted: an unobserved step stays empty.",
  "L'écart est calculé à partir des deux sous-groupes affichés.":
    "The gap is computed from the two displayed subgroups.",
  "Les écarts sont calculés à partir des deux observations affichées.":
    "Gaps are computed from the two displayed observations.",
  "Un écart négatif signifie que le groupe avantagé est en dessous; la variation est calculée en points, jamais en %.":
    "A negative gap means the advantaged group is below; change is computed in points, never in %.",
  "écart entre sous-groupes ≥ 10 pts": "gap between subgroups ≥ 10 pts",
  "étudier des offres et canaux de distribution conçus pour les femmes":
    "study offers and distribution channels designed for women",
  "examiner des comptes à bas coût et sans frais fixes pour les 40 % les plus pauvres":
    "examine low-cost accounts with no fixed fees for the poorest 40%",
  "tester des parcours d'ouverture simplifiés et de l'accompagnement pour les adultes du primaire ou moins":
    "test simplified opening journeys and support for adults with primary education or less",
  "explorer des canaux qui ne passent pas par l'employeur pour les adultes hors population active":
    "explore channels that do not go through the employer for adults outside the labour force",
  "étudier des offres d'entrée pour les jeunes de 15 à 24 ans":
    "study entry-level offers for young people aged 15 to 24",
  "examiner les points de service de proximité (agents, mobile) pour les adultes ruraux":
    "examine nearby service points (agents, mobile) for rural adults",
  "explorer des comptes individuels faciles à ouvrir pour les adultes sans compte dont un proche en possède un":
    "explore easy-to-open individual accounts for unbanked adults whose relative already has one",
  "explorer l'information sur la protection des clients et la garantie des dépôts pour les adultes sans compte méfiants envers les institutions financières":
    "explore client-protection and deposit-guarantee information for unbanked adults who distrust financial institutions",
  "examiner l'acceptation des paiements numériques chez les commerçants pour les adultes qui ne paient pas encore par voie numérique":
    "examine merchant acceptance of digital payments for adults who do not pay digitally yet",
  "pays − moyenne des pairs ≥ 5 pts": "country − peer average ≥ 5 pts",
  "moyenne des pairs − pays ≥ 5 pts": "peer average − country ≥ 5 pts",
  "Contexte macro, pas un KPI d'inclusion.": "Macro context, not an inclusion indicator.",
  "Association, pas causalité": "Observed link, not a cause",
  // Pipeline / agents
  "Collecte les sources officielles (Findex, FAS, PIB WDI) et les sources utilisateur confirmées ; calcule l'empreinte SHA-256 de chaque fichier.":
    "Collects official sources (Findex, FAS, WDI GDP) and confirmed user sources; computes the SHA-256 fingerprint of each file.",
  "Versionne les fichiers bruts (blobs dédupliqués par SHA-256) ; sans donnée nouvelle, le run s'arrête.":
    "Versions raw files (blobs deduplicated by SHA-256); with no new data, the run stops.",
  "Profile chaque source : dimensions, valeurs manquantes, types, colonnes de métadonnées, valeurs atypiques (IsolationForest).":
    "Profiles each source: dimensions, missing values, types, metadata columns and outliers (IsolationForest).",
  "Contrôle qualité : score par source, gate (seuil configuré), anomalies classées par sévérité, diagnostics de plausibilité, exclusion des sources utilisateur non conformes.":
    "Quality control: score per source, gate (configured threshold), anomalies ranked by severity, plausibility diagnostics and exclusion of non-compliant user sources.",
  "Harmonise les sources (codes pays ISO3, années, unités) et construit le modèle en étoile.":
    "Harmonises sources (ISO3 country codes, years, units) and builds the star schema.",
  "Calcule chaque KPI du catalogue pour le pays focus et les pairs, sur chaque année valide ; attribue un statut de publication.":
    "Computes every catalogue KPI for the focus country and peers, for each valid year; assigns a publication status.",
  "Vérification indépendante : recalcul depuis fact sans le code KPI, contrôles de cohérence et de traçabilité, verdict d'audit, explications par valeur ; décide la publication du snapshot.":
    "Independent verification: recomputation from fact without the KPI code, consistency and traceability checks, audit verdict and per-value explanations; decides snapshot publication.",
  "Écrit les constats et la carte XAI à partir des faits exportés ; tout nombre d'une phrase doit exister dans les faits (verify_numbers).":
    "Writes insights and the XAI map from exported facts; every number in a sentence must exist in the facts (verify_numbers).",
  "Construit le contrat FinOVA 2.0 validé (pages, métriques, graphiques, faits, avertissements) ; ne calcule aucun KPI et n'approuve aucune publication.":
    "Builds the validated FinOVA data contract (pages, metrics, charts, facts, warnings); computes no KPI and approves no publication.",
  "Répond aux questions de l'utilisateur sur la vue affichée ; lit les chiffres uniquement via des outils sur les faits ; chaque nombre de la réponse est contrôlé (grounding).":
    "Answers user questions about the displayed view; reads figures only through tools over the facts; every number in the answer is checked (grounding).",
  "déterministe": "deterministic",
  "déterministe + LLM optionnel (plan de remédiation rédigé, sans effet sur le score ni le gate ; groq → gemini)":
    "deterministic + optional LLM (remediation plan drafted, with no effect on the score or gate; groq → gemini)",
  "déterministe + LLM optionnel (reformulation de quelques explications, rejetée si un nombre n'est pas justifié ; groq → gemini)":
    "deterministic + optional LLM (rephrases a few explanations, rejected if a number is not justified; groq → gemini)",
  "déterministe (narration LLM désactivée : analyst.narrate = false)":
    "deterministic (LLM narration disabled: analyst.narrate = false)",
  "déterministe + LLM optionnel (conversation avec outils sur les faits, nombres contrôlés ; groq → gemini)":
    "deterministic + optional LLM (tool-based conversation over the facts, numbers checked; groq → gemini)",
  "réponses à la demande, nombres contrôlés contre les faits":
    "on-demand answers, numbers checked against the facts",
  "à la demande (POST /api/ask), aucun rapport de run":
    "on demand (POST /api/ask), no run report",
  "non disponible": "not available",
  "moyenne des pairs incomplète": "incomplete peer average",
  "aucun pair observé": "no peer observed",
  "non auditable": "not auditable",
};

const PROSE_AR: Record<string, string> = {
  "Findex mesure les raisons déclarées de ne pas avoir de compte : une même personne peut en citer plusieurs, et ces raisons décrivent l'exclusion sans en mesurer la cause.":
    "يقيس Findex الأسباب المعلنة لعدم امتلاك حساب: قد يذكر الشخص الواحد عدة أسباب، وهي تصف الإقصاء دون قياس سببه.",
  "Les barrières déclarées ne sont pas chargées dans le warehouse : aucune explication par ces barrières n'est mesurée dans ce run.":
    "لم تُحمَّل العوائق المعلنة في قاعدة البيانات: ولا يوجد في هذا التشغيل تفسير مبني عليها.",
  "Hypothèse à tester : des actions ciblant les femmes et les zones rurales pourraient réduire les écarts observés ; aucun effet causal n'est estimé ici.":
    "فرضية قابلة للاختبار: قد تقلّل الإجراءات الموجّهة إلى النساء والمناطق الريفية الفجوات الملحوظة؛ ولا يُقدَّر أي أثر سببي هنا.",
  "Association, pas causalité : les écarts décrivent des sous-groupes observés et ne démontrent aucun effet causal.":
    "علاقة وليست سببية: تصف الفجوات مجموعات ملحوظة ولا تثبت أي أثر سببي.",
  "Ordres de grandeur : contexte, pas des KPI d'inclusion.":
    "أحجام تقريبية: سياق وليست مؤشرات إدماج مالي.",
  "Contexte macro, pas un indicateur d'inclusion.":
    "سياق كلي وليس مؤشر إدماج مالي.",
  "Chaque point est une observation observée; aucune interpolation.":
    "كل نقطة رقم منشور؛ ولا توجد قيمة مقدّرة.",
  "Les sous-groupes ne sont pas des populations appariées.":
    "المجموعات ليست نفس الأشخاص.",
  "Les repères statiques sont des agrégats Findex 2025 (vague 2024), pas des observations du pays.":
    "العلامات المرجعية هي تجميعات Findex 2025 (موجة 2024)، وليست ملاحظات لهذا البلد.",
  "DZA, EGY, JOR, MAR, TUN; le pays sélectionné est mis en évidence.":
    "DZA, EGY, JOR, MAR, TUN؛ البلد المحدد مُبرَز.",
  "Comparaison des détentions de compte à l'année sélectionnée.":
    "مقارنة ملكية الحساب في السنة المحددة.",
  "ATMs et agences pour 100 000 adultes.": "الصرافات الآلية والفروع لكل 100 ألف بالغ.",
  "ATMs pour 100 000 adultes — pairs": "الصرافات الآلية لكل 100 ألف بالغ — الأقران",
  "Dernière année disponible au plus tard à l'année sélectionnée.":
    "آخر سنة متاحة في حدود السنة المحددة.",
  "Indice calculé en code à partir des séries affichées.":
    "مؤشر يُحسب برمجيًا من السلاسل المعروضة.",
  "Indice = valeur / valeur 2017 × 100; une année sans observation reste vide.":
    "المؤشر = القيمة / قيمة 2017 × 100؛ والسنة بلا ملاحظة تبقى فارغة.",
  "L'offre (ATMs) et la demande (paiements numériques) ont des définitions distinctes.":
    "العرض (الصرافات) والطلب (المدفوعات الرقمية) لهما تعريفان مختلفان.",
  "Deux échelles comparables (même unité). Aucune donnée annuelle inventée.":
    "مقياسان متقارنان (الوحدة نفسها). ولا تُختلق أي بيانات سنوية.",
  "Plusieurs raisons peuvent être citées : les parts ne s'additionnent pas à 100 %.":
    "قد تُذكر عدة أسباب: فالحصص لا تجمع إلى 100%.",
  "Part de tous les adultes (15 ans et plus) ; comptes bancaires uniquement (hors mobile money).":
    "نسبة جميع البالغين (15 سنة فأكثر)؛ حسابات بنكية فقط (دون المحفظة المحمولة).",
  "Aucune barre n'est dessinée à partir d'une valeur inventée.":
    "لا يُرسم أي عمود انطلاقًا من قيمة مختلقة.",
  "Réponses déterministes, chiffres vérifiés dans les faits.":
    "أجوبة حتمية وأرقام متحقق منها في الوقائع.",
  "Ce n'est pas un entonnoir de cohorte : les questions Findex sont posées séparément, la baisse n'est pas un taux de conversion individuel.":
    "هذا ليس قمعًا جماعيًا: أسئلة Findex تُطرح منفصلة، والانخفاض ليس معدل تحويل فردي.",
  "Aucune année n'est substituée : une marche non observée reste vide.":
    "لا تُستبدل أي سنة: الخطوة غير المرصودة تبقى فارغة.",
  "L'écart est calculé à partir des deux sous-groupes affichés.":
    "تُحسب الفجوة من المجموعتين المعروضتين.",
  "Les écarts sont calculés à partir des deux observations affichées.":
    "تُحسب الفجوات من الملاحظتين المعروضتين.",
  "Un écart négatif signifie que le groupe avantagé est en dessous; la variation est calculée en points, jamais en %.":
    "الفجوة السالبة تعني أن المجموعة الأكثر ميزة أدنى؛ ويُحسب التغيّر بالنقاط لا بالنسبة المئوية.",
  "écart entre sous-groupes ≥ 10 pts": "الفجوة بين المجموعات ≥ 10 نقاط",
  "étudier des offres et canaux de distribution conçus pour les femmes":
    "دراسة عروض وقنوات توزيع مصممة للنساء",
  "examiner des comptes à bas coût et sans frais fixes pour les 40 % les plus pauvres":
    "دراسة حسابات منخفضة الكلفة وبلا رسوم ثابتة لأفقر 40%",
  "tester des parcours d'ouverture simplifiés et de l'accompagnement pour les adultes du primaire ou moins":
    "اختبار مسارات فتح مبسطة ومواكبة للبالغين بمستوى ابتدائي أو أقل",
  "explorer des canaux qui ne passent pas par l'employeur pour les adultes hors population active":
    "استكشاف قنوات لا تمر عبر صاحب العمل للبالغين خارج القوى العاملة",
  "étudier des offres d'entrée pour les jeunes de 15 à 24 ans":
    "دراسة عروض أولية للشباب من 15 إلى 24 سنة",
  "examiner les points de service de proximité (agents, mobile) pour les adultes ruraux":
    "دراسة نقاط الخدمة القريبة (وكلاء، هاتف) للبالغين في الريف",
  "explorer des comptes individuels faciles à ouvrir pour les adultes sans compte dont un proche en possède un":
    "استكشاف حسابات فردية سهلة الفتح للبالغين بلا حساب ممن لديه قريب يملك حسابًا",
  "explorer l'information sur la protection des clients et la garantie des dépôts pour les adultes sans compte méfiants envers les institutions financières":
    "نشر معلومات حماية العملاء وضمان الودائع للبالغين بلا حساب الذين لا يثقون بالمؤسسات المالية",
  "examiner l'acceptation des paiements numériques chez les commerçants pour les adultes qui ne paient pas encore par voie numérique":
    "دراسة قبول المدفوعات الرقمية لدى التجار للبالغين الذين لا يدفعون رقميًا بعد",
  "pays − moyenne des pairs ≥ 5 pts": "البلد − متوسط الأقران ≥ 5 نقاط",
  "moyenne des pairs − pays ≥ 5 pts": "متوسط الأقران − البلد ≥ 5 نقاط",
  "Contexte macro, pas un KPI d'inclusion.": "سياق كلي وليس مؤشر إدماج مالي.",
  "Association, pas causalité": "علاقة ملحوظة وليست سببًا",
  "Collecte les sources officielles (Findex, FAS, PIB WDI) et les sources utilisateur confirmées ; calcule l'empreinte SHA-256 de chaque fichier.":
    "يجمع المصادر الرسمية (Findex وFAS والناتج المحلي WDI) ومصادر المستخدم المؤكدة؛ ويحسب بصمة SHA-256 لكل ملف.",
  "Versionne les fichiers bruts (blobs dédupliqués par SHA-256) ; sans donnée nouvelle, le run s'arrête.":
    "يؤرشف الملفات الخام (كتل منزوعة التكرار عبر SHA-256)؛ وفي غياب بيانات جديدة يتوقف التشغيل.",
  "Profile chaque source : dimensions, valeurs manquantes, types, colonnes de métadonnées, valeurs atypiques (IsolationForest).":
    "يحلّل كل مصدر: الأبعاد والقيم الناقصة والأنواع وأعمدة البيانات الوصفية والقيم الشاذة (IsolationForest).",
  "Contrôle qualité : score par source, gate (seuil configuré), anomalies classées par sévérité, diagnostics de plausibilité, exclusion des sources utilisateur non conformes.":
    "مراقبة الجودة: درجة لكل مصدر، وبوابة (حد مضبوط)، وشذوذات مرتبة حسب الخطورة، وتشخيصات المعقولية، واستبعاد مصادر المستخدم غير المطابقة.",
  "Harmonise les sources (codes pays ISO3, années, unités) et construit le modèle en étoile.":
    "يوحّد المصادر (رموز ISO3 والسنوات والوحدات) ويبني النموذج النجمي.",
  "Calcule chaque KPI du catalogue pour le pays focus et les pairs, sur chaque année valide ; attribue un statut de publication.":
    "يحسب كل مؤشر في الكتالوج للبلد المعني والأقران لكل سنة صالحة؛ ويُسند حالة نشر.",
  "Vérification indépendante : recalcul depuis fact sans le code KPI, contrôles de cohérence et de traçabilité, verdict d'audit, explications par valeur ; décide la publication du snapshot.":
    "تحقق مستقل: إعادة حساب من جدول الوقائع دون شيفرة المؤشر، وفحوص الاتساق والتتبّع، وحكم التدقيق، وشروح لكل قيمة؛ ويقرر نشر اللقطة.",
  "Écrit les constats et la carte XAI à partir des faits exportés ; tout nombre d'une phrase doit exister dans les faits (verify_numbers).":
    "يكتب الاستنتاجات وخريطة XAI من الوقائع المصدَّرة؛ وكل رقم في الجملة يجب أن يوجد في الوقائع (verify_numbers).",
  "Construit le contrat FinOVA 2.0 validé (pages, métriques, graphiques, faits, avertissements) ; ne calcule aucun KPI et n'approuve aucune publication.":
    "يبني عقد بيانات FinOVA المعتمد (الصفحات والمقاييس والرسوم والوقائع والتحذيرات)؛ ولا يحسب أي مؤشر ولا يعتمد أي نشر.",
  "Répond aux questions de l'utilisateur sur la vue affichée ; lit les chiffres uniquement via des outils sur les faits ; chaque nombre de la réponse est contrôlé (grounding).":
    "يجيب عن أسئلة المستخدم حول العرض المعروض؛ ويقرأ الأرقام فقط عبر أدوات على الوقائع؛ وكل رقم في الجواب مُتحقَّق منه (grounding).",
  "déterministe": "حتمي",
  "déterministe + LLM optionnel (plan de remédiation rédigé, sans effet sur le score ni le gate ; groq → gemini)":
    "حتمي + نموذج لغوي اختياري (خطة معالجة مكتوبة، دون أثر على الدرجة أو البوابة؛ groq → gemini)",
  "déterministe + LLM optionnel (reformulation de quelques explications, rejetée si un nombre n'est pas justifié ; groq → gemini)":
    "حتمي + نموذج لغوي اختياري (إعادة صياغة بعض الشروح، تُرفض إن لم يكن الرقم مبرَّرًا؛ groq → gemini)",
  "déterministe (narration LLM désactivée : analyst.narrate = false)":
    "حتمي (سرد النموذج اللغوي معطّل: analyst.narrate = false)",
  "déterministe + LLM optionnel (conversation avec outils sur les faits, nombres contrôlés ; groq → gemini)":
    "حتمي + نموذج لغوي اختياري (محادثة بأدوات على الوقائع، أرقام مُتحقَّق منها؛ groq → gemini)",
  "réponses à la demande, nombres contrôlés contre les faits":
    "أجوبة عند الطلب، وأرقام مُتحقَّق منها مقابل الوقائع",
  "à la demande (POST /api/ask), aucun rapport de run":
    "عند الطلب (POST /api/ask)، دون تقرير تشغيل",
  "non disponible": "غير متاح",
  "moyenne des pairs incomplète": "متوسط أقران غير مكتمل",
  "aucun pair observé": "لا يوجد قرين مرصود",
  "non auditable": "غير قابل للتدقيق",
};

// Traduction d'une phrase du pipeline analytique (constats, XAI, blocs).
// Retourne le texte d'origine si aucune règle ne s'applique.
export function localizeProse(text: string): string {
  const lang = getLang();
  if (lang === "fr" || !text) return text;
  // libellés de données (séries, groupes, pays) : traduction exacte
  const known = tr(text);
  if (known !== text) return known;
  const exact = lang === "en" ? PROSE_EN[text] : PROSE_AR[text];
  if (exact) return exact;
  for (const [pattern, render] of PATTERNS) {
    const match = text.match(pattern);
    if (match) {
      const output = render(match, lang);
      if (output) return output;
    }
  }
  // « Lecture XAI — Tunisie, 2024 »
  const xai = text.match(/^Lecture XAI — (.+), (\d{4})$/);
  if (xai) {
    return lang === "en"
      ? `XAI reading — ${translateCountryNames(xai[1], lang)}, ${xai[2]}`
      : `قراءة تفسيرية — ${translateCountryNames(xai[1], lang)}، ${xai[2]}`;
  }
  let out = translateCountryNames(text, lang);
  if (lang === "en") {
    out = out
      .replace(/\/ 100k adultes/g, "/ 100k adults")
      .replace(/\/ 1 000 adultes/g, "/ 1,000 adults")
      .replace(/\/ 100 000 adultes/g, "/ 100,000 adults")
      .replace(/\bdu PIB\b/g, "of GDP");
  } else {
    out = out
      .replace(/\/ 100k adultes/g, "/ 100 ألف بالغ")
      .replace(/\/ 1 000 adultes/g, "/ 1000 بالغ")
      .replace(/\/ 100 000 adultes/g, "/ 100 ألف بالغ")
      .replace(/\bdu PIB\b/g, "من الناتج المحلي الإجمالي");
  }
  return out;
}

// Typographie anglaise : virgule décimale → point, milliers → virgule.
export function englishNumbers(text: string): string {
  if (!text) return text;
  return text
    .replace(/(\d)[\u202f\u00a0 ](\d{3})(?=\D|$)/g, "$1,$2")
    .replace(/(\d)[\u202f\u00a0 ](\d{3})(?=\D|$)/g, "$1,$2")
    .replace(/(\d),(\d)/g, "$1.$2")
    .replace(/\s+%/g, "%");
}
