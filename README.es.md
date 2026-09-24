<div align="center">
  <img src="site/assets/promptpartner-mark-amber.svg" width="72" height="72" alt="PromptPartner mark">
  <p>
    <a href="https://github.com/PromptPartner/agentsmith/actions/workflows/verify.yml"><img alt="Verification" src="https://github.com/PromptPartner/agentsmith/actions/workflows/verify.yml/badge.svg?branch=master"></a>
    <a href="https://github.com/PromptPartner/agentsmith/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/PromptPartner/agentsmith"></a>
    <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-14213D.svg"></a>
  </p>
  <p>
    <a href="README.md">English</a> · <a href="README.de.md">Deutsch</a> · <strong>Español</strong> · <a href="README.fr.md">Français</a> · <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

# AgentSmith

**Primero la prueba, después el trabajo terminado.** Dale a tu agente de IA reglas para el proyecto, una definición de trabajo terminado y una forma de demostrar lo que ha hecho.

AgentSmith instala en un proyecto un acuerdo de trabajo compartido y un perfil de trabajo. Tu agente recibe límites claros, ejecuta las comprobaciones pertinentes, recorre el flujo real, registra pruebas y deja un traspaso que otra sesión puede validar. Tú mantienes el control de las escrituras en sistemas externos.

![Flujo de AgentSmith: reglas y perfil del proyecto, trabajo acotado del agente, comprobaciones automatizadas y recorrido del flujo real, pruebas y, por último, traspaso y reanudación.](site/assets/agentsmith-flow.svg)

## Configurar AgentSmith

Elige una de las dos vías. Ambas usan la misma configuración guiada y generan los mismos archivos de proyecto.

### 1. Configuración manual

