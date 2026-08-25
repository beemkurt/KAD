# KAD — Changelog

Здесь фиксируются значимые изменения проекта и его документации. Документ следует принципам [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), но версии пока привязаны к завершённым этапам, а не к релизам приложения.

## [Unreleased]

### Planned

- Read-only аудит живой инфраструктуры.
- Уточнение inventory по результатам аудита.
- Формирование Stabilization Sprint.

## [Project Management Setup] — 2026-08-25

### Added

- Один публичный GitHub Project [`KAD`](https://github.com/users/beemkurt/projects/1) со статусами `Backlog`, `Planned`, `In Progress`, `Review` и `Done`.
- Минимальный набор из семи labels для типа, приоритета и блокировки задач.
- Стартовый backlog из шести Issues с scope, критериями готовности и labels; [`Read-only audit VPS`](https://github.com/beemkurt/KAD/issues/1) назначен следующим практическим шагом.

### Changed

- Включён и проверен auto-add открытых Issues репозитория в Project.
- В `CURRENT.md` и roadmap зафиксирован завершённый промежуточный этап Project Management Setup перед read-only аудитом инфраструктуры.

## [Project Foundation] — 2026-08-25

### Added

- Содержательный корневой README с состоянием, границами репозитория и навигацией.
- Каноническая страница текущего состояния и следующего шага.
- Документы архитектуры, решений, roadmap, inventory и glossary.
- Индекс runbooks, правила безопасного выполнения и чек-лист read-only аудита VPS.
- Этот changelog.

### Changed

- Согласованы статусы `VERIFIED`, `KNOWN`, `NEEDS VERIFICATION`, `PLANNED` и `DECIDED`.
- Project Foundation отмечен завершённым; дальнейшая последовательность этапов зафиксирована в roadmap.
- Живая система явно отделена от содержимого GitHub: репозиторий пока хранит документацию, а не production-копию или исходники приложений.
- Уточнено последнее известное состояние: backend и бот ранее работали, VPN требует проверки и диагностики.
- Добавлена сквозная навигация между основными документами.
- `.gitignore` дополнен типичными временными файлами редакторов.

### Security

- Подтверждено отсутствие очевидных секретов, баз данных, архивов, логов и редакторских артефактов в отслеживаемом дереве на момент завершения этапа.
- Зафиксирован запрет на хранение production-секретов и пользовательских данных в публичном репозитории.

## [Initial documentation] — 2026-08-13

### Added

- Публичный GitHub-репозиторий KAD.
- Базовый `.gitignore` с исключениями для секретов, баз, архивов и сборочных артефактов.
- Первые версии `CURRENT.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `INVENTORY.md` и `GLOSSARY.md`.

## Навигация

[README](../README.md) · [Текущее состояние](CURRENT.md) · [Roadmap](ROADMAP.md) · [Runbooks](runbooks/README.md)
