"""Reuse Gamdl 4.x credentials without writing or displaying secrets."""

from __future__ import annotations

from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import yaml


class AuthenticationConfigError(RuntimeError):
    """The existing Gamdl authentication settings are absent or invalid."""


def _read_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AuthenticationConfigError(
            f"No existe la configuración de Gamdl: {path}. Ejecuta primero 'gamdl auth'."
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise AuthenticationConfigError(
            f"No se pudo leer la configuración de Gamdl: {path}"
        ) from exc
    if not isinstance(data, dict):
        raise AuthenticationConfigError("La configuración de Gamdl no es un objeto YAML válido")
    return data


async def open_gamdl_api(
    config_path: Path,
    *,
    storefront: str | None = None,
    language: str | None = None,
) -> tuple[AsyncExitStack, Any]:
    """Create AppleMusicApi from the auth method already stored by Gamdl.

    Supported auth modes match Gamdl 4.x: cookies, media-user-token, and
    wrapper. The returned exit stack owns the API and, when applicable,
    the WrapperApi connection.
    """
    from gamdl.api import AppleMusicApi, WrapperApi

    config = _read_config(config_path)
    auth = config.get("auth") or {}
    if not isinstance(auth, dict):
        raise AuthenticationConfigError("La sección auth de config.yml no es válida")

    mode = auth.get("mode")
    selected_storefront = storefront or auth.get("storefront")
    selected_language = language or auth.get("language") or "en-US"
    stack = AsyncExitStack()

    try:
        if mode == "cookies":
            cookies_path = Path(
                str(auth.get("cookies_path") or config_path.parent / "cookies.txt")
            ).expanduser()
            if not cookies_path.is_absolute():
                relative_to_config = config_path.parent / cookies_path
                if relative_to_config.is_file():
                    cookies_path = relative_to_config
            api = await AppleMusicApi.from_cookies(
                str(cookies_path),
                storefront=selected_storefront,
                language=selected_language,
            )

        elif mode == "media-user-token":
            token = auth.get("media_user_token")
            if not isinstance(token, str) or not token.strip():
                raise AuthenticationConfigError(
                    "Gamdl tiene auth.mode=media-user-token, pero no hay un token configurado."
                )
            api = await AppleMusicApi.create(
                media_user_token=token.strip(),
                storefront=selected_storefront,
                language=selected_language,
            )

        elif mode == "wrapper":
            wrapper = await WrapperApi.create(
                base_url=str(auth.get("wrapper_url") or "http://127.0.0.1"),
                decrypt_host=str(auth.get("wrapper_decrypt_host") or "127.0.0.1"),
                decrypt_port=int(auth.get("wrapper_decrypt_port") or 10020),
            )
            await stack.enter_async_context(wrapper)
            api = await AppleMusicApi.from_wrapper(
                wrapper,
                storefront=selected_storefront,
                language=selected_language,
            )

        else:
            raise AuthenticationConfigError(
                "Gamdl no tiene un método de autenticación seleccionado. Ejecuta 'gamdl auth' y vuelve a intentarlo."
            )

        await stack.enter_async_context(api)
        return stack, api
    except BaseException:
        await stack.aclose()
        raise
