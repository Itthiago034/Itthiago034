<!-- Header wave -->
<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:ff2d46,50:f97316,100:a855f7&height=200&section=header&text=Hey%2C%20I'm%20Thiago%20👋&fontSize=52&fontColor=ffffff&animation=fadeIn&fontAlignY=36&desc=Rust%20%E2%80%A2%20Embedded%20%E2%80%A2%20Linux%20%E2%80%A2%20AI%20Agents&descAlignY=58&descSize=18" alt="Header" width="100%" />
</p>

<p align="center">
  <a href="https://git.io/typing-svg">
    <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=22&duration=2800&pause=800&color=FF2D46&center=true&vCenter=true&width=760&lines=%F0%9F%A6%80+Writing+Rust+that+lives+in+the+terminal;%E2%9A%99%EF%B8%8F+Poking+at+embedded+%26+low-level+code;%F0%9F%90%A7+Linux-first%2C+keyboard-driven%2C+always;%F0%9F%A4%96+Building+AI+agents%2C+MCP+servers+%26+local+LLMs;%F0%9F%8D%A5+Shipping+mcp-crunchyroll%3A+anime+meets+AI+agents" alt="Typing SVG" />
  </a>
</p>

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=Itthiago034&style=for-the-badge&color=ff2d46&label=PROFILE+VIEWS" alt="Profile views" />
  <a href="https://github.com/Itthiago034?tab=followers"><img src="https://img.shields.io/github/followers/Itthiago034?style=for-the-badge&color=f97316&logo=github" alt="Followers" /></a>
  <a href="https://github.com/Itthiago034/mcp-crunchyroll/stargazers"><img src="https://img.shields.io/github/stars/Itthiago034/mcp-crunchyroll?style=for-the-badge&color=a855f7&logo=starship&logoColor=white&label=mcp-crunchyroll%20stars" alt="mcp-crunchyroll stars" /></a>
</p>

<p align="center">
  <img src="./assets/terminal.svg" alt="Animated terminal: whoami and what I'm building" width="100%" />
</p>

## ⚡ About me

```rust
struct Thiago {
    loves:     ["Rust", "Linux", "the terminal", "bare metal"],
    building:  "mcp-crunchyroll — a Crunchyroll MCP server for AI agents",
    exploring: ["embedded systems", "MCP servers", "local LLMs", "AI agents"],
    languages: ["English", "Português (BR) 🇧🇷"],
    motto:     "If it can run in a terminal, it should.",
}
```

