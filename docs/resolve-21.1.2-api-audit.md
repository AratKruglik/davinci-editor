# Аудит DaVinci Resolve MCP і scripting API 21.1.2

Статус: дослідження, скіли ще не змінено. Дата: 2026-10-31.
Перевірено на: DaVinci Resolve Studio 21.1.2.10 (macOS), сервер `DaVinci_Resolve` (`ResolveMCP` з бандла Resolve), stub `DaVinciResolveScript.pyi` (152 KiB, 3525 рядків), README API (оновлено 31 Aug 2026), changelog API на диску `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/CHANGELOG.md` (оновлено 22 Oct 2026).
Пов'язані документи: `skills/resolve-core/SKILL.md`, `skills/resolve-core/reference.md`.

Мета: зібрати все, що вміє MCP Resolve, звірити з тим, що вважають наші скіли, і скласти план покращень. Кожне твердження нижче має позначку: **вживу** (виклик виконано на 21.1.2, результат перечитано) або **stub** (є в API, не перевірено).

Чому скіли відстали: `reference.md` звіряли з 21.1.1, а `CHANGELOG.md` фіксує, що в **21.1.2** додано ефекти (`GetEffectsList`, `AddEffect`, `Effect`), тріми й позиції (`Set*Offset`, `SetPosition`, `MoveItems`), `DeleteGaps`, `RippleDeleteSilence`, `AnalyzeAudioLevels`, `SetTranscription`, `ExportFrame`, `SetNodeLabel`/`SetNodeColor`, extended-модель транскрипції, а також Photo Album API. 21.1.1 зробив неблокуючими `TranscribeAudio`, `AnalyzeForSlate`, `CreateSubtitlesFromAudio`, `DetectSceneCuts`, `SmartReframe` і `RenderWithQuickExport`. 21.1 додав keyboard presets, multicam, clone tool, `ValidateDCTL`, fades і speed.

Покриття: основний stub і README пройдено повністю, а `fusion_api.pyi` (69 типів) і `ui_api.pyi` (23 типи) — лише на рівні outline. `DCTLReadme.txt` не відкривався.

## 1. Інструменти MCP-сервера (14)

| Інструмент | Що робить | Нюанси |
|---|---|---|
| `get_resolve_status` | чи запущено Resolve, версія | |
| `launch_resolve` | запускає Resolve і чекає до 60 с | може відкрити останній проєкт, тому лише після «так» користувача |
| `get_whats_new(since)` | changelog застосунку після версії або дати | **закінчується на 21.0.4**. Для змін API 21.1–21.1.2 читати `Developer/Scripting/CHANGELOG.md` на диску |
| `get_scripting_api(api, types, outline, as_file)` | `.pyi` stubs: `DaVinciResolveScript.pyi`, `fusion_api.pyi`, `ui_api.pyi` | `outline` дає дешевий список типів, `types=[…]` дає лише потрібні класи, а `as_file` пише stub у файл і не витрачає контекст (найкраще для grep) |
| `search_scripting_api(pattern, api)` | regex по іменах і описах | перший крок перед будь-яким «API цього не вміє» |
| `get_scripting_docs(document, section, as_file)` | `README.md` (36 KiB), `DCTLReadme.txt` (40 KiB) | `section="TOC"` дає зміст |
| `run_script(script, timeout)` | sandbox Python 3.14; `resolve` і `project` уже є | без `os`/файлів/мережі; timeout 10 с за замовчуванням, максимум 60 с; повертати `result` |
| `run_script_unsafe` | те саме, але з доступом до ФС, мережі й процесів | лише коли сам Python мусить читати чи писати файли |
| `list_luts` / `list_dctls` | рекурсивний список у `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT` | |
| `generate_lut(path, size, transform)` | `.cube` з Python-функції `(r,g,b)→(r,g,b)` | пише лише в `LUT/MCP` |
| `update_dctl(path, content)` | пише `.dctl`, **попередньо компілюючи** | помилки компіляції приходять до запису |
| `delete_lut` / `delete_dctl` | видаляють з `LUT/MCP` | лише за явним проханням |

