# Configuration des LLM (Gemini, Groq, Claude)

BIFlow utilise trois providers avec une chaîne de fallback automatique.
Les clés sont lues depuis `.env` (jamais depuis `config.yaml` ni le code).

## 1. Créer les clés

| Provider | Console | Variable |
|---|---|---|
| Google AI Studio (Gemini) | <https://aistudio.google.com/apikey> | `GOOGLE_API_KEY` |
| Groq | <https://console.groq.com/keys> | `GROQ_API_KEY` |
| Anthropic (Claude) | <https://console.anthropic.com/settings/keys> | `ANTHROPIC_API_KEY` |

1. Copier le modèle : `Copy-Item .env.example .env`
2. Renseigner les trois variables dans `.env`.
3. Vérifier : `python scripts/check_llm.py`

## 2. Quotas et coûts

- **Gemini Flash** : tier gratuit avec quota journalier. Provider principal.
- **Groq Llama 3.3 70B** : tier gratuit, rate-limit à la minute. Très rapide.
- **Claude Sonnet** : API payante (pas de tier gratuit). Réservé aux agents
  `semantic`, `analyst` et `xai`, avec `llm.max_calls_per_agent` comme plafond.

Consommation typique : 20 à 50 appels par run complet (6 agents, sorties JSON,
quelques retries), hors cache.

## 3. Routage

Défini dans `config/config.yaml` sous `llm.routing`. L'ordre est :
**primaire → fallback 1 → fallback 2**. Un provider sans clé est ignoré.

```yaml
routing:
  semantic: [claude, gemini, groq]
  profiler: [groq, gemini, claude]
  quality:  [gemini, groq, claude]
```

Changer de modèle sans toucher au code :

```yaml
providers:
  gemini:
    type: google
    model: gemini-2.5-flash
```

## 4. Garde-fous

- `temperature: 0` pour des sorties stables.
- `max_calls_per_agent: 5` limite les boucles et les coûts.
- Cache disque dans `outputs/llm_cache/` : les mêmes prompts ne sont pas repayés.
- Les sorties LLM seront validées par des schémas pydantic avant utilisation
  (ajouté avec les agents), avec repli déterministe en cas d'échec.
- Compteur de tokens par agent exposé via `AgentLLM.usage()`.

## 5. Dépannage

| Message | Cause / solution |
|---|---|
| `cle absente : GOOGLE_API_KEY` | variable non renseignée dans `.env` |
| `paquet manquant` | `pip install -r requirements.txt` |
| `appel : Unauthorized` | clé invalide ou révoquée |
| `appel : 429` | quota atteint → le fallback prend le relais |
| `model not found` | ajuster `llm.providers.<nom>.model` |

Tester un seul provider : `python scripts/check_llm.py --provider groq`
Tester une chaîne d'agent : `python scripts/check_llm.py --agent semantic`

## 6. Sécurité

- `.env` est ignoré par Git (`.gitignore`) : ne jamais le committer.
- Ne jamais coller une clé dans un ticket, un rapport ou une conversation.
- En cas de fuite : révoquer la clé dans la console du provider et en générer une autre.
