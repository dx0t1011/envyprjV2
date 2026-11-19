# envyprjV2

Личный инструмент для загрузки видео на собственный канал YouTube через официальный
**YouTube Data API v3**. Запускается локально, работает под одним аккаунтом Google,
не является публичным сервисом.

- Репозиторий: <https://github.com/dx0t1011/envyprjV2>
- Сайт: <https://dx0t1011.github.io/envyprjV2/>
- Политика конфиденциальности: <https://dx0t1011.github.io/envyprjV2/privacy.html>
- Условия использования: <https://dx0t1011.github.io/envyprjV2/terms.html>

Здесь же лежит сайт проекта — он нужен как публичные ссылки (home page / privacy policy /
terms) для настройки OAuth-приложения в Google Cloud.

| Страница | Файл |
| --- | --- |
| Главная | `index.html` |
| Политика конфиденциальности | `privacy.html` |
| Условия использования | `terms.html` |

---

## 1. Настройка Google Cloud (один раз)

Полный чек-лист с точными полями. Проект: **envyprjV2**, аккаунт: **envyproject@gmail.com**.

### 1.1 Включить API

[console.cloud.google.com](https://console.cloud.google.com) → сверху выбрать проект `envyprjV2` →
`APIs & Services` → `Library` → найти **YouTube Data API v3** → **Enable**.

### 1.2 Branding

[console.cloud.google.com/auth/branding](https://console.cloud.google.com/auth/branding)

| Поле | Значение |
| --- | --- |
| App name | `envyprjV2` |
| User support email | `envyproject@gmail.com` |
| App logo | **не загружать** (включает отдельную проверку бренда) |
| Application home page | ссылка на этот репозиторий или на GitHub Pages |
| Application privacy policy link | `<Pages URL>/privacy.html` |
| Application terms of service link | `<Pages URL>/terms.html` |
| Authorized domains | `github.io` (или `github.com`, если ссылки на репозиторий) |
| Developer contact email | `envyproject@gmail.com` |

→ **Save**.

### 1.3 Data access

[console.cloud.google.com/auth/scopes](https://console.cloud.google.com/auth/scopes) →
**Add or remove scopes** → в фильтр вставить по одному и отметить галочкой:

```
https://www.googleapis.com/auth/youtube.upload
https://www.googleapis.com/auth/youtube.readonly
https://www.googleapis.com/auth/youtube.force-ssl
```

→ **Update** → **Save**. Лишние scopes удалить: всё, что не нужно, только усложняет проверку.

Зачем третий. `youtube.upload` позволяет только **создать** видео и поставить обложку
(`videos.insert`, `thumbnails.set`). Сменить приватность (`videos.update`), удалить видео
(`videos.delete`) или править плейлисты им нельзя — нужен `youtube.force-ssl`. Без него команда
`upload.py publish` падает с `403 Request had insufficient authentication scopes`, хотя `upload.py upload`
при этом работает. `youtube.force-ssl` — тоже **sensitive**, не restricted: проверка приложения
по-прежнему не требуется.

Важно: набор scopes в коде (`upload.py`, константа `SCOPES`) и в консоли должен совпадать.
Если добавить scope в код, но не в консоль, авторизация упадёт с `invalid_scope`.

### 1.4 OAuth-клиент

[console.cloud.google.com/auth/clients](https://console.cloud.google.com/auth/clients) →
**Create client** → Application type: **Desktop app** → имя `envyprjV2-desktop` → **Create** →
**Download JSON** → положить файл рядом с `upload.py` **как `client_secret.json`**.

### 1.5 Audience и публикация

[console.cloud.google.com/auth/audience](https://console.cloud.google.com/auth/audience)

1. **Test users** → **+ Add users** → `envyproject@gmail.com` → Save.
2. **Publish app** → подтвердить. Статус станет **In production**, статус проверки —
   «Needs verification»; для личного использования это нормально и игнорируется.

После смены статуса **обязательно** переавторизоваться, иначе останется 7-дневный токен:
[myaccount.google.com/permissions](https://myaccount.google.com/permissions) → удалить доступ
`envyprjV2` → запустить `upload.py channel` заново.

---

## 2. Установка

```bash
cd envyprjV2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Положить `client_secret.json` в корень проекта (он в `.gitignore`, в репозиторий не попадёт).

## 3. Использование

```bash
# какой канал авторизован
python upload.py channel

# загрузить (по умолчанию — private, безопасный дефолт)
python upload.py upload video.mp4 \
  --title "Название" \
  --description "Описание" \
  --tags тег1 тег2 \
  --category 27 \
  --thumbnail cover.jpg

# опубликовать позже
python upload.py publish VIDEO_ID --privacy public

# последние видео
python upload.py list --limit 10
```

Первый запуск откроет браузер: войти под `envyproject@gmail.com`, **выбрать нужный канал**,
нажать «Разрешить», пройти экран «Google не проверил приложение» → *Дополнительно* →
*Перейти в envyprjV2 (небезопасно)*.

Токен хранится в `~/.config/envyprjV2/token.json` с правами `600`.

## 4. Что важно знать

- **Приватность.** С 2 ноября 2026 дефолт YouTube API — `public`, если `privacyStatus`
  не передан. Скрипт всегда передаёт явно и по умолчанию ставит `private`.
- **Обложка.** `thumbnails.set` работает только на подтверждённом канале (нужен телефон
  и отсутствие страйков), картинка 1280×720, до 2 MB.
- **Бренд-аккаунт.** Если на аккаунте несколько каналов, видео уйдёт в тот, что выбран на
  экране согласия Google. Проверка: `python upload.py channel` печатает название и ID.
- **Квота.** 10 000 юнитов в сутки на проект. `videos.insert` стоит 1600 юнитов, то есть
  **6 загрузок в день** (а не 100 — ранняя версия этой строки врала). `videos.delete` — 50,
  `videos.list` / `channels.list` — по 1, `videos.update` — 50. Для ручной/ежедневной публикации
  запаса хватает, но пакетная заливка десяти роликов за один день упрётся в лимит.
- **Проверка Google** нужна только если пользователей станет больше 100 или понадобится
  убрать жёлтый экран предупреждения.

## 5. Лицензия

Код — для личного использования. Приложение использует YouTube API Services и подчиняется
[Условиям использования YouTube API Services](https://developers.google.com/youtube/terms/api-services-terms-of-service).
