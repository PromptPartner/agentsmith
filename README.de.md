<div align="center">
  <img src="site/assets/promptpartner-mark-amber.svg" width="72" height="72" alt="PromptPartner mark">
  <h1>AgentSmith</h1>
  <p><strong>Erst der Beleg, dann „fertig“.</strong> Gib deinem KI-Agenten Projektregeln, eine Definition von „fertig“ und eine Möglichkeit, seine Arbeit zu belegen.</p>
  <p>
    <a href="https://github.com/PromptPartner/agentsmith/actions/workflows/verify.yml"><img alt="Verification" src="https://github.com/PromptPartner/agentsmith/actions/workflows/verify.yml/badge.svg?branch=master"></a>
    <a href="https://github.com/PromptPartner/agentsmith/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/PromptPartner/agentsmith"></a>
    <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-14213D.svg"></a>
  </p>
  <p>
    <a href="README.md">English</a> · <strong>Deutsch</strong> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

AgentSmith installiert eine gemeinsame Arbeitsvereinbarung und ein Arbeitsprofil in einem Projekt. Dein Agent erhält klare Grenzen, führt die passenden Prüfungen aus, testet den tatsächlichen Ablauf, dokumentiert Belege und hinterlässt eine Übergabe, die eine spätere Sitzung nachvollziehen kann. Du behältst die Kontrolle über Schreibzugriffe auf externe Systeme.

![AgentSmith-Ablauf: Projektregeln und Profil, klar begrenzte Agentenarbeit, automatisierte Prüfungen und Test des tatsächlichen Ablaufs, Belege, danach Übergabe und Fortsetzung.](site/assets/agentsmith-flow.svg)

## AgentSmith einrichten

Wähle einen von zwei Wegen. Beide verwenden dieselbe geführte Einrichtung und erzeugen dieselben Projektdateien.

### 1. Manuell einrichten

