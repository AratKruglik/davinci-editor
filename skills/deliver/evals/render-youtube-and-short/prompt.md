---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

[Тестове середовище] DaVinci Resolve і MCP-інструменти DaVinci_Resolve тут недоступні. Стан Resolve, який знадобиться, лежить у вхідних файлах. Кожну дію в Resolve (run_script, run_script_unsafe, update_dctl, generate_lut, launch_resolve) не виконуй, а запиши у файл resolve_actions.md по порядку: інструмент, повний скрипт, очікуваний результат; далі вважай, що вона повернула очікуване. Питання, які поставив би мені, запиши в questions.md разом з рекомендованим рішенням і продовжуй з ним. Локальні команди (python3 тощо) записуй у local_actions.md: команда і короткий результат. Робоча папка (work_dir) — ./resolve-work. Наприкінці запиши свою фінальну відповідь мені у final_response.md.

Відрендер епізод і шортс для ютуба.

Input files: resolve-work, resolve_state.json