Що важливо для `run_script`, **вживу**:

- **Resolve-методи, які самі пишуть файли, працюють і з sandbox `run_script`.** Наприклад, `Timeline.ExportFrame(..., {"outputType": "file"})` пише JPG, а Python цей файл не відкриває. `run_script_unsafe` потрібен, лише коли файл читає чи пише сам Python.
- `time.sleep` усередині скрипта працює. Довгі задачі (транскрипцію) можна опитувати в межах 60 с одного виклику.

**Подвійна реєстрація.** На машині є два MCP-сервери Resolve:

- `DaVinci Resolve` — з `~/.claude.json`, бінарник `ResolveMCP` у бандлі Resolve;
- `DaVinci Resolve Studio` — Desktop-розширення `local.mcpb.blackmagic-design.davinci-resolve` з `display_name` «DaVinci Resolve Studio», Node-сервер `server/index.js`.

Розширення показує застарілий опис («21.1.1 not running», stub 118 KiB), хоча віддає той самий stub на 152 KiB. Скіли використовують префікс `mcp__DaVinci_Resolve__`, тому розширення можна вимкнути: зникнуть дубльовані інструменти.

## 2. Карта scripting API 21.1.2

| Клас | Методів | Ключове |
|---|---|---|
| `Resolve` | 47 | сторінки, `GetEffectsList`, пресети (layout, render, burn-in, keyboard, user prefs, Fairlight), `ValidateDCTL`/`EncryptDCTL`, `DisableBackgroundTasksForCurrentResolveSession`, keyframe mode |
| `ProjectManager` | 27 | проєкти, папки, БД, cloud, архів і відновлення |
| `Project` | 67 | налаштування, рендер (jobs, Quick Export, фото), color groups, `GenerateSpeech`, статуси AI-задач, `InsertAudioToCurrentTrackAtPlayhead`, `ExportCurrentFrameAsStill` |
| `MediaPool` | 32 | біни, імпорт, timeline з кліпів, multicam, `AutoSyncAudio`, stereo, photo albums, relink |
| `MediaPoolItem` | 48 | metadata, markers, flags, proxy, `TranscribeAudio`/`GetTranscription`/`SetTranscription`, audio classification, IntelliSearch, Slate, `RemoveMotionBlur`, `ExportFrame` |
| `Timeline` | 69 | доріжки, markers, `MoveItems`, `DeleteGaps`, `NormalizeAudioLevel`, `AutoAlignClips`, вставка titles і generators, `CreateSubtitlesFromAudio`, `DetectSceneCuts`, `ExportFrame`, voice isolation на доріжці |
| `TimelineItem` | 104 | properties (transform, crop, composite, audio, dialogue leveler), **тріми** (`SetLeftOffset`/`SetRightOffset`), `SetPosition`, `SetSpeed`, `SetFades`, **ефекти** (`AddEffect`/`GetEffects`/`DeleteEffects`), `AddTransition`, `CopyAttributes`, `RippleDeleteSilence`, `AnalyzeAudioLevels`, Fusion comps, grade versions, takes, Magic Mask, Stabilize, Smart Reframe, multicam SmartSwitch і Flatten, кеш |
| `Effect` | 6 | `GetInfo`, `Get/SetIsEnabled`, `Get/SetIndex`, `GetFusionComp` |
| `Graph` | 14 | `SetLUT`/`GetLUT`, `SetCDL` (через item), `Get/SetNodeLabel`, `Get/SetNodeColor`, `GetToolsInNode`, `SetNodeEnabled`, `ApplyGradeFromDRX`, `ResetAllGrades`, кеш вузла |
| `ColorGroup`, `Gallery`, `GalleryStillAlbum` | 6 / 8 / 6 | pre-clip і post-clip graph, stills, PowerGrade-альбоми |
| `MediaStorage` | 11 | томи, файли, mattes, **Clone Tool з checksum** |
| `Folder` | 14 | транскрипція, класифікація, IntelliSearch, Slate, deblur для всього біна |
| `PhotoAlbum`, `PhotoAlbumItem` | 10 / 43 | нова сторінка Photo: рейтинги, версії, ефекти, експорт |