1. Lade das signierte Installationsprogramm für macOS, Windows oder Linux aus der [neuesten Version](https://github.com/PromptPartner/agentsmith/releases/latest) herunter.
2. Öffne ein Terminal und führe `agentsmith` aus.
3. Beantworte die geführten Fragen. AgentSmith zeigt dir den genauen Plan, bevor es etwas schreibt.

Der Assistent kann ein bestehendes Projekt konfigurieren oder für ein neues Projekt einen leeren Ordner anlegen und Git initialisieren. Die eigenständige Anwendung enthält ihre Laufzeitumgebung; Python ist nicht erforderlich.

### 2. Deinen Agenten beauftragen

Füge diesen Text in Claude Code, Codex oder einen anderen Programmieragenten ein:

```text
Install AgentSmith for this project. Follow the official agent guide at
https://github.com/PromptPartner/agentsmith/blob/master/AGENT-INSTALL.md
Inspect the project first, explain your profile recommendation in plain language,
show me the exact installation plan, and ask once before applying it.
```

Der Agent untersucht das Repository, ohne Projektcode auszuführen, empfiehlt anhand der gefundenen Hinweise ein Profil, zeigt eine Vorschau der verwalteten Dateien, installiert AgentSmith und führt die Diagnoseprüfung aus.

> AgentSmith aus dem Quellcode zu erstellen ist für Mitwirkende und fortgeschrittene Automatisierung gedacht. Siehe die [Installationsreferenz](INSTALL.md).

## Neues oder bestehendes Projekt?

| Ausgangspunkt | Was AgentSmith macht | Was AgentSmith nicht macht |
|---|---|---|
| Bestehendes Projekt | Untersucht die Dateien, empfiehlt ein Profil, bewahrt fremde Inhalte und ergänzt verwaltete Regeln sowie ein Prüfgerüst. | Es führt bei der Untersuchung keinen Projektcode aus und ersetzt keine bestehende Projektkonfiguration. |
| Neues Projekt | Erstellt oder prüft einen leeren Ordner, initialisiert Git und fügt AgentSmith hinzu. | Es wählt oder erzeugt kein Anwendungsframework. Dein Agent kann die Anwendung nach der Einrichtung erstellen. |

Die Projekteinrichtung ist die Voreinstellung, weil die Regeln mit dem Repository weitergegeben und von Mitwirkenden geprüft werden können. Ein benutzerweit geltender Kern für alle Projekte ist unter **Erweiterte Optionen** verfügbar. Eine mehrschichtige Einrichtung kombiniert diesen benutzerweiten Kern mit einem kleinen projektspezifischen Profil. Siehe [projektbezogene, benutzerweite und mehrschichtige Einrichtungen](INSTALL.md#where-the-rules-live).

## Arbeitsprofile

Ein Profil sagt dem Agenten, was für die jeweilige Arbeit „fertig“ bedeutet. Der Assistent empfiehlt ein Profil und zeigt, auf welche Dateien er seine Wahl stützt. Du kannst es annehmen oder die vollständige Liste anzeigen.

| Profil | Geeignet für | Wichtigster Nachweis |
|---|---|---|
| `software-dev` | Funktionen, Fehlerbehebungen, Refactorings, Anwendungen, Bibliotheken und Produktoberflächen | Build, Prüfungen, Tests, Sicherheitsprüfung, echter Aufruf |
| `devops-setup` | Installationsprogramme, CI, Container, Konfiguration und Bereitstellungen | Probelauf, Idempotenz, Rücknahme, echter Bereitstellungsablauf |
| `marketing-outreach` | Kampagnen, E-Mail, Newsletter, Landingpage-Texte und CRM-Arbeit | Zielgruppen- und Faktenprüfung, Links, Darstellung, Sendefreigabe |
| `document-creation` | Berichte, Angebote, Spezifikationen, Handbücher und Wikis | Quellengenauigkeit, Struktur, Links, Prüfung der gerenderten Datei |
| `data-crunching` | Datenbereinigung, Analyse, SQL, Kennzahlen und ETL | Reproduzierbarkeit, Summen, Grenzfälle, Prüfung der Ausgabe |
| `general-admin` | Triage, Terminplanung, Organisation, Zusammenfassungen und Routineaufgaben | Vollständigkeit, originalgetreue Ausgabe, Ziel- und Freigabeprüfungen |
| `deep-research` | Due Diligence, Marktforschung und Untersuchungen mit Quellenangaben | Quellenqualität, Abdeckung der Aussagen, Quellenangaben, Prüfung der Synthese |
| `creative-design` | Diagramme, Präsentationen, Markenmaterial, Bilder und Videos | Briefing, Sicht- und Exportprüfung, Barrierefreiheit, Markenkonsistenz |
| `security-audit` | Bedrohungsmodelle, Sicherheitsprüfungen, Penetrationstests und IAM-Audits | Reproduktion, Schweregradbelege, Behebung, erneuter Test |

`autonomous-loops` ist eine erweiterte Ergänzung für geplante oder unbeaufsichtigte Arbeit. Kombiniere sie mit dem wichtigsten Arbeitsprofil; verwende sie nicht allein. Der [Profil-Leitfaden](docs/07-how-to-pick-a-profile.md) erklärt Grenzfälle, Wechsel und Kombinationen.

## Was installiert wird

- `AGENTS.md` ist die maßgebliche Projektvereinbarung. Claude Code erhält außerdem eine erzeugte `CLAUDE.md`.
- `.harness/verify.conf` definiert die tatsächlichen Prüfungen für dieses Projekt.
- `.agentsmith/state.json` speichert nur Einstellungen, die AgentSmith gehören, damit Aktualisierungen und das Entfernen fremde Inhalte bewahren.
- Optionale Skills, MCP-Server und Hooks sind im eingeklappten erweiterten Schritt verfügbar.

Der vorsichtige Berechtigungsmodus ist die Voreinstellung. AgentSmith betrachtet einen verbundenen externen Dienst niemals als Erlaubnis, darauf zu schreiben.

## Die Nachweise ansehen

Die [erste verifizierte Schleife](docs/demos/first-verified-loop/README.md) dokumentiert einen fehlschlagenden Test vor der Korrektur, eine danach erfolgreiche Prüfung, einen echten Befehlsaufruf, einen Nachweis und eine fortsetzbare Übergabe. Das [Support-Verzeichnis](config/agents.json) trennt die Unterstützung für Anweisungen von getestetem nativem Verhalten.

## Dokumentation und Community

- [Installationsreferenz](INSTALL.md)
- [Dokumentationsübersicht](docs/README.md)
- [Wie Prüfungen zu Belegen werden](docs/03-verify-means-evidence.md)
- [Agentenkompatibilität](docs/22-compatibility-contract.md)
- [Mitwirken](CONTRIBUTING.md) und [Support](SUPPORT.md)
- [Sicherheitsrichtlinie](SECURITY.md) und [Verhaltenskodex](CODE_OF_CONDUCT.md)

MIT-lizenziert. Erstellt von [PromptPartner](https://promptpartner.ai/).