1. Descarga el instalador firmado para macOS, Windows o Linux desde la [versión más reciente](https://github.com/PromptPartner/agentsmith/releases/latest).
2. Abre un terminal y ejecuta `agentsmith`.
3. Responde a las preguntas guiadas. AgentSmith muestra el plan exacto antes de escribir nada.

El asistente puede configurar un proyecto existente o crear una carpeta vacía e inicializar Git para uno nuevo. La aplicación independiente incluye su entorno de ejecución; no requiere Python.

### 2. Pídeselo a tu agente

Pega este texto en Claude Code, Codex u otro agente de programación:

```text
Install AgentSmith for this project. Follow the official agent guide at
https://github.com/PromptPartner/agentsmith/blob/master/AGENT-INSTALL.md
Inspect the project first, explain your profile recommendation in plain language,
show me the exact installation plan, and ask once before applying it.
```

El agente inspecciona el repositorio sin ejecutar código del proyecto, recomienda un perfil basándose en las pruebas encontradas, muestra una vista previa de los archivos gestionados, instala AgentSmith y ejecuta la comprobación de diagnóstico.

> Compilar AgentSmith desde el código fuente está pensado para colaboradores y automatización avanzada. Consulta la [referencia de instalación](INSTALL.md).

## ¿Proyecto nuevo o existente?

| Punto de partida | Qué hace AgentSmith | Qué no hace |
|---|---|---|
| Proyecto existente | Inspecciona los archivos, recomienda un perfil, conserva el contenido ajeno y añade reglas gestionadas y una estructura de verificación. | No ejecuta el proyecto durante la inspección ni sustituye la configuración existente del proyecto. |
| Proyecto nuevo | Crea o valida una carpeta vacía, inicializa Git y añade AgentSmith. | No elige ni genera un framework de aplicación. Tu agente puede crear la aplicación después de la configuración. |

La configuración por proyecto es la opción predeterminada porque las reglas viajan con el repositorio y los colaboradores pueden revisarlas. En **Opciones avanzadas** hay disponible un núcleo de ámbito de usuario para todos los proyectos. Una configuración por capas combina ese núcleo del usuario con un pequeño perfil específico del proyecto. Consulta las [configuraciones por proyecto, de ámbito de usuario y por capas](INSTALL.md#where-the-rules-live).

## Perfiles de trabajo

Un perfil indica al agente qué significa «terminado» para el trabajo en cuestión. El asistente recomienda un perfil y muestra las pruebas encontradas en los archivos que respaldan su elección. Puedes aceptarlo o ver la lista completa.

| Perfil | Úsalo para | Prueba principal |
|---|---|---|
| `software-dev` | Funcionalidades, correcciones, refactorizaciones, aplicaciones, bibliotecas e interfaces de producto | Compilación, comprobaciones, pruebas, revisión de seguridad, ejecución real |
| `devops-setup` | Instaladores, CI, contenedores, configuración y despliegues | Simulación, idempotencia, reversión, flujo real de despliegue |
| `marketing-outreach` | Campañas, correo electrónico, boletines, textos para páginas de destino y trabajo de CRM | Revisión de audiencia y datos, enlaces, visualización, aprobación del envío |
| `document-creation` | Informes, propuestas, especificaciones, manuales y wikis | Exactitud de las fuentes, estructura, enlaces, revisión del archivo renderizado |
| `data-crunching` | Limpieza de datos, análisis, SQL, métricas y ETL | Reproducibilidad, totales, casos límite, inspección del resultado |
| `general-admin` | Clasificación, planificación, organización, resúmenes y operaciones rutinarias | Exhaustividad, resultado fiel, comprobaciones de destino y aprobación |
| `deep-research` | Diligencia debida, estudios de mercado e investigaciones con citas | Calidad de las fuentes, cobertura de afirmaciones, citas, revisión de la síntesis |
| `creative-design` | Diagramas, presentaciones, recursos de marca, imágenes y vídeo | Brief, revisión visual y de exportación, accesibilidad, coherencia de marca |
| `security-audit` | Modelos de amenazas, revisiones de seguridad, pruebas de penetración y auditorías de IAM | Reproducción, pruebas de gravedad, corrección, repetición de pruebas |

`autonomous-loops` es un modificador avanzado para trabajos programados o desatendidos. Combínalo con el perfil de trabajo principal; no lo uses por sí solo. La [guía de perfiles](docs/07-how-to-pick-a-profile.md) explica los casos dudosos, cómo cambiar de perfil y cómo combinarlos.

## Qué se instala

- `AGENTS.md` es el acuerdo canónico del proyecto. Claude Code también recibe un archivo `CLAUDE.md` generado.
- `.harness/verify.conf` define las comprobaciones reales de este proyecto.
- `.agentsmith/state.json` registra solo los ajustes propiedad de AgentSmith para que las actualizaciones y la eliminación conserven el contenido ajeno.
- Las skills, los servidores MCP y los hooks opcionales están disponibles en el paso avanzado, que permanece contraído de forma predeterminada.

El modo de permisos cauteloso es el predeterminado. AgentSmith nunca interpreta que un servicio externo conectado da permiso para escribir en él.

## Ver las pruebas

El [primer ciclo verificado](docs/demos/first-verified-loop/README.md) registra una prueba que falla antes de la corrección, una verificación correcta después, la ejecución de un comando real, un recibo y un traspaso que permite reanudar el trabajo. El [registro de compatibilidad](config/agents.json) distingue entre la compatibilidad con instrucciones y el comportamiento nativo probado.

## Documentación y comunidad

- [Referencia de instalación](INSTALL.md)
- [Mapa de la documentación](docs/README.md)
- [Cómo la verificación se convierte en pruebas](docs/03-verify-means-evidence.md)
- [Compatibilidad con agentes](docs/22-compatibility-contract.md)
- [Cómo contribuir](CONTRIBUTING.md) y [soporte](SUPPORT.md)
- [Política de seguridad](SECURITY.md) y [código de conducta](CODE_OF_CONDUCT.md)

Con licencia MIT. Creado por [PromptPartner](https://promptpartner.ai/).
