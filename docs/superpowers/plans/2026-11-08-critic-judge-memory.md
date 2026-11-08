# Критик, суддя і пам'ять правок — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** три нові скіли плагіна `davinci-editor` — `frame-critic`, `edit-judge`, `edit-memory` — і їхнє підключення до наявних скілів.

**Architecture:** скіли-власники записують кожен поставлений у кадр елемент у спільний журнал `placed-<timeline>.json`; критик будує з нього інвентар, перевіряє числа, межі (різниця двох рендерів) і кадр очима, повертає правки власникам. Пам'ять порівнює знімки таймлайну (за `GetUniqueId()`, з компенсацією ripple), веде журнал подій і правила, які затверджує користувач. Суддя — ізольований агент: метрики скриптом, рубрика, детермінований вердикт, сліпий попарний вибір.

**Tech Stack:** Python 3.10+ лише stdlib; SKILL.md (Claude Code / Cowork plugin); DaVinci Resolve Studio 21.2 через MCP `mcp__DaVinci_Resolve__*`.

**Spec:** [docs/superpowers/specs/2026-11-08-critic-judge-memory-design.md](../specs/2026-11-08-critic-judge-memory-design.md)

## Global Constraints

- Передумова: виправлено вставку титрів у `fusion-motion-graphics` під 21.2 (окрема задача «Fix Fusion title insert with locked tracks (21.2)»). Без неї Task 5 не перевірити вживу.
- Робота в гілці `feature/critic-judge-memory`, не в `main`; без push.
- Скрипти: Python 3.10+, лише стандартна бібліотека; кожен має `selftest` (`python3 <script> selftest` друкує `<name> selftest ok`).
- Кожен новий selftest — у README «Development» і в `.github/workflows/release.yml`, в обох.
- Інструменти лише з префіксом `mcp__DaVinci_Resolve__` (не `_Studio`).
- Скіли з `run_script` мають hook `guard.py` у frontmatter, як `pre-delivery-qc`.
- Нові виклики 21.1.2+ — під version gate `resolve-core` §10.
- SKILL.md, README і `docs/skills/*.md` — англійською; `docs/` дизайн-нотатки — українською. Скіли говорять мовою користувача, назви UI Resolve англійською.
- Вихідні файли — лише під `${user_config.work_dir}/<project>/` (окрім файлів пам'яті, §6.5 спеку); ніколи в медіапапки.
- Знахідки й записи журналів змінюються лише через CLI скриптів, не редагуванням JSON.
- Маркери Claude — лише Cream з `customData` `claude:…`; маркери користувача не змінюються.
- Пороги зі спеку: час читання `0.5 + chars/14` с, мінімум 3 с для `lower-third`; близькість до склейки 6 кадрів; action-safe 5 %, title-safe 10 %; не більше 2 кіл критика; статичний відрізок 20 с (`youtube`) / 4 с (`shorts`); хук-вікно 30 с / 3 с; кандидат у правило — ≥ 2 події в один бік.

## Review Focus

1. Користувач видалив елемент, що є в журналі `placed` → критик пропускає його з приміткою, а не падає й не звітує помилку на неіснуючий елемент. Тест — Task 2.
2. Таймлайн починається з 01:00:00:00 (`start_frame` 86400 при 24 fps) → журнал і знахідки в абсолютних кадрах, а офсет для `ExportFrame` = `frame - start_frame`. Тест — Task 2 і Task 3.
3. Користувач вирізав шматок на початку **і** зсунув один титр → `diff` дає одну подію `moved`, а не зсув для кожного елемента. Тест — Task 6.
4. Файлу пам'яті ще немає (перший запуск) → `rules` повертає порожній список, `learn` створює файли. Тест — Task 7.
5. `pick` з одним кандидатом або з нічиєю на першому місці → один кандидат повертається без порівнянь; нічия позначається `"tie": true` для вибору користувачем. Тест — Task 9.

---

### Task 1: Журнал поставлених елементів `placed.py`

**Files:**
- Create: `skills/resolve-core/scripts/placed.py`
- Modify: `README.md` (Development), `.github/workflows/release.yml`

**Interfaces:**
- Produces:
  - `add(path: str, entry: dict) -> dict` — додає або замінює запис з тим самим `item_id`, повертає весь журнал `{"timeline_id": str, "items": [entry...]}`.
  - `load(path: str) -> dict` — порожній журнал `{"timeline_id": None, "items": []}`, якщо файлу немає.
  - Запис: `{"item_id": str, "owner": str, "kind": str, "spec": str|None, "track": str, "start": int, "end": int, "full": int, "hold_end": int, "gone": int, "text": str, "scale": float|None}` — усі кадри абсолютні (кадри таймлайну, як `item.GetStart()`). `kind` ∈ `lower-third, callout, kinetic, counter, zoom, caption, pip`.
  - CLI: `placed.py add <ledger> --timeline-id ID --item-id ID --owner SKILL --kind KIND --track NAME --start F --end F --full F --hold-end F --gone F [--spec PATH] [--text T] [--scale S]`; `placed.py selftest`.

- [ ] **Step 1: Гілка.** `git checkout -b feature/critic-judge-memory`; закомітити спек і цей план: `git add docs/superpowers && git commit -m "Add design and plan for critic, judge and edit memory"`.
- [ ] **Step 2: Тест `selftest()`** у `placed.py`: новий журнал з тимчасової теки порожній; `add` двох записів → 2 елементи; повторний `add` з тим самим `item_id` і іншим `start` → усе ще 2, `start` новий; `--kind wrong` → `SystemExit`; `timeline_id` іншого таймлайну в наявному журналі → `SystemExit` з текстом `"different timeline"`.
- [ ] **Step 3:** `python3 skills/resolve-core/scripts/placed.py selftest` → падає (немає функцій).
- [ ] **Step 4: Реалізувати** `add`, `load`, CLI (`argparse`, запис `json.dump(..., ensure_ascii=False, indent=1)`, створення теки).
- [ ] **Step 5:** selftest → `placed selftest ok`. Додати рядок у README «Development» і `release.yml` після `timeline_map.py selftest`.
- [ ] **Step 6: Commit** `git add skills/resolve-core/scripts/placed.py README.md .github/workflows/release.yml && git commit -m "resolve-core: ledger of elements placed by skills"`.

### Task 2: `critic.py` — інвентар і числові перевірки

**Files:**
- Create: `skills/frame-critic/scripts/critic.py`
- Modify: `skills/resolve-core/reference.md` (timeline dump: поле `"item_id": it.GetUniqueId()` у `items()`), `README.md`, `.github/workflows/release.yml`

**Interfaces:**
- Consumes: `placed.load` (Task 1); `qc.state_of`, `qc.stale`, `qc.summarize`, `qc.ORDER` з `skills/pre-delivery-qc/scripts/qc.py` (через `sys.path.insert`, як інші скрипти); `tc.frames_to_tc`.
- Produces:
  - `inventory(ledger: dict, dump: dict) -> tuple[list[dict], list[str]]` — елементи (запис журналу + `id` = `"<owner>/<item_id>"`, `mid` = `(full + hold_end) // 2`) і примітки про записи, яких немає в dump (видалені користувачем). Пошук елемента в dump лише за `item_id`.
  - `check(elements: list, dump: dict, cfg: dict) -> dict` — результат формату спеку §4.4 (`findings`, `state`, `verdict`, `counts`, `round: 1`). `cfg`: `{"cut_margin": 6, "zoom_max": float, "cps_max": float, "chars_max": int, "hold_extra_s": {kind: float}}`.
  - `add_finding(result: dict, **finding) -> dict`; `next_round(result: dict) -> dict`.
  - CLI: `critic.py inventory <ledger> <dump> --out elements.json`; `critic.py check <elements.json> <dump> --zoom-max Z --cps-max C --chars-max N [--rules rules.json] --out critic.json`; `critic.py add <critic.json> --severity S --kind K --element ID --tc TC --message M [--still P] [--bbox x0 y0 x1 y1] [--fix-skill S --fix-change C]`; `critic.py stale <critic.json> <dump>` (exit 1 = застарів); `critic.py selftest`.

Правила `check` (kind знахідки → умова):
- `short-hold` (error): текстовий елемент, `(hold_end - full)/fps < 0.5 + len(text)/14 + hold_extra_s[kind]`, або `< 3 + hold_extra_s` для `lower-third`.
- `overlap` (error): два текстові елементи з перетином `[full, gone)`, якщо жоден з них не `callout`.
- `near-cut` (warn): `start` або `gone` ближче ніж `cut_margin` кадрів до межі елемента на доріжці з роллю `A-roll` або `Screen` (без початку й кінця таймлайну).
- `zoom-scale` (error): `kind == "zoom"` і `scale > zoom_max`.
- `cps` (warn): `kind == "caption"` і `len(text) / ((gone - full)/fps) > cps_max`; `chars` (warn): рядок довший за `chars_max`.

`--rules` — вихід `memory.py rules` (Task 7): правило з `param.name == "hold_extra_s"` дає `cfg["hold_extra_s"][scope.kind]`; з `param.name == "max_scale"` — `zoom_max = min(zoom_max, value)`; інші правила критик ігнорує (їх перевіряє суддя). Поки Task 7 немає — `--rules` не передається.

- [ ] **Step 1: Тести в `selftest()`** (dump з `start_frame` 86400, fps 24, A-roll з двома кліпами, межа 86600):
  - `lower-third` «Олексій Круглик» з hold 2 с → `short-hold`; той самий з hold 3,5 с → без знахідки; з `hold_extra_s {"lower-third": 1.0}` і hold 3,5 с → `short-hold`.
  - `kinetic` і `lower-third` з перетином → `overlap`; `callout` + `lower-third` з перетином → без `overlap`.
  - елемент з `start` 86603 → `near-cut`; 86610 → немає.
  - `zoom` 2.8 при `zoom_max` 2.5 → `zoom-scale`.
  - запис журналу з `item_id`, якого немає в dump → не в елементах, є в примітках (Review Focus 1).
  - `tc` знахідки на 86600 = `"01:00:08:08"` (Review Focus 2).
  - `stale` false для того ж dump, true після видалення елемента; `next_round` → `round == 2`; третій виклик `next_round` → `SystemExit` (`"max 2 rounds"`).
- [ ] **Step 2:** `python3 skills/frame-critic/scripts/critic.py selftest` → падає.
- [ ] **Step 3: Реалізувати** функції й CLI; `state`, `stale`, `summarize` — з `qc.py`, не копією.
- [ ] **Step 4:** selftest → `critic selftest ok`; рядок у README і `release.yml`.
- [ ] **Step 5: Commit** `"frame-critic: inventory and numeric checks"`.

### Task 3: `critic.py bbox` — межі за різницею двох рендерів

**Files:**
- Modify: `skills/frame-critic/scripts/critic.py`

**Interfaces:**
- Consumes: `chart_match.read_tiff(path) -> (w, h, pixel(x, y) -> (r, g, b) у 0..1)`; `thumbs.write_tiff(path, w, h, rgb_fn)` для тестів.
- Produces:
  - `bbox_diff(on_path: str, off_path: str, threshold: float = 0.04, step: int = 2) -> list[int] | None` — `[x0, y0, x1, y1]` пікселів, де `max(|Δr|, |Δg|, |Δb|) > threshold`; `None`, якщо різниці немає; різні розміри файлів → `SystemExit`.
  - `safe_kinds(bbox: list, w: int, h: int) -> list[tuple[str, str]]` — `("offscreen", "error")`, якщо межа торкається краю кадру (`x0 <= 0` або `x1 >= w - 1`, так само y); інакше `("unsafe", "error")` за межами action-safe 5 %; інакше `("unsafe-title", "warn")` за межами title-safe 10 %; інакше `[]`.
  - CLI: `critic.py bbox <on.tif> <off.tif>` → JSON `{"bbox", "width", "height", "kinds"}`.

- [ ] **Step 1: Тести:** синтетичні 192×108 TIF: фон-градієнт однаковий в обох; у `on` — **темний** прямокутник (0.05) x 150..191 → `bbox` x1 = 191, `kinds` містить `offscreen`; прямокутник x 20..60, y 20..40 → `kinds == []`; прямокутник x 5..60 → `unsafe-title` ні, `unsafe` так (5 % від 192 = 9.6); однакові файли → `None`; різні розміри → `SystemExit`.
- [ ] **Step 2:** selftest → падає на нових асертах.
- [ ] **Step 3: Реалізувати** `bbox_diff`, `safe_kinds`, підкоманду `bbox`.
- [ ] **Step 4:** selftest → `critic selftest ok`.
- [ ] **Step 5: Commit** `"frame-critic: measured text bounds from two renders"`.

### Task 4: Скіл `frame-critic`

**Files:**
- Create: `skills/frame-critic/SKILL.md`, `skills/frame-critic/reference.md`, `skills/frame-critic/evals/title-offscreen/{case.yaml,prompt.md,place-files.sh,graders/01..05-*.md,files/resolve_state.json,files/resolve-work/<project>/{timeline-<tl>.json,placed-<tl>.json,critic/*.tif}}`, `docs/skills/frame-critic.md`
- Modify: `README.md` (розділ Skills)

**Interfaces:**
- Consumes: `critic.py` CLI (Tasks 2–3), `placed-<timeline>.json` (Task 1), timeline dump (`resolve-core/reference.md#timeline-dump`).
- Produces: `<work>/critic-<timeline>.json` (спек §4.4) і `<work>/critic-<timeline>.md`; Cream-маркери `claude:critic:<kind>`; аргументи скіла `[timeline] [all|<owner skill>]`.

SKILL.md (англійською), розділи за зразком `pre-delivery-qc`: frontmatter (`name`, `description`, `when_to_use` з тригерами «перевір титри», «чи не вилазить текст», «critic», `argument-hint`, `arguments: [timeline, scope]`, `allowed-tools`: `get_resolve_status`, `search_scripting_api`, `get_scripting_api`, `get_image`, `get_thumbnails`, `Bash(python3 *critic.py *)`, `Bash(python3 *placed.py *)`, `Read`; hook `guard.py`); §1 інвентар і числа; §2 межі; §3 очима (спек §4.3 п. 3); §4 цикл виправлень (спек §4.5); §5 звіт; Never (спек §4.7).

`reference.md`: Resolve-скрипт для одного елемента — запис `GetIsTrackEnabled` усіх відео-доріжок, `ExportFrame(full - start_frame, …on.tif)`, вимкнення доріжки елемента, `ExportFrame(…off.tif)`, відновлення в `finally`, повторне читання і `result = {"restored": all(...)}`; Mac-шлях і Cowork-mapping (`resolve-core` §8).

- [ ] **Step 1: Eval-фікстура** `title-offscreen`: dump з таймлайном на 01:00:00:00, журнал із трьома елементами (лоуер-терд за правим краєм, kinetic з hold 1,5 с, callout поверх запису екрана), готові `on/off` TIF (з Task 3 генератора) і `get_image`-кадри в `resolve_state.json` за зразком наявних evals.
- [ ] **Step 2: Грейдери:** `01` знаходить `offscreen` з таймкодом і bbox; `02` знаходить `short-hold` у kinetic; `03` не звітує callout як `overlap`; `04` кожна знахідка має `fix.skill` і конкретну зміну специфікації; `05` нічого не рухає й не видаляє на таймлайні, стан доріжок відновлено в тому ж скрипті.
- [ ] **Step 3: Написати** SKILL.md і reference.md.
- [ ] **Step 4:** `claude plugin validate .` → без помилок; `claude plugin eval . --allow-tools Write,Edit,Bash --scaffold` лише для `frame-critic/title-offscreen` (платний запуск — спитати користувача) → грейдери проходять.
- [ ] **Step 5:** README Skills — рядок про `frame-critic`; `docs/skills/frame-critic.md` (англ.) за зразком сусідніх гайдів.
- [ ] **Step 6: Commit** `"Add frame-critic skill"`.

### Task 5: Власники пишуть журнал і приймають правки; QC читає вердикт критика

**Files:**
- Modify: `skills/fusion-motion-graphics/SKILL.md` (§3 після кроку 4, §5), `skills/tutorial-zooms/SKILL.md`, `skills/subtitles-uk/SKILL.md` (режим shorts), `skills/dual-video-sync-pip/SKILL.md`, `skills/shorts-cutdown/SKILL.md`, `skills/pre-delivery-qc/SKILL.md` (§2 «Looks»), `skills/edit-episode/SKILL.md` (стадія D)
- Modify evals цих скілів, якщо грейдери перевіряють старий «Looks» QC.

**Interfaces:**
- Consumes: `placed.py add` (Task 1), `frame-critic` (Task 4).
- Produces: кожен власник після встановлення елемента викликає `placed.py add` з `item.GetUniqueId()` і кадрами `full/hold_end/gone`:
  - графіка: `full = start + (visible[0] - comp_start) + timing_frames.in`, `gone = start + (visible[1] - comp_start)`, `hold_end = gone - timing_frames.out`;
  - зум: `full = start + ease frames`, `hold_end = end - ease frames`, `gone = end`, `scale`;
  - субтитр Shorts: кадри групи з `captions.json`; PiP: межі сегмента `pip-plan.json`.
- Наприкінці — виклик `frame-critic <timeline> <owner>`; розділ «Fix from frame-critic»: прийняти `fix.change`, змінити лише свою специфікацію, перезастосувати лише ці елементи, оновити журнал.

- [ ] **Step 1:** Правки п'яти SKILL.md власників (журнал + виклик критика + прийом правки).
- [ ] **Step 2:** `pre-delivery-qc` §2: «Looks» → `critic.py stale` / вердикт (спек §4.6); kinds `critic-stale` (warn) і `look` (error).
- [ ] **Step 3:** `edit-episode`: критик після кожного кроку стадії D, що ставить елементи в кадр.
- [ ] **Step 4:** `claude plugin validate .`; selftest-и `motion.py`, `zooms.py`, `subtitles.py`, `pip_plan.py`, `shorts.py`, `qc.py` → ok.
- [ ] **Step 5: Жива перевірка** на тестовому таймлайні `claude-probe-critic` (не `Timeline 3`): один лоуер-терд через `fusion-motion-graphics` → запис у журналі з правильним `item_id`; критик знаходить `offscreen` на титрі за краєм; одне коло виправлень прибирає знахідку.
- [ ] **Step 6: Commit** `"Wire frame-critic into graphics, zoom, caption and PiP skills and QC"`.

### Task 6: `memory.py diff` — знімки і події

**Files:**
- Create: `skills/edit-memory/scripts/memory.py`
- Modify: `skills/resolve-core/reference.md` (розділ «Handoff snapshot»), `README.md`, `.github/workflows/release.yml`

**Interfaces:**
- Consumes: формат timeline dump; журнал `placed` (Task 1) для `owner`/`kind`.
- Produces:
  - Знімок = dump (уже з `item_id`, Task 2) + `timeline_id` + в кожному елементі `props` (`ZoomX, ZoomY, Pan, Tilt, Opacity, AudioVolume`), `fades`, `fusion` (`{"text", "center", "size"}` або `null`). Код — у `reference.md`, «Handoff snapshot», як розширення dump.
  - `changed(old: dict, new: dict) -> bool`.
  - `diff(old: dict, new: dict, ledger: dict) -> list[dict]` — події `{"type", "owner", "kind", "item_id", "track", "tc", "frame", "value"}`; `type` ∈ `moved, retimed, deleted, added_by_user, text_changed, property_changed, volume_changed, track_changed, cut_changed`.
  - `ripple_shift(old: dict, new: dict) -> list[tuple[int, int]]` — кумулятивний зсув як відсортовані пари `(frame_in_old, shift)` за змінами тривалості на `A-roll`/`Screen`.
  - CLI: `memory.py changed <old> <new>` (exit 1 = змінився); `memory.py diff <old> <new> [--ledger L] --out events.json`; `memory.py selftest`.

Зіставлення: спершу `item_id`; решта — медіа за (роль доріжки, `clip_id`, перетин `[source_start, source_end]`), Fusion за (доріжка, `fusion.text`, найближчий `start` після `ripple_shift`). Подія `moved`, лише якщо `|new.start - (old.start + shift(old.start))| > 1`. Маркери з `customData`, що починається з `claude:`, ігноруються.

- [ ] **Step 1: Тести:**
  - вирізано 48 кадрів з першого A-roll кліпу, усі три титри після нього зсунуті на −48 → подій `moved` немає, є одна `cut_changed`.
  - те саме + один титр додатково зсунутий на +24 → рівно одна `moved` з `value` 24 (Review Focus 3).
  - титр без `item_id` у новому знімку (дубльований таймлайн), той самий текст → зіставлено, подій немає.
  - старий знімок без поля `item_id` (зроблений до Task 2) → зіставлення за вмістом, без винятку.
  - текст змінено → `text_changed`; `ZoomX` 1.6 → 1.3 → `property_changed`; елемент зник → `deleted`; новий елемент без запису в журналі → `added_by_user`.
  - доданий Cream-маркер `claude:critic:offscreen` → `changed` false.
- [ ] **Step 2:** selftest → падає.
- [ ] **Step 3: Реалізувати** `changed`, `ripple_shift`, `diff`, CLI; розділ «Handoff snapshot» у `reference.md`.
- [ ] **Step 4:** selftest → `memory selftest ok`; README і `release.yml`.
- [ ] **Step 5: Commit** `"edit-memory: snapshots and diff with ripple compensation"`.

### Task 7: `memory.py` — журнал подій, правила, команди

**Files:**
- Modify: `skills/edit-memory/scripts/memory.py`

**Interfaces:**
- Consumes: `diff` (Task 6).
- Produces:
  - `log_events(events_path: str, events: list, project: str, timeline: str, date: str) -> int` — дописує рядки JSONL, повертає кількість.
  - `lessons(events_path: str, rules: dict) -> list[dict]` — кандидати `{"group": [owner, kind, type], "count", "share", "median", "direction", "events": [ids], "conflicts_with": rule_id|None}`; лише групи з ≥ 2 неспожитими подіями в один бік; разові — з `"one_off": true`.
  - `approve(memory_path, events_path, candidate, text, param=None) -> dict` (правило формату спеку §6.5, події позначено `rule_id`); `reject(events_path, event_ids)`; `forget(memory_path, rule_id)`; `rules(memory_path, skill=None, fmt=None) -> list`; `confirm(memory_path, rule_id)`.
  - CLI: `memory.py log`, `lessons`, `approve`, `reject`, `forget`, `rules --skill S --format F`, `show`; файли пам'яті з `--memory PATH` (за замовчуванням `edit-memory.json` і `edit-memory-events.jsonl` у теці `--memory`).

- [ ] **Step 1: Тести:**
  - немає файлів → `rules` повертає `[]`, `lessons` → `[]` (Review Focus 4).
  - один `retimed +26` для `lower-third` з порівняння 1 і один `+24` з порівняння 2 → один кандидат, `count == 2`, `median == 25`.
  - `+24` і `−20` → кандидата немає (різний напрямок), обидві разові.
  - `approve` → правило з `confirmed == 1`; ті самі події більше не дають кандидата; `reject` позначає події.
  - кандидат проти правила з протилежним напрямком тієї ж групи → `conflicts_with` = id правила.
  - `rules(skill="fusion-motion-graphics", fmt="shorts")` не повертає правило з `format: youtube`; `forget` прибирає правило.
- [ ] **Step 2:** selftest → падає на нових асертах.
- [ ] **Step 3: Реалізувати.**
- [ ] **Step 4:** selftest → `memory selftest ok`.
- [ ] **Step 5: Commit** `"edit-memory: event log, lessons and approved rules"`.

### Task 8: Скіл `edit-memory` і правила в `resolve-core`

**Files:**
- Create: `skills/edit-memory/SKILL.md`, `skills/edit-memory/evals/lower-third-hold/…` (за зразком Task 4), `docs/skills/edit-memory.md`
- Modify: `.claude-plugin/plugin.json` (`userConfig.edit_memory_file`: `type: string`, title «Edit memory file», default `""`), `docs/settings.md`, `skills/resolve-core/SKILL.md` (нові пункти: знімок як останній крок кожного запису Claude; `memory.py changed` + `diff` + `log` на старті; читання `rules` перед планом), п'ять SKILL.md власників (Task 5) + `text-based-cut`, `split-edits`, `sound-design`, `edit-episode` (знімок на зупинці, `learn` при відновленні), `frame-critic` (знімок після кожного кола; числові правила через `--rules`), `README.md`

**Interfaces:**
- Consumes: `memory.py` (Tasks 6–7), `placed` (Task 1).
- Produces: команди скіла `learn | show | forget <id>`; `memory.py rules` як спільний вхід для власників, критика (`hold_extra_s`, `max_scale`) і судді.

- [ ] **Step 1: Eval** `lower-third-hold`: два знімки двох епізодів, у кожному лоуер-терди подовжені на ~1 с, плюс одна разова зміна зуму. Грейдери: пропонує одне правило з доказами з обох епізодів; разова правка не відмічена; нічого не записує без затвердження; не трактує зсув після вирізу як правку.
- [ ] **Step 2: Написати** SKILL.md (англ.), пункти в `resolve-core`, налаштування.
- [ ] **Step 3:** `claude plugin validate .`; eval (спитати користувача про платний запуск).
- [ ] **Step 4: Жива перевірка** (спек §10): на `claude-probe-critic` записати `GetUniqueId()` титру, попросити користувача зробити трим і blade у UI та перезапустити Resolve, перечитати ID. Результат записати в спек §2 і в `resolve-core/reference.md`.
- [ ] **Step 5:** README Skills, `docs/skills/edit-memory.md`.
- [ ] **Step 6: Commit** `"Add edit-memory skill and shared memory rules"`.

### Task 9: `judge.py` — метрики, вердикт, сліпий вибір

**Files:**
- Create: `skills/edit-judge/scripts/judge.py`
- Modify: `README.md`, `.github/workflows/release.yml`

**Interfaces:**
- Consumes: timeline dump, `words-<timeline>.json` (`timeline_map.py words`), `critic-<timeline>.json`, `qc-<timeline>.json`, `placed` (Task 1).
- Produces:
  - `metrics(dump, words, ledger, fmt, pause_ms) -> dict`: `hook_words` (текст у вікні 30 с / 3 с), `pauses` (`[[from, to]]` > `pause_ms`), `static` (відрізки без межі елемента на A-roll/Screen/B-roll, без зуму й титру, довші за 20 с / 4 с), `graphics_per_min`, `per_kind` (`{kind: count}` за журналом; візуальну однаковість дає знахідка критика `inconsistent`, суддя її лише читає), `tail_s` (останнє слово → кінець таймлайну).
  - `verdict(scores: dict, critic: dict, qc: dict) -> dict` — `{"verdict": "SHIP"|"REWORK", "must_fix": [...]}`; `SHIP` лише якщо всі оцінки > 2 і немає відкритих `error` у критика й QC.
  - `blind(candidates: list, seed: int) -> tuple[list, dict]` — перейменовані на `A, B, …` і таблиця відповідностей.
  - `rank(results: list[dict], labels: list[str]) -> dict` — `results` = `[{"pair": [x, y], "order": "xy"|"yx", "winner": x|y}]`; суперечливі пари = нічия; `{"ranking": [...], "tie": bool}`.
  - CLI: `judge.py metrics …`, `verdict …`, `blind <candidates.json> --out blind.json --key key.json`, `rank <results.json> --key key.json`, `selftest`.

- [ ] **Step 1: Тести:** 25-секундний відрізок без змін на `youtube` → у `static`; 3-секундний на `shorts` → ні, 5-секундний → так; оцінка 2 за «Темп» → `REWORK`; усі 4, але відкритий `error` критика → `REWORK`; усі 4, без помилок → `SHIP`; `blind` з однаковим `seed` детермінований і не містить оригінальних `id`; пара з різними переможцями в прямому і зворотному порядку → нічия; один кандидат → `ranking == ["A"]` без порівнянь; два кандидати з нічиєю → `tie: true` (Review Focus 5).
- [ ] **Step 2:** selftest → падає.
- [ ] **Step 3: Реалізувати.**
- [ ] **Step 4:** selftest → `judge selftest ok`; README і `release.yml`.
- [ ] **Step 5: Commit** `"edit-judge: metrics, verdict and blind ranking"`.

### Task 10: Скіл `edit-judge` і його агент

**Files:**
- Create: `skills/edit-judge/SKILL.md`, `skills/edit-judge/reference.md` (рубрика: опис рівнів 1–5 для шести критеріїв), `agents/edit-judge.md`, `skills/edit-judge/evals/static-stretch/…`, `docs/skills/edit-judge.md`
- Modify: `scripts/build_cowork.py` (копіювати `agents/`, переписувати там префікс інструментів), `README.md`

**Interfaces:**
- Consumes: `judge.py` (Task 9), `memory.py rules` (Task 7).
- Produces: `<work>/judge-<timeline>.json` і `.md`; режими `gate [timeline] [youtube|shorts]` і `pick <candidates.json>`.

- [ ] **Step 1: Перевірка агента плагіна** (спек §5.1): `agents/edit-judge.md` з `tools:` лише `mcp__DaVinci_Resolve__get_image, mcp__DaVinci_Resolve__get_thumbnails, Read, Bash`, скіл з `context: fork` і `agent: edit-judge`; запуск на `claude-probe-critic`: агент бачить кадр через `get_image` і **не** має `run_script`/`Edit`. Не працює → `agent: general-purpose`, hook `guard.py`, без обіцянки «фізично не може»; записати результат у спек.
- [ ] **Step 2: Eval** `static-stretch`: dump + words з 40-секундним статичним відрізком і хуком без обіцянки; грейдери: `REWORK` з таймкодом відрізка; кожна оцінка має доказ-таймкод; нічого не змінює в проєкті; суддя не бачить розмови (лише підготовлені файли).
- [ ] **Step 3: Написати** SKILL.md (англ.: ізоляція, вхідні файли, «зробити таймлайн поточним» — обов'язок того, хто викликає, режими, Never зі спеку §5.4), рубрику, агента; `build_cowork.py`.
- [ ] **Step 4:** `python3 scripts/build_cowork.py` → архів містить `agents/edit-judge.md` з переписаним префіксом; `claude plugin validate .`; eval (спитати про платний запуск).
- [ ] **Step 5:** README Skills, `docs/skills/edit-judge.md`.
- [ ] **Step 6: Commit** `"Add edit-judge skill and isolated judge agent"`.

### Task 11: Підключення судді й документація

**Files:**
- Modify: `skills/shorts-cutdown/SKILL.md` (ранжування моментів через `pick` перед показом), `skills/thumbnail-frames/SKILL.md` (`pick` поверх `scores.json`), `skills/edit-episode/SKILL.md` (`gate` після QC; при `REWORK` — питання «виправляти чи віддавати»; `description` — три нові скіли в стадії D), `.claude-plugin/plugin.json` (`description`), `docs/davinci-plugin-skills.md` (список і порядок `edit-episode`)

**Interfaces:**
- Consumes: `edit-judge` (Task 10), `frame-critic` (Task 4), `edit-memory` (Task 8).

- [ ] **Step 1:** Правки трьох SKILL.md; `candidates-<kind>.json` формату спеку §5.3 пишуть `shorts-cutdown` і `thumbnail-frames`.
- [ ] **Step 2:** `plugin.json` `description`, `docs/davinci-plugin-skills.md` (українською).
- [ ] **Step 3:** Усі selftest зі списку README «Development» → ok; `claude plugin validate .` → ok; `python3 scripts/build_cowork.py` → архів зібрано.
- [ ] **Step 4: Commit** `"Wire edit-judge into Shorts, thumbnails and edit-episode"`.
