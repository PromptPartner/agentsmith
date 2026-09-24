<div align="center">
  <img src="site/assets/promptpartner-mark-amber.svg" width="72" height="72" alt="PromptPartner mark">
  <p>
    <a href="https://github.com/PromptPartner/agentsmith/actions/workflows/verify.yml"><img alt="Verification" src="https://github.com/PromptPartner/agentsmith/actions/workflows/verify.yml/badge.svg?branch=master"></a>
    <a href="https://github.com/PromptPartner/agentsmith/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/PromptPartner/agentsmith"></a>
    <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-14213D.svg"></a>
  </p>
  <p>
    <a href="README.md">English</a> · <a href="README.de.md">Deutsch</a> · <a href="README.es.md">Español</a> · <strong>Français</strong> · <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

# AgentSmith

**La preuve avant de déclarer le travail terminé.** Donnez à votre agent IA les règles du projet, une définition du travail terminé et un moyen de prouver le résultat.

AgentSmith installe dans un projet un accord de fonctionnement commun et un profil de travail. Votre agent reçoit des limites claires, exécute les vérifications pertinentes, teste le parcours réel, consigne les preuves et prépare une transmission qu’une autre session peut valider. Vous gardez le contrôle des écritures vers des services externes.

![AgentSmith flow: project rules and profile, bounded agent work, automated checks and real-path exercise, evidence, then handoff and resume.](site/assets/agentsmith-flow.svg)

## Configurer AgentSmith

Choisissez l’une des deux méthodes. Toutes deux utilisent la même configuration guidée et produisent les mêmes fichiers de projet.

### 1. Configuration manuelle

1. Téléchargez le programme d’installation signé pour macOS, Windows ou Linux depuis la [dernière version](https://github.com/PromptPartner/agentsmith/releases/latest).
2. Ouvrez un terminal et exécutez `agentsmith`.
3. Répondez aux questions guidées. AgentSmith affiche le plan exact avant d’écrire quoi que ce soit.

L’assistant peut configurer un projet existant ou créer un dossier vide et initialiser Git pour un nouveau projet. L’application autonome inclut son environnement d’exécution ; Python n’est pas nécessaire.

### 2. Demander à votre agent

Collez ce texte dans Claude Code, Codex ou un autre agent de programmation :

```text
Install AgentSmith for this project. Follow the official agent guide at
https://github.com/PromptPartner/agentsmith/blob/master/AGENT-INSTALL.md
Inspect the project first, explain your profile recommendation in plain language,
show me the exact installation plan, and ask once before applying it.
```

L’agent inspecte le dépôt sans exécuter le code du projet, recommande un profil à partir d’éléments concrets, présente les fichiers gérés, installe AgentSmith et lance le diagnostic.

> La compilation d’AgentSmith à partir du code source est réservée aux contributeurs et à l’automatisation avancée. Consultez la [documentation de référence de l’installation](INSTALL.md).

## Nouveau projet ou projet existant ?

| Point de départ | Ce que fait AgentSmith | Ce qu’il ne fait pas |
|---|---|---|
| Projet existant | Il inspecte les fichiers, recommande un profil, préserve le contenu qui ne lui appartient pas et ajoute les règles gérées ainsi que la structure de vérification. | Il n’exécute pas le projet pendant l’inspection et ne remplace pas sa configuration existante. |
| Nouveau projet | Il crée ou valide un dossier vide, initialise Git et ajoute AgentSmith. | Il ne choisit ni ne génère de framework d’application. Votre agent peut construire l’application après la configuration. |

La configuration au niveau du projet est proposée par défaut, car les règles suivent le dépôt et peuvent être examinées par les autres contributeurs. Un socle commun à tous les projets d’un utilisateur est disponible dans les **Options avancées**. Une configuration en couches associe ce socle global à un petit profil propre au projet. Consultez les [configurations par projet, globales et en couches](INSTALL.md#where-the-rules-live).

## Profils de travail

Un profil indique à l’agent ce que signifie « terminé » pour le travail en cours. L’assistant recommande un profil et montre les fichiers sur lesquels repose son choix. Vous pouvez l’accepter ou afficher la liste complète.

| Profil | À utiliser pour | Preuve principale |
|---|---|---|
| `software-dev` | Fonctionnalités, corrections, refactorisations, applications, bibliothèques et interfaces produit | Compilation, contrôles, tests, contrôle de sécurité, exécution réelle |
| `devops-setup` | Programmes d’installation, CI, conteneurs, configuration et déploiements | Simulation, idempotence, retour arrière, parcours de déploiement réel |
| `marketing-outreach` | Campagnes, e-mails, newsletters, textes de pages de destination et travail dans le CRM | Relecture du public et des faits, liens, rendu, autorisation d’envoi |
| `document-creation` | Rapports, propositions, spécifications, manuels et wikis | Exactitude des sources, structure, liens, contrôle du fichier rendu |
| `data-crunching` | Nettoyage de données, analyse, SQL, indicateurs et ETL | Reproductibilité, totaux, cas limites, inspection du résultat |
| `general-admin` | Triage, planification, organisation, synthèses et opérations courantes | Exhaustivité, fidélité du résultat, destination et autorisations |
| `deep-research` | Diligence raisonnable, études de marché et recherches avec sources | Qualité des sources, couverture des affirmations, citations, contrôle de la synthèse |
| `creative-design` | Diagrammes, présentations, ressources de marque, images et vidéo | Brief, contrôle visuel et des exports, accessibilité, cohérence de marque |
| `security-audit` | Modèles de menaces, revues de sécurité, tests d’intrusion et audits IAM | Reproduction, preuve de gravité, correction, nouveau test |

`autonomous-loops` est un modificateur avancé pour le travail planifié ou sans supervision. Associez-le au profil de travail principal ; ne l’utilisez pas seul. Le [guide des profils](docs/07-how-to-pick-a-profile.md) explique les cas proches, le changement de profil et leur combinaison.

## Éléments installés

- `AGENTS.md` est l’accord de projet de référence. Claude Code reçoit également un fichier `CLAUDE.md` généré.
- `.harness/verify.conf` définit les vérifications réelles de ce projet.
- `.agentsmith/state.json` ne consigne que les paramètres appartenant à AgentSmith, afin que les mises à jour et la désinstallation préservent le reste du contenu.
- Des compétences, des serveurs MCP et des hooks facultatifs sont disponibles dans l’étape avancée, repliée par défaut.

Le mode d’autorisation prudent est sélectionné par défaut. AgentSmith ne considère jamais qu’un service externe connecté constitue une autorisation d’y écrire.

## Voir les preuves

La [Première boucle vérifiée](docs/demos/first-verified-loop/README.md) consigne un test en échec avant la correction, une vérification réussie après celle-ci, l’exécution d’une commande réelle, un reçu et une transmission permettant de reprendre le travail. Le [registre de compatibilité](config/agents.json) distingue la prise en charge des instructions du comportement natif testé.

## Documentation et communauté

- [Documentation de référence de l’installation](INSTALL.md)
- [Plan de la documentation](docs/README.md)
- [Comment la vérification devient une preuve](docs/03-verify-means-evidence.md)
- [Compatibilité avec les agents](docs/22-compatibility-contract.md)
- [Contribution](CONTRIBUTING.md) et [assistance](SUPPORT.md)
- [Politique de sécurité](SECURITY.md) et [code de conduite](CODE_OF_CONDUCT.md)

Sous licence MIT. Créé par [PromptPartner](https://promptpartner.ai/).