Плюс `fusion_api.pyi` (69 типів: `Composition` має 102 члени, `Operator`, `Fusion`) і `ui_api.pyi` (23 типи: UIManager для власних вікон у Workspace → Scripts).

## 3. Перевірено вживу на 21.1.2

Метод: два прогони на тимчасовому timeline `claude-api-probe` у проєкті `Apple Log Test`. Медіа: WAV 6 с, згенерований скриптом (тон 2 с / тиша 2 с / тон 2 с), still-JPG, генератор `Solid Color`, на другому прогоні ще CDL і титр Text+. Після кожного прогону timeline і бін видалено, проєкт збережено.

| Виклик | Результат | Що це означає для скілів |
|---|---|---|
| `GetEffectsList("video"/"audio"/"photo")` | video: 301 fusion (уся бібліотека MotionVFX) + 94 ofx; audio: 56; photo: 272 fusion + 64 ofx. `id` — це шлях: `Resolve FX/Resolve FX Blur/CineFocus`, `Fusion/Effects/MotionVFX/mHowTo/Camera Movements/mHowTo Zoom`, `Audio FX/Fairlight FX/Reverb` | авторитетний список встановлених ефектів з id |
| `item.AddEffect("ofx", id)` на кліпі з медіа | `CineFocus` і `Glow` додано (це ефекти Edit-сторінки, Inspector → Effects) | твердження «API can't add Resolve FX» неточне |
| `AddEffect` на генераторі | `None` | ефекти лише на кліпах з медіа |
| `Effect.SetIndex(1)`, `SetIsEnabled(False)`, `GetIsEnabled()` | порядок змінився; стан читається | для ефектів є і getter, і setter enabled |
| `Effect.GetFusionComp()` для OFX | `None` | **параметри OFX недоступні** |
| `item.AddEffect("fusion", "…/mHowTo Zoom")` → `GetFusionComp()` → `FindTool("mHowTo_Zoom")` | macro з інпутами `Input3` Movement Target, `Input4` Zoom Scale (0.3 за замовчуванням), `Input5/6` ease in/out; `SetInput("Input4", 1.8)` зберігається | **Fusion-ефекти (MotionVFX) повністю керуються зі скрипта** |
| `item.AddEffect("audio", "Audio FX/Fairlight FX/Reverb")` | додано, видно в `GetEffects("audio")` | параметрів немає |
| `item.DeleteEffects(item.GetEffects(cat))` | OFX і audio прибрано | додані ефекти можна зняти скриптом |
| `SetRightOffset(200)` на аудіо з handle 261 | end 99 → 160, source end 99 → 160 | аргумент означає **залишок handle після точки монтажу**, а не кількість кадрів для обрізання |
| `SetLeftOffset(30)` | start 0 → 30, source start 0 → 30, зліва діра | правка **in place, без ripple** |
| `SetRightOffset` на генераторі | `False` | генератори, титри й comp, які не мають медіа, так не тримуються |
| `A.SetRightOffset(ro − 30, False, False)`, коли B стоїть впритул на тій самій доріжці (обидва аудіо злінковані зі still на V1) | `True`; A подовжилось до 330, **голову B перезаписано** (B 330..600, його handle 60 → 90); відео обох пар не змінилось | L-кат одним викликом: звук A заходить під картинку B. J-кат дзеркально: `B.SetLeftOffset(lo − n, False, False)`. Повернення: обернений виклик |
| `SetRightOffset`/`SetLeftOffset` з `updateLinkedItems=False` на злінкованій парі V+A | змінилось лише аудіо, відео на місці | для split edit саме так |
| `SetRightOffset(20)` з `updateLinkedItems=True` (за замовчуванням) | злінкований still отримав **те саме значення offset 20**, а не той самий зсув: його кінець став 3 384 281 | **ніколи не покладатись на `updateLinkedItems=True`**, коли handles кліпів різні. Передавати `False` і правити кожен кліп окремо |
| `RippleDeleteSilence` при залоченій V1 | аудіо порізано (0..120, 120..240), відео на V1 лишилось 0..300 | lock доріжки **захищає** від ripple |
| `tl.MoveItems([a, b], {"trackIndex": 2, "startFrame": 400}, False)` | обидва шматки перейшли на A2 400..520, 520..640 | групове переміщення зі збереженням взаємного розташування |
| `tl.ExportFrame(10, {"outputType": "file", "filePath": "….tif"})` і `item.ExportFrame` | TIF **16 bit**, 3840×2160, з CDL (offset 0.5/0.25/0 → центр R 128, G 64, B 0); з `maxDimension: 480` значення ті самі | придатно для вимірювань кольору (`chart-match`, `natural-skin-grade`) |
| `project.ExportCurrentFrameAsStill(….tif)` у той самий момент | чорний кадр: playhead стояв на кадрі 360, за межами кліпу | старий шлях залежить від playhead; `ExportFrame` — ні |
| `GetSourceEndFrame` при різній довжині | 99 кадрів (0..99) → 99; після розширення → 160; на повній довжині 360 кадрів → **359** | поведінка кінця біля межі кліпу відрізняється, причину не з'ясовано. Важливо для timeline dump і `timeline_map.py`: перевіряти по `GetDuration()` |
| `AppendToTimeline(startFrame=0, endFrame=99)` (аудіо) | тривалість 99, source 0..99 | `endFrame` **exclusive** на 21.1.2 (калібрування `resolve-core` все одно лишається) |
| `AppendToTimeline` still з `endFrame=120` | 300 кадрів | для stills діапазон ігнорується, береться Standard still duration |
| `Timeline.ExportFrame(120, {"outputType": "file", "filePath": "….jpg", "maxDimension": 640})` у sandbox `run_script` | JPG 640×360, **playhead не зрушив** | кадр без `run_script_unsafe` і без руху playhead |
| `TimelineItem.ExportFrame(10, {"outputType": "encodedString", "maxDimension": 320})` | base64 JPG ≈ 2 KB; на генераторі видає помилку «not a media item» | лише кліпи з медіа |
| `item.SetCDL(offset R +0.3)` на чорному still → `item.ExportFrame` | кадр став темно-червоним | **грейд потрапляє** в `ExportFrame` |
| still з CDL на V1 + титр Text+ на V2 → `tl.ExportFrame(330, …png)` | у PNG видно грейд і текст «CLAUDE PROBE» | `Timeline.ExportFrame` віддає **готовий композит**: усі доріжки, грейд, Fusion-титри |
| `tl.InsertFusionTitleIntoTimeline("Text+")` з playhead на 0, still на V1 0..300 | титр став на **V1** 0..300, still зсунуто на 300..600 | це **insert з ripple** на нижню доріжку, а не накладання зверху. Пояснює, навіщо `fusion-motion-graphics` лочить доріжки |
| `title.SetPosition({"trackIndex": 2, "startFrame": 300})` | титр перейшов на V2 300..600 | `SetPosition` переносить кліп між доріжками |
| `tl.GetNormalizeAudioModes()` | `Sample Peak Program`, `True Peak`, `ITU-R BS.1770-1`, `ITU-R BS.1770-4`, `ATSC A/85`, `EBU R128`, `OP-59`, `TR-B32`, `AGCOM 219/09/CSP`, `Netflix`, **`YouTube`**, `Disney - 2.0`, `Disney - 5.1+`, `TencentVideo` | рядки для `NormalizeAudioLevel` і `AnalyzeAudioLevels` |
| `item.AnalyzeAudioLevels("YouTube")` | `{"TruePeak": -6.0, "Integrated": -7.19}` на синусі −6 dBFS; без рендеру. Усі 12 стандартів дали **ті самі числа** | LUFS і TP **по кліпу**; міксу timeline-а метод не дає. Аргумент `standard` на цьому сигналі нічого не змінив, тому не очікувати різних чисел від різних режимів |
| `item.RippleDeleteSilence({"threshold": -25, "minimumToStrip": 30})` | вирізано рівно source 120..240 (2 с тиші); **ripple пройшов по всіх доріжках**: незлінковані генератор на V1 і still на V2 розрізано й зсунуто | працювати на дублікаті; lock доріжки від цього ripple захищає (перевірено окремою пробою нижче) |
| `clip.SetTranscription({...})` українською | `True`; спікер «Олексій» додався до проєкту; таймінги слів без часу інтерпольовано; сегмент тиші `(...)` створено автоматично | транскрипт можна **виправити і записати назад** |
| `GetTranscription()` після `SetTranscription` | `segment.text` склеює слова **без пробілів** («Привіт,цетест»); нативні слова Resolve йдуть **з пробілом попереду** (`" fe"`) | текст збирати з `words`; у `SetTranscription` передавати слова з пробілом попереду, як у нативних |
| `SetSettings({"transcriptionLanguage": "uk"})` при `transcriptionExtendedLanguageSupport="0"` | `False`, лишилось `auto` | українська є **лише в extended-моделі** |
| `transcriptionExtendedLanguageSupport="1"`, потім `transcriptionLanguage="uk"` | обидва `True`; транскрипт `language: "uk"` | закриває відкрите питання з `reference.md`. Зміна extended скидає мову на `auto`, тому порядок важливий |
| `TranscribeAudio` → `GetTranscribeAudioStatus()` | `Initializing` → `Complete` за кілька секунд на 2 с | опитувати в межах одного виклику з `sleep` або окремими викликами |
| `auto`-мова на 2 с української | визначилась як `es` | для коротких кліпів мову задавати явно |
| `project.GenerateSpeech({"TextInput", "VoiceModel": "Female 1", "Filename"})` | `MediaPoolItem` (≈2 с WAV), Extra встановлено | працює |
| `GenerateSpeech` українською («Це короткий тест голосу.») | розпізнається назад як «Фекаро тіць з колосу» | модель `Female 1` **не вимовляє українську**; інші моделі й `Custom Voice` не перевірено |
| куди пише `GenerateSpeech` | `<project media location>/Audio Files/SpeechGenerator/` | порушує наше правило «не писати в медіапапки»: попереджати користувача |
| новий timeline у цьому проєкті | 60 fps, 3840×2160, `GetStartFrame() == 0` | 86400 не можна вважати сталою, правило `resolve-core` §4 підтверджено |

