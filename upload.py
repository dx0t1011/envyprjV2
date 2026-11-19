#!/usr/bin/env python3
"""envyprjV2 — загрузка видео на собственный канал YouTube через Data API v3.

Команды:
    python upload.py channel              # какой канал авторизован (id + название)
    python upload.py upload FILE ...      # загрузить видео
    python upload.py publish VIDEO_ID     # перевести видео в public
    python upload.py list                 # последние видео канала

Первый запуск открывает браузер: войди под envyproject@gmail.com, выбери нужный
канал и нажми «Разрешить». Токен сохранится в ~/.config/envyprjV2/token.json
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    # нужен для videos.update (publish) и videos.delete: youtube.upload их не покрывает.
    # Тот же набор должен быть включён в консоли (Data access), иначе будет invalid_scope.
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

HERE = Path(__file__).resolve().parent
CLIENT_SECRET = Path(os.environ.get("ENVY_CLIENT_SECRET", HERE / "client_secret.json"))
TOKEN_PATH = Path(
    os.environ.get("ENVY_TOKEN", Path.home() / ".config" / "envyprjV2" / "token.json")
)


def die(msg: str) -> None:
    print(f"Ошибка: {msg}", file=sys.stderr)
    raise SystemExit(1)


def get_service():
    """OAuth-авторизация с кэшем токена и без аргумента cache_discovery (его убрали)."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        die(
            "нет зависимостей. Выполни:\n"
            "  python3 -m venv .venv && source .venv/bin/activate\n"
            "  pip install -r requirements.txt"
        )

    creds = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except ValueError:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:  # noqa: BLE001
                print(f"Не удалось обновить токен ({exc}), прохожу авторизацию заново.")
                creds = None
        if not creds:
            if not CLIENT_SECRET.exists():
                die(
                    f"не найден {CLIENT_SECRET}\n"
                    "Скачай JSON OAuth-клиента (тип Desktop app) в Google Cloud Console →\n"
                    "Google Auth Platform → Clients → твой клиент → Download JSON,\n"
                    "и положи его рядом с этим скриптом под именем client_secret.json"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            # access_type=offline + prompt=consent гарантируют refresh_token
            creds = flow.run_local_server(
                port=int(os.environ.get("ENVY_OAUTH_PORT", "8765")),
                access_type="offline",
                prompt="consent",
                open_browser=True,
                authorization_prompt_message="Открываю браузер для авторизации...",
                success_message="Готово, можно закрыть окно и вернуться в терминал.",
            )

        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        TOKEN_PATH.chmod(0o600)
        print(f"Токен сохранён: {TOKEN_PATH}")

    return build("youtube", "v3", credentials=creds)


# --- команды -----------------------------------------------------------------


def cmd_channel(_args) -> None:
    yt = get_service()
    resp = yt.channels().list(part="snippet,contentDetails", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        die(
            "у авторизованного аккаунта нет канала YouTube. Создай канал под "
            "envyproject@gmail.com или выбери другой аккаунт при авторизации."
        )
    for ch in items:
        print(f"Канал:   {ch['snippet']['title']}")
        print(f"ID:      {ch['id']}")
        print(f"Ссылка:  https://www.youtube.com/channel/{ch['id']}")
        uploads = ch["contentDetails"]["relatedPlaylists"].get("uploads")
        print(f"Uploads: {uploads}")
    if len(items) > 1:
        print(
            "\nВнимание: каналов несколько. При загрузке видео уйдёт в тот канал, "
            "который был выбран на экране согласия Google."
        )


def _progress(current: int, total: int) -> None:
    if not total:
        return
    pct = current * 100 / total
    bar = "#" * int(pct // 4)
    print(f"\r[{bar:<25}] {pct:5.1f}%  {current / 1e6:.1f}/{total / 1e6:.1f} MB", end="")


def cmd_upload(args) -> None:
    from googleapiclient.http import MediaFileUpload

    path = Path(args.file).expanduser()
    if not path.exists():
        die(f"файл не найден: {path}")
    if args.thumbnail and not Path(args.thumbnail).expanduser().exists():
        die(f"обложка не найдена: {args.thumbnail}")

    yt = get_service()

    body = {
        "snippet": {
            "title": args.title or path.stem,
            "description": args.description,
            "tags": args.tags,
            "categoryId": args.category,
        },
        "status": {
            "privacyStatus": args.privacy,
            "selfDeclaredMadeForKids": False,
            "license": "youtube",
        },
    }

    media = MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    print(f"Загружаю: {path.name} ({path.stat().st_size / 1e6:.1f} MB) → privacy={args.privacy}")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            _progress(status.progress(), status.total_size)
    print()

    video_id = response["id"]
    print(f"Готово. videoId={video_id}")
    print(f"https://www.youtube.com/watch?v={video_id}")
    print(f"Studio: https://studio.youtube.com/video/{video_id}/edit")

    if args.thumbnail:
        thumb = Path(args.thumbnail).expanduser()
        try:
            yt.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(str(thumb))
            ).execute()
            print(f"Обложка установлена: {thumb.name}")
        except Exception as exc:  # noqa: BLE001
            print(
                f"Обложку поставить не удалось: {exc}\n"
                "Частая причина — канал не подтверждён (нужен номер телефона) "
                "или картинка не 1280x720 / больше 2 MB.",
                file=sys.stderr,
            )

    if args.publish:
        _set_privacy(yt, video_id, "public")


def _set_privacy(yt, video_id: str, privacy: str) -> None:
    yt.videos().update(
        part="status",
        body={"id": video_id, "status": {"privacyStatus": privacy}},
    ).execute()
    print(f"Приватность {video_id} → {privacy}")


def cmd_publish(args) -> None:
    yt = get_service()
    _set_privacy(yt, args.video_id, args.privacy)


def cmd_list(args) -> None:
    yt = get_service()
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = (
        yt.playlistItems()
        .list(part="snippet", playlistId=uploads, maxResults=args.limit)
        .execute()
        .get("items", [])
    )
    if not items:
        print("На канале пока нет видео.")
        return
    for it in items:
        sn = it["snippet"]
        print(f"{sn['publishedAt'][:10]}  {sn['title']}  https://youtu.be/{sn['resourceId']['videoId']}")


# --- CLI ---------------------------------------------------------------------


def main() -> None:
    p = argparse.ArgumentParser(prog="upload.py", description="envyprjV2 YouTube uploader")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("channel", help="показать авторизованный канал").set_defaults(func=cmd_channel)

    up = sub.add_parser("upload", help="загрузить видео")
    up.add_argument("file")
    up.add_argument("--title", default="", help="название (по умолчанию — имя файла)")
    up.add_argument("--description", default="", help="описание")
    up.add_argument("--tags", nargs="*", default=[], help="теги через пробел")
    up.add_argument("--category", default="27", help="categoryId, 27 = Education")
    up.add_argument(
        "--privacy",
        default="private",
        choices=["private", "unlisted", "public"],
        help="приватность сразу после загрузки (по умолчанию private)",
    )
    up.add_argument("--thumbnail", default="", help="путь к обложке (1280x720, <2MB)")
    up.add_argument("--publish", action="store_true", help="сразу перевести в public после загрузки")
    up.set_defaults(func=cmd_upload)

    pub = sub.add_parser("publish", help="сменить приватность существующего видео")
    pub.add_argument("video_id")
    pub.add_argument("--privacy", default="public", choices=["private", "unlisted", "public"])
    pub.set_defaults(func=cmd_publish)

    ls = sub.add_parser("list", help="последние видео канала")
    ls.add_argument("--limit", type=int, default=10)
    ls.set_defaults(func=cmd_list)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