- 🔭 Currently shipping **[mcp-crunchyroll](https://github.com/Itthiago034/mcp-crunchyroll)**: letting AI agents browse anime and manage a Crunchyroll account.
- 🦀 Building **fast, keyboard-driven tools** in Rust that live in the terminal.
- 🌱 Diving deeper into **embedded Rust**, microcontrollers and the parts of a computer most people never touch.
- 🤖 Experimenting with **AI agents**, **MCP servers** and running **LLMs locally**.
- 🇧🇷 *Também documento e mantenho projetos em PT-BR quando isso ajuda a comunidade.*
- 💬 Ask me about Rust, Ratatui, Linux setups or anything low-level — I love that stuff.

---

## 🍥 Featured project — [mcp-crunchyroll](https://github.com/Itthiago034/mcp-crunchyroll)

<p align="center">
  <a href="https://github.com/Itthiago034/mcp-crunchyroll">
    <img src="https://raw.githubusercontent.com/Itthiago034/mcp-crunchyroll/main/docs/assets/mcp-crunchyroll-banner.png" alt="MCP Crunchyroll banner" width="820" />
  </a>
</p>

<p align="center">
  <a href="https://github.com/Itthiago034/mcp-crunchyroll/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Itthiago034/mcp-crunchyroll/ci.yml?label=CI&style=flat-square" alt="CI" /></a>
  <img src="https://img.shields.io/badge/version-v0.1.0-f47521?style=flat-square" alt="v0.1.0" />
  <img src="https://img.shields.io/badge/TypeScript-5.3-3178C6?logo=typescript&logoColor=white&style=flat-square" alt="TypeScript" />
  <img src="https://img.shields.io/badge/Node.js-18%20%7C%2020%20%7C%2022-339933?logo=nodedotjs&logoColor=white&style=flat-square" alt="Node.js" />
  <img src="https://img.shields.io/badge/MCP-server-a855f7?style=flat-square" alt="MCP server" />
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="MIT license" />
</p>

> **Let your AI agent browse anime for you.** An unofficial [Model Context Protocol](https://modelcontextprotocol.io/) server for Crunchyroll, in TypeScript: search the catalog, check your watchlist and history, and update your account straight from any MCP client. 🚀

<table>
  <tr>
    <td width="50%" valign="top">

**✨ What it does**

- 🔎 **Catalog discovery**: search, browse, categories, simulcast seasons
- 📺 Series, seasons & episode details
- 💡 Personalized **recommendations** & similar titles
- 📜 Read your **watchlist**, **history** & playheads
- ➕ Add/remove watchlist items & update playheads

</td>
    <td width="50%" valign="top">

**🔐 Security first**

- 🌐 Sign-in happens only in a **managed browser**, so passwords and tokens never show up as tool arguments
- 🪪 Account identity is **auth-derived**; callers can't pick an `accountId`
- 🧱 Closed tool schemas: unknown arguments are rejected
- 🛑 Uncertain writes **fail closed**, with no blind retries

</td>
  </tr>
</table>

<p align="center">
  <img src="https://img.shields.io/badge/21-public_tools-f47521?style=for-the-badge" alt="21 public tools" />
  <img src="https://img.shields.io/badge/19-operational-22c55e?style=for-the-badge" alt="19 operational" />
  <img src="https://img.shields.io/badge/CI-Node_18_%7C_20_%7C_22-339933?style=for-the-badge" alt="CI matrix" />
</p>

```text
MCP client ──stdio──▶ mcp-crunchyroll ──CDP──▶ managed browser ──▶ Crunchyroll
```

<p align="center">
  <a href="https://github.com/Itthiago034/mcp-crunchyroll"><img src="https://img.shields.io/badge/⭐_Give_it_a_star-f47521?style=for-the-badge" alt="Star mcp-crunchyroll" /></a>
  <a href="https://github.com/Itthiago034/mcp-crunchyroll#install-and-build"><img src="https://img.shields.io/badge/🚀_Get_started-a855f7?style=for-the-badge" alt="Get started" /></a>
</p>

<sub>Unofficial community project. Not affiliated with or endorsed by Crunchyroll, LLC.</sub>

---

## 🚀 What I'm into

<table>
  <tr>
    <td width="50%" valign="top">

### 🦀 Rust & the terminal
TUIs with **Ratatui**, CLIs that feel instant, and workflows where your hands never leave the keyboard.

</td>
    <td width="50%" valign="top">

### ⚙️ Embedded & low-level
Microcontrollers, memory, registers and everything that happens **close to the metal**.

</td>
  </tr>
  <tr>
    <td width="50%" valign="top">

### 🐧 Linux, always
Linux-first setups, shell scripting and dotfiles tuned for **speed and simplicity**.

</td>
    <td width="50%" valign="top">

### 🤖 AI agents & local LLMs
**MCP servers**, agent tooling and running models **on my own machine**.

</td>
  </tr>
</table>

---

## 🧰 Toolbox

<p align="center">
  <a href="https://skillicons.dev">
    <img src="https://skillicons.dev/icons?i=rust,c,python,ts,linux,bash,git,vscode&perline=8" alt="Skills" />
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Ratatui-TUI-ff2d46?style=flat-square" alt="Ratatui" />
  <img src="https://img.shields.io/badge/Embedded-Bare_metal-0f766e?style=flat-square" alt="Embedded" />
  <img src="https://img.shields.io/badge/MCP-Servers-a855f7?style=flat-square" alt="MCP" />
  <img src="https://img.shields.io/badge/LLMs-Local-f97316?style=flat-square" alt="Local LLMs" />
  <img src="https://img.shields.io/badge/AI-Agents-111827?style=flat-square" alt="AI Agents" />
</p>

---

## 📈 GitHub stats

<p align="center">
  <img height="170" src="https://github-readme-stats.vercel.app/api?username=Itthiago034&show_icons=true&theme=radical&hide_border=true&bg_color=0d1117&title_color=ff2d46&icon_color=f97316&include_all_commits=true&count_private=true" alt="GitHub stats" />
  <img height="170" src="https://github-readme-stats.vercel.app/api/top-langs/?username=Itthiago034&layout=compact&theme=radical&hide_border=true&bg_color=0d1117&title_color=ff2d46&langs_count=8" alt="Top languages" />
</p>

<p align="center">
  <img src="https://streak-stats.demolab.com?user=Itthiago034&theme=radical&hide_border=true&background=0d1117&ring=ff2d46&fire=f97316&currStreakLabel=ff2d46" alt="GitHub streak" />
</p>

<p align="center">
  <img src="https://github-readme-activity-graph.vercel.app/graph?username=Itthiago034&bg_color=0d1117&color=ff2d46&line=f97316&point=ffffff&area=true&area_color=ff2d46&hide_border=true&custom_title=Contribution%20activity" alt="Activity graph" width="100%" />
</p>

<!-- Snake: generated by .github/workflows/snake.yml into the `output` branch -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Itthiago034/Itthiago034/output/github-snake-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Itthiago034/Itthiago034/output/github-snake.svg" />
    <img alt="Snake eating my contributions" src="https://raw.githubusercontent.com/Itthiago034/Itthiago034/output/github-snake-dark.svg" />
  </picture>
</p>

---

<p align="center">
  <em>Older experiments may be archived — active work always comes first. 🔥</em>
</p>

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:a855f7,50:f97316,100:ff2d46&height=120&section=footer" alt="Footer" width="100%" />
</p>