## 4. Досі неможливо (підтверджено stub 21.1.2)

- Створювати вузли або міняти їхні tools: у `Graph` немає `AddNode`. DRX-шаблон лишається.
- Читати CDL (`GetCDL` немає) і стан enabled вузла: є `SetNodeEnabled`, але немає getter-а. Для `Effect` getter є.
- Параметри OFX- і audio-ефектів: `Effect` не має param API. Виняток — Fusion-ефекти через `GetFusionComp()`.
- Keyframes властивостей кліпу (volume, pan, zoom, OFX). Ключі можна ставити лише всередині Fusion comp.
- Генерувати проксі: є тільки `LinkProxyMedia`/`LinkFullResolutionMedia`/`UnlinkProxyMedia`.
- Тримити генератори, титри й Fusion compositions через `Set*Offset` (повертає `False`, **вживу** перевірено на `Solid Color`).
- Читати результати IntelliSearch: є `AnalyzeForIntellisearch` і `ResetIntellisearchAnalysis`, а пошуку немає.
- Колір заголовка доріжки.

## 5. Є в stub, не перевірено

| Виклик | Навіщо нам |
|---|---|
| `Timeline.MoveItems(items, {"trackIndex", "startFrame"}, moveLinkedItems, subframePrecision)` | переставляти групу кліпів без delete і append (`SetPosition` для одного кліпу перевірено, §3); разом із `Set*Offset` це ripple- і roll-трим |
| `Timeline.DeleteGaps()` | закрити діри після `SetLeftOffset` |
| `TimelineItem.SetSpeed({"Percentage", "PitchCorrection", "RippleTimeline"})` | прискорення нудних місць у записі екрану, freeze frame (`0.0`) |
| `TimelineItem.AddTransition({"type", "category", "position", "alignment", "duration"})` | вже використовує `text-based-cut` для audio cross fade |
| `CopyAttributes(targets, {...retimeEffect, videoPlugins, fusionEffects…})` | перенести ефекти, ретайм чи кроп з одного кліпу на інші |
| `Stabilize()`, `CreateMagicMask("F"/"B"/"BI")`, `RegenerateMagicMask()` | стабілізація handheld B-roll, маска людини |
| `MediaPool.CreateMulticamClip(clips, {...})`, `TimelineItem.PerformMulticamSmartSwitch({...})`, `FlattenMulticam(...)` | автоматичний монтаж 2–3 камер (подкаст, інтерв'ю) |
| `Timeline.CreateSubtitlesFromAudio({"language": resolve.AUTO_CAPTION_UKRAINIAN, "extendedLanguageSupport": True, "charsPerLine", "lineBreak", "gap"})` | у списку `AutoCaptionLanguage` є `AUTO_CAPTION_UKRAINIAN` |
| `Timeline.DetectSceneCuts()` + `GetDetectSceneCutsStatus()` | порізати змонтований файл, отриманий ззовні |
| `MediaPoolItem/Folder.PerformAudioClassification()` | класифікувати бібліотеку SFX і музики (куди пише результат — з'ясувати) |
| `AnalyzeForSlate(resolve.MARKER_*)` | маркери на хлопавках |
| `RemoveMotionBlur({...})` | AI deblur кліпу (рендерить новий файл) |
| `Project.RenderWithQuickExport("YouTube", {"TargetDir", "CustomName", "EnableUpload"})` + `GetRenderWithQuickExportStatus()` | рендер з прямим завантаженням на YouTube |
| `SetRenderSettings({"ExportSubtitle", "SubtitleFormat": "BurnIn"/"EmbeddedCaptions"/"SeparateFile", "UseFullExtents", "AddFrameHandles", "DataBurnIn"})` | субтитри в рендері |
| `Graph.SetNodeLabel(i, label)`, `SetNodeColor(i, color)`, `GetToolsInNode(i)` | підписати вузли шаблону скриптом після підтвердження |
| `MediaStorage.SetCloneToolSettings({"ChecksumType"})` + `StartCloneMedia(src, [dst])` + `GetCloneStatus()` | резервна копія карти з checksum перед імпортом |
| `Resolve.ExportKeyboardPreset` / `ImportKeyboardPreset` / `LoadKeyboardPreset` | автоматизувати скіл `davinci-cyrillic-shortcuts` |
| `TimelineItem.SetFusionOutputCache` / `SetColorOutputCache`, `Graph.SetNodeCacheMode` | кеш для важких MotionVFX-титрів і AI-вузлів |
| `Timeline/TimelineItem.SetOutputBlanking({"Top", "Bottom", "Left", "Right"})` | letterbox без кропу |
| `Project.InsertAudioToCurrentTrackAtPlayhead(path, offsetSamples, durSamples)` | SFX у точку з точністю до семплу |
| `MediaPool.ExportMetadata(csv, clips)` | метадані кліпів у CSV для QC |

## 6. Рекомендації по скілах

Пріоритет 1 — перевірено вживу, великий виграш:

| Скіл | Зараз | Пропозиція |
|---|---|---|
| `resolve-core` / `reference.md` | «there is no API to trim an item»; відкрите питання про код української | додати перевірені рядки з §3: семантику `Set*Offset`, `ExportFrame`, `AddEffect`/`Effect`, `AnalyzeAudioLevels`, `RippleDeleteSilence`, `SetTranscription`, extended → `uk`, `GenerateSpeech`. Прибрати «can't trim», лишивши «generators can't be trimmed» |
| `split-edits` | §76 «API cannot trim an item's edge»; Mode 2 робить unlink, delete і повторний append аудіо (guard prompt) | J/L — це roll-трим лише аудіо: `A.SetRightOffset(ro + n, updateLinkedItems=False)` і `B.SetLeftOffset(lo - n, updateLinkedItems=False)` без видалення. **Перевірити** розширення в бік сусіда на тій самій доріжці і `updateLinkedItems=False` на злінкованій парі |
| `motionvfx-catalog` | §48 «Effects can't be attached to a clip through the API» | `item.AddEffect("fusion", id)` + `Effect.GetFusionComp()` + `SetInput` на інпутах macro. `id` брати з `resolve.GetEffectsList("video")` і звіряти з каталогом |
| `tutorial-zooms` | власний Fusion-зум або transform | варіант на MotionVFX `mHowTo Zoom` / `mKBHD Zoom`: додати ефект, задати `Zoom Scale` і `Movement Target` (центр області з кадру) |
| `audio-effects` | «no setters for EQ, effects»; backup timeline, бо «no API call can remove» | `AddEffect("audio", "Audio FX/Fairlight FX/Reverb" / "Fairlight EQ" / "De-Esser")` вмикає ефект, а `DeleteEffects` робить це оборотним. Параметри — вручну або `CopyAttributes` з еталонного кліпу. Таблицю «by script / by hand» оновити |
| `depth-background-blur` | §26 «The API can't add Resolve FX» | уточнити: OFX `CineFocus`/`Depth Map` додаються як ефект Edit-сторінки, вмикаються, вимикаються, переставляються і видаляються; параметри й keyframes — лише вручну. Шлях через Color-вузли лишається основним |
| `uk-transcribe` | код мови визначається на ходу | налаштування: `transcriptionExtendedLanguageSupport="1"`, потім `transcriptionLanguage="uk"`, перечитати; без extended-моделі зупинитись і сказати, що треба Extras. Після ручної правки транскрипту (імена, терміни) записати його назад через `SetTranscription` зі словами з пробілом попереду |
| `thumbnail-frames`, `pre-delivery-qc`, `tutorial-zooms`, `fusion-motion-graphics` | playhead → `ExportCurrentFrameAsStill` через `run_script_unsafe` | `tl.ExportFrame(offset, {"outputType": "file", "filePath", "maxDimension"})` з sandbox `run_script`, без руху playhead. Перевірено, що в кадр потрапляють грейд, усі доріжки і Fusion-титри (§3). `maxDimension` 1280 для прев'ю. Для Cowork mapping шляхів лишається |
| `audio-finish`, `pre-delivery-qc` | loudness лише через mixdown-рендер | швидкий крок: `AnalyzeAudioLevels("YouTube")` по кліпах Voice і Music. Фінальна перевірка міксу лишається рендером: метод працює по кліпу |
| `text-based-cut` | тишу ріже власний аналіз транскрипту | опційний швидкий прохід `RippleDeleteSilence` лише на дублікаті: ripple іде по всіх доріжках, а захист lock-ом не перевірено. `preHead`/`postTail` у кадрах, щоб не різати подих. Потрібен фікс guard (§7) |
| `davinci-cyrillic-shortcuts` (особистий скіл, не в репо) | просить експортувати вручну; шлях `/Users/foten/.gemini/...` неправильний | `resolve.ExportKeyboardPreset(current, txt)` → `convert.py` → `ImportKeyboardPreset(out, "!Custom_Shortcuts_UKR")` → `LoadKeyboardPreset`. Формат експорту **перевірити** |

Пріоритет 2 — потрібна перевірка вживу:

| Скіл | Пропозиція |
|---|---|
| `chart-match`, `natural-skin-grade`, `log-to-rec709` | **перевірено пізніше (§3)**: `ExportFrame` у `.tif` дає 16 bit, повну роздільність і точні значення з грейдом, тож ці скіли переходять на нього. Не перевірено лише `item.ExportFrame` на тимчасовій local-версії з вимкненими вузлами |
| `log-to-rec709` | відсутній label → показати `GetToolsInNode(i)` кожного вузла, запропонувати мапу і після «так» підписати через `SetNodeLabel` |
| `subtitles-uk` | `CreateSubtitlesFromAudio` з `AUTO_CAPTION_UKRAINIAN` + `extendedLanguageSupport: True` після виправлення транскрипту через `SetTranscription`; у рендері `ExportSubtitle` + `SubtitleFormat` |
| `deliver` | `RenderWithQuickExport("YouTube", {"EnableUpload": True})`: лише після явного «так», бо це публікація. Субтитри через `SetRenderSettings`. Статуси background render |
| `dual-video-sync-pip` | OFX `Picture In Picture` (новий у 21) як ефект; `CreateMulticamClip` + `PerformMulticamSmartSwitch` для 2 камер |
| `project-bootstrap` | `StartCloneMedia` з MD5 перед імпортом з карти |
| `shorts-cutdown` | `SetSpeed` / `SetLeftOffset` для підрізання хвостів без перезбирання |

Нові скіли-кандидати: `multicam-smartswitch` (подкасти, інтерв'ю), `speed-ramp` (прискорення нудних частин запису екрану через `SetSpeed`), `scene-detect` (`DetectSceneCuts` для чужих мастерів).

## 7. Як впроваджувати

- Плагін декларує 21.0+ (`resolve-core` §1), а більшість цих викликів з'явилась лише в 21.1.2 (`CHANGELOG.md`). Кожен новий виклик огорнути перевіркою: `resolve.GetVersion() >= [21, 1, 2]` або `hasattr(item, "SetRightOffset")`. За відсутності методу лишати поточний ручний шлях.
- `guard.py`: `DeleteEffects` і `DeleteGaps` давали prompt і раніше. `RippleDeleteSilence` проходив без нього, бо шаблон `\b(Delete\w*|…)` не бачить `Delete` всередині ідентифікатора. **Виправлено**: метод додано в `DESTRUCTIVE`, усі три виклики — в selftest. Інших методів API з `Delete`/`Clear`/`Reset` всередині назви немає (перевірено по stub).
- У `reference.md` додавати лише рядки з позначкою **вживу**. Решту лишити в «Settings that need runtime discovery».

## 8. Побічні ефекти цієї перевірки

- Проєкт `Apple Log Test`: після обох прогонів тимчасові timeline і бін видалено, мовні налаштування транскрипції повернуто (`0` / `auto`), проєкт збережено. Стан той самий, що до перевірки: 0 timeline-ів, 6 бінів. Спікер «Олексій» лишився в списку спікерів проєкту: API для видалення немає.
- На диску лишились два WAV від `GenerateSpeech`: `/Volumes/AratData/Projects/Youtube/KRUHLYK/2026/Test intro/Apple Log Test/Audio Files/SpeechGenerator/claude-probe-speech-{en,uk}-Female 1-G1-001.wav`.
