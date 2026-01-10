"""
Сервис для взаимодействия с MikroTik роутером через SSH и REST API.
"""
import paramiko
import requests
import json
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models.mikrotik_config import MikroTikConfig, ConnectionType
from backend.services.settings_service import get_settings_dict, set_setting, get_setting_value
from backend.services.mikrotik_config_service import (
    get_active_mikrotik_config as get_active_config_db,
    get_mikrotik_config_with_decrypted_password,
)


class MikroTikConnectionError(Exception):
    """Исключение для ошибок подключения к MikroTik."""
    pass


class MikroTikSSHClient:
    """Клиент для работы с MikroTik через SSH."""
    
    def __init__(self, host: str, port: int, username: str, password: Optional[str] = None, ssh_key_path: Optional[str] = None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.ssh_key_path = ssh_key_path
        self.client: Optional[paramiko.SSHClient] = None

    def _load_private_key(self, path: str):
        """
        Загрузить приватный ключ из файла.

        RouterOS/окружение часто используют ed25519/ecdsa ключи, поэтому пробуем несколько типов.
        """
        last_error: Optional[Exception] = None
        key_loaders = []
        # paramiko может не иметь Ed25519Key в старых версиях
        if hasattr(paramiko, "Ed25519Key"):
            key_loaders.append(paramiko.Ed25519Key.from_private_key_file)  # type: ignore[attr-defined]
        key_loaders.extend(
            [
                paramiko.ECDSAKey.from_private_key_file,
                paramiko.RSAKey.from_private_key_file,
                paramiko.DSSKey.from_private_key_file,
            ]
        )
        for loader in key_loaders:
            try:
                return loader(path)
            except Exception as e:  # noqa: BLE001
                last_error = e
                continue
        raise MikroTikConnectionError(
            f"Failed to load SSH private key '{path}': {last_error}"
        )
    
    def connect(self) -> None:
        """Подключиться к MikroTik."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.ssh_key_path:
                # Подключение по SSH ключу
                key = self._load_private_key(self.ssh_key_path)
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    pkey=key,
                    allow_agent=False,
                    look_for_keys=False,
                    timeout=10,
                    banner_timeout=10,
                    auth_timeout=10,
                )
            elif self.password:
                # Подключение по паролю
                try:
                    # Важно отключить agent/поиск ключей, чтобы поведение было детерминированным как у сервиса
                    self.client.connect(
                        hostname=self.host,
                        port=self.port,
                        username=self.username,
                        password=self.password,
                        allow_agent=False,
                        look_for_keys=False,
                        timeout=10,
                        banner_timeout=10,
                        auth_timeout=10,
                    )
                except (paramiko.AuthenticationException, paramiko.SSHException, EOFError) as e:
                    # На некоторых RouterOS пароль принимается только через keyboard-interactive.
                    # OpenSSH в терминале проходит, а paramiko password auth — нет.
                    transport = paramiko.Transport((self.host, self.port))
                    # В некоторых версиях paramiko есть дополнительные таймауты
                    if hasattr(transport, "banner_timeout"):
                        transport.banner_timeout = 10  # type: ignore[attr-defined]
                    if hasattr(transport, "auth_timeout"):
                        transport.auth_timeout = 10  # type: ignore[attr-defined]
                    transport.start_client(timeout=10)

                    def _handler(title, instructions, prompt_list):
                        # Возвращаем пароль на все запросы
                        return [self.password for _ in prompt_list]

                    # Сначала пробуем обычный password auth на Transport (иногда срабатывает лучше, чем SSHClient.connect)
                    try:
                        transport.auth_password(self.username, self.password)
                    except Exception:  # noqa: BLE001
                        pass

                    if not transport.is_authenticated():
                        transport.auth_interactive(self.username, _handler)
                    if not transport.is_authenticated():
                        raise MikroTikConnectionError(
                            f"Failed to connect to MikroTik via SSH: authentication failed for {self.username}@{self.host}:{self.port}. "
                            "Проверьте логин/пароль, доступ по SSH (/ip service), ограничения по address/фаерволу и права пользователя."
                        ) from e

                    # Привязываем transport к SSHClient, чтобы работали exec_command
                    self.client = paramiko.SSHClient()
                    self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    self.client._transport = transport  # noqa: SLF001
            else:
                raise MikroTikConnectionError("No password or SSH key provided")
        except paramiko.AuthenticationException as e:
            # Важно: не логируем пароль/ключи
            raise MikroTikConnectionError(
                f"Failed to connect to MikroTik via SSH: authentication failed for {self.username}@{self.host}:{self.port}. "
                "Проверьте логин/пароль, что включен SSH (/ip service), и что выбран правильный порт."
            ) from e
        except paramiko.SSHException as e:
            raise MikroTikConnectionError(
                f"Failed to connect to MikroTik via SSH: SSH error for {self.username}@{self.host}:{self.port}: {str(e)}. "
                "Часто это неправильный порт (например 443 вместо 22) или нестандартные шифры/баннер."
            ) from e
        except Exception as e:
            raise MikroTikConnectionError(f"Failed to connect to MikroTik: {str(e)}")
    
    def execute_command(self, command: str) -> str:
        """Выполнить команду на MikroTik."""
        if not self.client:
            raise MikroTikConnectionError("Not connected to MikroTik")
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            if error:
                raise MikroTikConnectionError(f"MikroTik command error: {error}")
            
            return output.strip()
        except Exception as e:
            raise MikroTikConnectionError(f"Failed to execute command: {str(e)}")
    
    def disconnect(self) -> None:
        """Отключиться от MikroTik."""
        if self.client:
            self.client.close()
            self.client = None


class MikroTikRESTClient:
    """Клиент для работы с MikroTik через REST API."""
    
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_https: bool = False,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.protocol = "https" if use_https else "http"
        # RouterOS REST живёт на веб-порту (обычно 80/443, либо кастомный)
        self.base_url = f"{self.protocol}://{self.host}:{self.port}/rest"
        self.session: Optional[requests.Session] = None
    
    def connect(self) -> None:
        """Подключиться к MikroTik REST API."""
        try:
            self.session = requests.Session()
            self.session.auth = (self.username, self.password)
            # Тестируем подключение
            response = self.session.get(f"{self.base_url}/system/identity", timeout=10)
            response.raise_for_status()
        except Exception as e:
            raise MikroTikConnectionError(f"Failed to connect to MikroTik REST API: {str(e)}")
    
    def get(self, path: str) -> List[Dict[str, Any]]:
        """GET запрос к REST API."""
        if not self.session:
            raise MikroTikConnectionError("Not connected to MikroTik REST API")
        
        try:
            response = self.session.get(f"{self.base_url}/{path}", timeout=10)
            response.raise_for_status()
            return response.json() if response.content else []
        except Exception as e:
            raise MikroTikConnectionError(f"REST API GET error: {str(e)}")
    
    def post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST запрос к REST API."""
        if not self.session:
            raise MikroTikConnectionError("Not connected to MikroTik REST API")
        
        try:
            response = self.session.post(
                f"{self.base_url}/{path}",
                json=data,
                timeout=10,
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except Exception as e:
            raise MikroTikConnectionError(f"REST API POST error: {str(e)}")
    
    def delete(self, path: str) -> None:
        """DELETE запрос к REST API."""
        if not self.session:
            raise MikroTikConnectionError("Not connected to MikroTik REST API")
        
        try:
            response = self.session.delete(f"{self.base_url}/{path}", timeout=10)
            response.raise_for_status()
        except Exception as e:
            raise MikroTikConnectionError(f"REST API DELETE error: {str(e)}")
    
    def disconnect(self) -> None:
        """Закрыть сессию."""
        if self.session:
            self.session.close()
            self.session = None


# get_active_mikrotik_config теперь импортируется из mikrotik_config_service


def test_mikrotik_connection(
    host: str,
    port: int,
    username: str,
    password: Optional[str] = None,
    ssh_key_path: Optional[str] = None,
    connection_type: ConnectionType = ConnectionType.SSH_PASSWORD,
) -> tuple[bool, Optional[str]]:
    """
    Протестировать подключение к MikroTik.
    Возвращает (успех, сообщение об ошибке).
    """
    try:
        if connection_type == ConnectionType.SSH_PASSWORD or connection_type == ConnectionType.SSH_KEY:
            client = MikroTikSSHClient(
                host=host,
                port=port,
                username=username,
                password=password if connection_type == ConnectionType.SSH_PASSWORD else None,
                ssh_key_path=ssh_key_path if connection_type == ConnectionType.SSH_KEY else None,
            )
            client.connect()
            # Выполняем простую команду для проверки
            client.execute_command("/system identity print")
            client.disconnect()
        elif connection_type == ConnectionType.REST_API:
            client = MikroTikRESTClient(
                host=host,
                port=port,
                username=username,
                password=password or "",
                use_https=(port == 443),
            )
            client.connect()
            client.get("system/identity")
            client.disconnect()
        else:
            return False, "Unsupported connection type"
        
        return True, None
    except MikroTikConnectionError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def _get_active_config_dict(db: Session) -> Dict[str, Any]:
    """Вспомогательная функция для получения активной конфигурации с расшифрованным паролем."""
    active_config = get_active_config_db(db)
    if not active_config:
        raise MikroTikConnectionError("No active MikroTik configuration found")
    config_data = get_mikrotik_config_with_decrypted_password(db, active_config.id)
    if not config_data:
        raise MikroTikConnectionError("Failed to decrypt MikroTik configuration")
    return config_data


def get_mikrotik_users(db: Session) -> List[Dict[str, Any]]:
    """
    Получить список пользователей MikroTik для VPN.

    Приоритет:
    - User Manager (`/tool user-manager user`) — если доступен
    - PPP secrets (`/ppp secret`) — fallback, если User Manager не установлен
    """
    users, _source, _warning = get_mikrotik_users_with_info(db)
    return users


def get_mikrotik_users_with_info(db: Session) -> tuple[List[Dict[str, Any]], str, Optional[str]]:
    """
    Получить список VPN пользователей и мета-информацию.

    Returns:
      - users: список пользователей (сырой вывод RouterOS REST/CLI, нормализован "name")
      - source: "user_manager" | "ppp_secret"
      - warning: человекочитаемое предупреждение (если есть)
    """
    config_data = _get_active_config_dict(db)

    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                port=int(config_data["port"]),
                username=config_data["username"],
                password=config_data["password"] or "",
                use_https=(int(config_data["port"]) == 443),
            )
            client.connect()
            try:
                # 1) User Manager
                users = client.get("tool/user-manager/user")
                # нормализуем имя: RouterOS часто использует поле username вместо name
                for u in users:
                    if isinstance(u, dict) and not u.get("name") and u.get("username"):
                        u["name"] = u.get("username")
                client.disconnect()
                return users, "user_manager", None
            except Exception:
                # 2) PPP secrets fallback
                secrets = client.get("ppp/secret")
                for u in secrets:
                    if isinstance(u, dict) and not u.get("name") and u.get("username"):
                        u["name"] = u.get("username")
                warning = (
                    None
                    if secrets
                    else "User Manager не установлен/недоступен на MikroTik и PPP secrets пусты — на роутере нет VPN пользователей для отображения."
                )
                if secrets:
                    warning = "User Manager не установлен/недоступен на MikroTik — отображаем PPP secrets."
            client.disconnect()
            return secrets, "ppp_secret", warning
        else:
            # SSH подключение
            connection_type_enum = ConnectionType(config_data["connection_type"])
            client = MikroTikSSHClient(
                host=config_data["host"],
                port=config_data["port"],
                username=config_data["username"],
                password=config_data["password"] if connection_type_enum == ConnectionType.SSH_PASSWORD else None,
                ssh_key_path=config_data["ssh_key_path"] if connection_type_enum == ConnectionType.SSH_KEY else None,
            )
            client.connect()
            # 1) пробуем User Manager (RouterOS v7: /user-manager)
            output = client.execute_command("/user-manager user print detail")
            if not _is_routeros_cli_error_output(output):
                client.disconnect()
                return _parse_user_manager_output(output), "user_manager", None

            # 1b) старый путь (встречается в некоторых сборках/доках)
            output = client.execute_command("/tool user-manager user print detail")
            if not _is_routeros_cli_error_output(output):
                client.disconnect()
                return _parse_user_manager_output(output), "user_manager", None

            # 2) fallback на PPP secrets
            output = client.execute_command("/ppp secret print detail")
            client.disconnect()
            secrets = _parse_ppp_print_detail_output(output, username_key="name")
            warning = (
                None
                if secrets
                else "User Manager не установлен/недоступен на MikroTik и PPP secrets пусты — на роутере нет VPN пользователей для отображения."
            )
            if secrets:
                warning = "User Manager не установлен/недоступен на MikroTik — отображаем PPP secrets."
            return secrets, "ppp_secret", warning
    except Exception as e:
        raise MikroTikConnectionError(f"Failed to get MikroTik users: {str(e)}")


def _parse_user_output(output: str) -> List[Dict[str, Any]]:
    """Парсинг вывода команды /user print detail (упрощенный вариант)."""
    # Это упрощенный парсер, в реальности нужен более сложный парсинг
    users = []
    lines = output.split('\n')
    current_user = {}
    
    for line in lines:
        line = line.strip()
        if line.startswith('Flags:'):
            if current_user:
                users.append(current_user)
                current_user = {}
        elif '=' in line:
            parts = line.split('=', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                current_user[key] = value
    
    if current_user:
        users.append(current_user)
    
    return users


def _is_routeros_cli_error_output(output: str) -> bool:
    """
    RouterOS иногда пишет ошибки в stdout (а не в stderr),
    поэтому проверяем текст вывода на типичные маркеры ошибок.
    """
    text = (output or "").strip().lower()
    if not text:
        return False
    return (
        "bad command name" in text
        or "no such item" in text
        or "input does not match" in text
        or "syntax error" in text
        or text.startswith("failure:")
    )


# ВАЖНО: RouterOS часто использует ключи вида ".id=*1", поэтому поддерживаем точку в имени ключа.
# Также значения часто НЕ в кавычках (chain=forward, action=accept, .id=*1),
# поэтому используем \S+ (а не литеральное \\S+).
_KV_RE = re.compile(r'([A-Za-z0-9_.-]+)=("([^"\\]|\\.)*"|\S+)')


def _parse_kv_pairs_from_line(line: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for m in _KV_RE.finditer(line):
        key = m.group(1)
        value = m.group(2)
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            value = value[1:-1]
        result[key] = value
    return result


def _normalize_bool(value: Any) -> Optional[bool]:
    """Нормализовать RouterOS boolean-значения (REST/CLI) в Python bool."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in {"true", "yes", "enabled", "enable", "1"}:
        return True
    if s in {"false", "no", "disabled", "disable", "0"}:
        return False
    return None


def _split_routeros_index_and_flags(line: str) -> tuple[Optional[int], str, str]:
    """
    Разобрать начало строки RouterOS вида:
      '0 X name="user" ...'
      '1   name="user2" ...'
      '72 X'
      '72 X   ;;; comment' (после удаления ';;;' останется '72 X')
      '72'

    Returns: (number, flags, rest)
    """
    # num + FLAGS + optional rest
    m = re.match(r"^(?P<num>\d+)\s+(?P<flags>[A-Z]+)(?:\s+(?P<rest>.+))?$", line)
    if m:
        rest = (m.group("rest") or "").strip()
        return int(m.group("num")), (m.group("flags") or ""), rest
    # num + optional rest
    m2 = re.match(r"^(?P<num>\d+)(?:\s+(?P<rest>.+))?$", line)
    if m2:
        rest = (m2.group("rest") or "").strip()
        return int(m2.group("num")), "", rest
    return None, "", line.strip()


def _parse_ppp_print_detail_output(output: str, username_key: str = "name") -> List[Dict[str, Any]]:
    """
    Парсинг вывода RouterOS `print detail` для PPP сущностей (`/ppp secret` и `/ppp active`).
    Учитывает формат "одна запись в одной строке" (с индексом в начале).
    """
    items: List[Dict[str, Any]] = []
    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Flags:") or line.startswith("#"):
            continue
        # убираем комментарии RouterOS ";;;" (если есть)
        if ";;;" in line:
            line = line.split(";;;", 1)[0].strip()
        number, flags, rest = _split_routeros_index_and_flags(line)
        # для PPP вывод обычно "одна запись в одной строке"; index/flags (если есть) отрезаем
        line = rest

        kv = _parse_kv_pairs_from_line(line)
        if not kv:
            continue

        if number is not None:
            kv["number"] = number

        # disabled: либо флаг X, либо поле disabled=
        disabled_from_flags = True if "X" in (flags or "") else None
        disabled_from_field = _normalize_bool(kv.get("disabled"))
        kv["disabled"] = (
            disabled_from_field
            if disabled_from_field is not None
            else disabled_from_flags
        )

        # нормализуем "user" для совместимости с логикой сессий
        if "user" not in kv:
            kv["user"] = kv.get(username_key) or kv.get("username") or kv.get("name")
        items.append(kv)
    return items


def create_mikrotik_user(
    db: Session,
    username: str,
    password: str,
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Создать VPN пользователя на MikroTik.

    Приоритет:
    - User Manager user
    - PPP secret (fallback, если User Manager недоступен)
    """
    config_data = _get_active_config_dict(db)
    
    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                port=int(config_data["port"]),
                username=config_data["username"],
                password=config_data["password"] or "",
                use_https=(int(config_data["port"]) == 443),
            )
            client.connect()
            # 1) User Manager
            try:
                data = {
                    "customer": "admin",
                    "username": username,
                    "password": password,
                }
                result = client.post("tool/user-manager/user", data)
                if profile:
                    # Пытаемся активировать профиль (если endpoint доступен)
                    try:
                        client.post(
                            "tool/user-manager/user/create-and-activate-profile",
                            {"customer": "admin", "numbers": username, "profile": profile},
                        )
                    except Exception:
                        pass
                client.disconnect()
                return result
            except Exception:
                # 2) PPP secret fallback
                data = {
                    "name": username,
                    "password": password,
                    # Без знания типа сервиса безопаснее "any"
                    "service": "any",
                }
                if profile:
                    data["profile"] = profile
                result = client.post("ppp/secret", data)
            client.disconnect()
            return result
        else:
            # SSH подключение
            connection_type_enum = ConnectionType(config_data["connection_type"])
            client = MikroTikSSHClient(
                host=config_data["host"],
                port=config_data["port"],
                username=config_data["username"],
                password=config_data["password"] if connection_type_enum == ConnectionType.SSH_PASSWORD else None,
                ssh_key_path=config_data["ssh_key_path"] if connection_type_enum == ConnectionType.SSH_KEY else None,
            )
            client.connect()
            # 1) User Manager
            out = client.execute_command(
                f'/tool user-manager user add customer="admin" username="{username}" password="{password}"'
            )
            if _is_routeros_cli_error_output(out):
                # 2) PPP secret fallback
                cmd = f'/ppp secret add name="{username}" password="{password}" service=any'
                if profile:
                    cmd += f' profile="{profile}"'
                out2 = client.execute_command(cmd)
                if _is_routeros_cli_error_output(out2):
                    client.disconnect()
                    raise MikroTikConnectionError(f"Failed to create PPP secret: {out2 or out}")
            else:
                if profile:
                    try:
                        client.execute_command(
                            f'/tool user-manager user create-and-activate-profile customer="admin" numbers="{username}" profile="{profile}"'
                        )
                    except Exception:
                        pass
            client.disconnect()
            return {"name": username, "status": "created"}
    except Exception as e:
        raise MikroTikConnectionError(f"Failed to create MikroTik user: {str(e)}")


def delete_mikrotik_user(
    db: Session,
    username: str,
) -> None:
    """Удалить VPN пользователя (User Manager или PPP secret)."""
    config_data = _get_active_config_dict(db)
    
    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                port=int(config_data["port"]),
                username=config_data["username"],
                password=config_data["password"] or "",
                use_https=(int(config_data["port"]) == 443),
            )
            client.connect()
            # 1) User Manager
            try:
                users = client.get("tool/user-manager/user")
                user_id = None
                for user in users:
                    if user.get("username") == username or user.get("name") == username:
                        user_id = user.get(".id")
                        break
                if user_id:
                    client.delete(f"tool/user-manager/user/{user_id}")
                    client.disconnect()
                    return
            except Exception:
                pass

            # 2) PPP secret fallback
            secrets = client.get("ppp/secret")
            secret_id = None
            for s in secrets:
                if s.get("name") == username:
                    secret_id = s.get(".id")
                    break
            if not secret_id:
                raise MikroTikConnectionError(f"User {username} not found")
            client.delete(f"ppp/secret/{secret_id}")
            client.disconnect()
        else:
            # SSH подключение
            connection_type_enum = ConnectionType(config_data["connection_type"])
            client = MikroTikSSHClient(
                host=config_data["host"],
                port=config_data["port"],
                username=config_data["username"],
                password=config_data["password"] if connection_type_enum == ConnectionType.SSH_PASSWORD else None,
                ssh_key_path=config_data["ssh_key_path"] if connection_type_enum == ConnectionType.SSH_KEY else None,
            )
            client.connect()
            out = client.execute_command(f'/tool user-manager user remove [find username="{username}"]')
            if _is_routeros_cli_error_output(out):
                out2 = client.execute_command(f'/ppp secret remove [find name="{username}"]')
                if _is_routeros_cli_error_output(out2):
                    client.disconnect()
                    raise MikroTikConnectionError(f"User {username} not found")
            client.disconnect()
    except Exception as e:
        raise MikroTikConnectionError(f"Failed to delete MikroTik user: {str(e)}")


def get_firewall_rules(
    db: Session,
    chain: Optional[str] = None,
    comment: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Получить правила firewall из MikroTik."""
    config_data = _get_active_config_dict(db)
    
    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                port=int(config_data["port"]),
                username=config_data["username"],
                password=config_data["password"] or "",
                use_https=(int(config_data["port"]) == 443),
            )
            client.connect()
            path = "ip/firewall/filter"
            if chain:
                # Фильтрация по цепочке через параметры запроса
                rules = client.get(path)
                rules = [r for r in rules if r.get("chain") == chain]
            else:
                rules = client.get(path)
            
            if comment:
                needle = str(comment).lower()
                rules = [r for r in rules if needle in str(r.get("comment", "")).lower()]
            
            client.disconnect()
            return rules
        else:
            # SSH подключение
            connection_type_enum = ConnectionType(config_data["connection_type"])
            client = MikroTikSSHClient(
                host=config_data["host"],
                port=config_data["port"],
                username=config_data["username"],
                password=config_data["password"] if connection_type_enum == ConnectionType.SSH_PASSWORD else None,
                ssh_key_path=config_data["ssh_key_path"] if connection_type_enum == ConnectionType.SSH_KEY else None,
            )
            client.connect()
            cmd = "/ip firewall filter print detail"
            output = client.execute_command(cmd)
            client.disconnect()
            # Парсим вывод (упрощенный вариант)
            rules = _parse_firewall_output(output)
            
            if chain:
                rules = [r for r in rules if r.get("chain") == chain]
            if comment:
                needle = str(comment).lower()
                rules = [r for r in rules if needle in str(r.get("comment", "")).lower()]
            
            return rules
    except Exception as e:
        raise MikroTikConnectionError(f"Failed to get firewall rules: {str(e)}")


def _parse_firewall_output(output: str) -> List[Dict[str, Any]]:
    """
    Парсинг вывода RouterOS `/ip firewall filter print detail`.

    Учитывает формат:
      Flags: X - disabled ...
      0 X chain=... action=... comment="..." .id=*1
      1   chain=... ...
    Комментарий может быть:
      - inline: `0   ;;; BASE: ...`
      - отдельной строкой: `;;; BASE: ...`
    """
    rules: List[Dict[str, Any]] = []
    pending_comment: Optional[str] = None
    current: Optional[Dict[str, Any]] = None
    current_flags: str = ""

    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Flags:") or line.startswith("#"):
            continue

        # Комментарий может быть отдельной строкой или inline
        if ";;;" in line:
            before, after = line.split(";;;", 1)
            comment_text = after.strip()
            if comment_text:
                pending_comment = comment_text
            line = before.strip()
            if not line:
                continue

        # Новая запись начинается со строки с индексом
        if line[:1].isdigit():
            if current:
                # нормализуем disabled если не установлен из поля
                if "disabled" not in current or current["disabled"] is None:
                    current["disabled"] = True if "X" in (current_flags or "") else False
                rules.append(current)

            number, flags, rest = _split_routeros_index_and_flags(line)
            current_flags = flags or ""
            current = {}
            if number is not None:
                current["number"] = number
            # переносим pending comment на запись
            if pending_comment:
                current["comment"] = pending_comment
                pending_comment = None

            kv = _parse_kv_pairs_from_line(rest)
            if kv:
                current.update(kv)
            continue

        # continuation line для текущей записи
        if current is None:
            continue
        kv = _parse_kv_pairs_from_line(line)
        if kv:
            current.update(kv)

    if current:
        if "disabled" not in current or current["disabled"] is None:
            current["disabled"] = True if "X" in (current_flags or "") else False
        rules.append(current)

    # Нормализуем disabled поле, если оно строковое
    for r in rules:
        b = _normalize_bool(r.get("disabled"))
        if b is not None:
            r["disabled"] = b

    return rules


def enable_firewall_rule(
    db: Session,
    rule_id: str,
) -> None:
    """Включить правило firewall по ID."""
    config_data = _get_active_config_dict(db)
    
    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                port=int(config_data["port"]),
                username=config_data["username"],
                password=config_data["password"] or "",
                use_https=(int(config_data["port"]) == 443),
            )
            client.connect()
            client.post(f"ip/firewall/filter/{rule_id}", {"disabled": "false"})
            client.disconnect()
        else:
            # SSH подключение
            connection_type_enum = ConnectionType(config_data["connection_type"])
            client = MikroTikSSHClient(
                host=config_data["host"],
                port=config_data["port"],
                username=config_data["username"],
                password=config_data["password"] if connection_type_enum == ConnectionType.SSH_PASSWORD else None,
                ssh_key_path=config_data["ssh_key_path"] if connection_type_enum == ConnectionType.SSH_KEY else None,
            )
            client.connect()
            # На некоторых RouterOS в выводе print detail может не быть .id, зато есть номер правила.
            # Поддерживаем оба варианта: либо .id=*XX, либо numbers=NN.
            if str(rule_id).isdigit():
                client.execute_command(f"/ip firewall filter enable numbers={rule_id}")
            else:
                client.execute_command(f'/ip firewall filter enable [find .id="{rule_id}"]')
            client.disconnect()
    except Exception as e:
        raise MikroTikConnectionError(f"Failed to enable firewall rule: {str(e)}")


def disable_firewall_rule(
    db: Session,
    rule_id: str,
) -> None:
    """Выключить правило firewall по ID."""
    config_data = _get_active_config_dict(db)
    
    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                port=int(config_data["port"]),
                username=config_data["username"],
                password=config_data["password"] or "",
                use_https=(int(config_data["port"]) == 443),
            )
            client.connect()
            client.post(f"ip/firewall/filter/{rule_id}", {"disabled": "true"})
            client.disconnect()
        else:
            # SSH подключение
            connection_type_enum = ConnectionType(config_data["connection_type"])
            client = MikroTikSSHClient(
                host=config_data["host"],
                port=config_data["port"],
                username=config_data["username"],
                password=config_data["password"] if connection_type_enum == ConnectionType.SSH_PASSWORD else None,
                ssh_key_path=config_data["ssh_key_path"] if connection_type_enum == ConnectionType.SSH_KEY else None,
            )
            client.connect()
            if str(rule_id).isdigit():
                client.execute_command(f"/ip firewall filter disable numbers={rule_id}")
            else:
                client.execute_command(f'/ip firewall filter disable [find .id="{rule_id}"]')
            client.disconnect()
    except Exception as e:
        raise MikroTikConnectionError(f"Failed to disable firewall rule: {str(e)}")


def find_firewall_rule_by_comment(
    db: Session,
    comment: str,
) -> Optional[Dict[str, Any]]:
    """Найти правило firewall по комментарию."""
    rules = get_firewall_rules(db, comment=comment)
    if rules:
        return rules[0]
    return None


def get_user_manager_users(db: Session) -> Dict[str, Any]:
    """Получить список пользователей из MikroTik User Manager."""
    config_data = _get_active_config_dict(db)
    
    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                port=int(config_data["port"]),
                username=config_data["username"],
                password=config_data["password"] or "",
                use_https=(int(config_data["port"]) == 443),
            )
            client.connect()
            # Для REST API пробуем оба пути:
            # - RouterOS v7 часто: user-manager/user
            # - иногда встречается: tool/user-manager/user
            try:
                users = client.get("user-manager/user")
            except:
                try:
                    users = client.get("tool/user-manager/user")
                except Exception:
                    # Если User Manager не установлен или недоступен, возвращаем пустой список
                    users = []
            client.disconnect()
            return {"users": users, "total": len(users)}
        else:
            # SSH подключение
            connection_type_enum = ConnectionType(config_data["connection_type"])
            client = MikroTikSSHClient(
                host=config_data["host"],
                port=config_data["port"],
                username=config_data["username"],
                password=config_data["password"] if connection_type_enum == ConnectionType.SSH_PASSWORD else None,
                ssh_key_path=config_data["ssh_key_path"] if connection_type_enum == ConnectionType.SSH_KEY else None,
            )
            client.connect()
            # Выполняем команду для получения пользователей User Manager
            try:
                # RouterOS v7
                output = client.execute_command("/user-manager user print detail")
                if _is_routeros_cli_error_output(output):
                    # fallback: старый путь
                    output = client.execute_command("/tool user-manager user print detail")
                users = [] if _is_routeros_cli_error_output(output) else _parse_user_manager_output(output)
            except:
                # Если User Manager не установлен или недоступен, возвращаем пустой список
                users = []
            client.disconnect()
            return {"users": users, "total": len(users)}
    except Exception as e:
        raise MikroTikConnectionError(f"Failed to get User Manager users: {str(e)}")


def _parse_user_manager_output(output: str) -> List[Dict[str, Any]]:
    """Парсинг вывода команды /tool user-manager user print detail."""
    users: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}
    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Flags:") or line.startswith("#"):
            continue

        # Новая запись обычно начинается со строки с индексом "0", "1", ...
        if line[:1].isdigit():
            if current and (current.get("name") or current.get("username")):
                if "name" not in current and "username" in current:
                    current["name"] = current.get("username")
                users.append(current)
            current = {}
            number, flags, rest = _split_routeros_index_and_flags(line)
            if number is not None:
                current["number"] = number
            current["disabled"] = True if "X" in (flags or "") else False
            line = rest

        # В RouterOS пары key=value могут быть в одной строке
        kv = _parse_kv_pairs_from_line(line)
        if kv:
            current.update(kv)

    if current and (current.get("name") or current.get("username")):
        if "name" not in current and "username" in current:
            current["name"] = current.get("username")
        users.append(current)

    # Нормализуем disabled (на случай REST/других форматов)
    for u in users:
        u["disabled"] = _normalize_bool(u.get("disabled")) if _normalize_bool(u.get("disabled")) is not None else bool(u.get("disabled"))

    return users


def _parse_user_manager_session_output(output: str) -> List[Dict[str, Any]]:
    """
    Парсинг вывода команды `/user-manager session print detail`.

    Формат похож на:
      Flags: A - active
       0   user=noadmin acct-session-id="85600000" ...
           status=... started=... ended=...

    Активность в UI отмечена флагом "A". В выводе это обычно выглядит как:
       6 A user=...
    """
    sessions: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    current_flags: str = ""

    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Flags:") or line.startswith("#"):
            continue

        # RouterOS ";;;" комментарии на всякий случай
        if ";;;" in line:
            line = line.split(";;;", 1)[0].strip()
            if not line:
                continue

        if line[:1].isdigit():
            # flush previous
            if current:
                # вычисляем active, если не было выставлено
                if "active" not in current or current.get("active") is None:
                    current["active"] = True if "A" in (current_flags or "") else False
                # нормализуем user поле
                if "user" not in current:
                    current["user"] = current.get("username") or current.get("name")
                # выставляем mikrotik_session_id для удобства (acct-session-id в UM)
                if "mikrotik_session_id" not in current:
                    current["mikrotik_session_id"] = (
                        # Важно: для User Manager "правильный" ID сессии — acct-session-id (его и показываем пользователю)
                        current.get("acct-session-id")
                        or current.get("acct_session_id")
                        or current.get(".id")
                        or current.get("id")
                    )
                sessions.append(current)

            number, flags, rest = _split_routeros_index_and_flags(line)
            current_flags = flags or ""
            current = {}
            if number is not None:
                current["number"] = number
            # базовая активность по флагу
            current["active"] = True if "A" in (current_flags or "") else False
            kv = _parse_kv_pairs_from_line(rest)
            if kv:
                current.update(kv)
            continue

        # continuation line
        if current is None:
            continue
        kv = _parse_kv_pairs_from_line(line)
        if kv:
            current.update(kv)

    if current:
        if "active" not in current or current.get("active") is None:
            current["active"] = True if "A" in (current_flags or "") else False
        if "user" not in current:
            current["user"] = current.get("username") or current.get("name")
        if "mikrotik_session_id" not in current:
            current["mikrotik_session_id"] = (
                current.get("acct-session-id")
                or current.get("acct_session_id")
                or current.get(".id")
                or current.get("id")
            )
        sessions.append(current)

    # Доп. эвристика: если RouterOS по какой-то причине не печатает "A",
    # но сессия выглядит активной (нет ended= и нет expired в status) — считаем active.
    for s in sessions:
        if s.get("active") is True:
            continue
        status = str(s.get("status") or "").lower()
        ended = s.get("ended")
        if (ended is None or str(ended).strip() == "") and ("expired" not in status):
            s["active"] = True

    return sessions


def get_user_manager_sessions(db: Session) -> List[Dict[str, Any]]:
    """
    Получить активные сессии User Manager.
    Используется для определения факта подключения пользователя.
    """
    config_data = _get_active_config_dict(db)
    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                port=int(config_data["port"]),
                username=config_data["username"],
                password=config_data["password"] or "",
                use_https=(int(config_data["port"]) == 443),
            )
            client.connect()
            sessions: List[Dict[str, Any]] = []
            # 1) User Manager sessions (если доступно)
            try:
                sessions = client.get("user-manager/session")
            except Exception:
                try:
                    sessions = client.get("tool/user-manager/session")
                except Exception:
                    sessions = []

            # Нормализуем структуру REST UM sessions под scheduler:
            # - active (bool)
            # - user (username)
            for s in sessions:
                s["source"] = "user_manager_session"
                # RouterOS REST часто отдаёт "active": "true"/"false"
                b = _normalize_bool(s.get("active"))
                if b is not None:
                    s["active"] = b
                if "user" not in s:
                    s["user"] = s.get("username") or s.get("name")
                if "mikrotik_session_id" not in s:
                    s["mikrotik_session_id"] = (
                        s.get("acct-session-id")
                        or s.get("acct_session_id")
                        or s.get(".id")
                        or s.get("id")
                    )

            # 2) PPP active sessions (часто это “факт подключения”, даже если UM не используется/не отдаёт активные)
            ppp_active: List[Dict[str, Any]] = []
            try:
                ppp_active = client.get("ppp/active") or []
            except Exception:
                ppp_active = []
            for s in ppp_active:
                s["source"] = "ppp_active"
                # ppp/active = всегда активные
                s["active"] = True
                if "user" not in s:
                    s["user"] = s.get("name") or s.get("username") or s.get("user")
                if "mikrotik_session_id" not in s:
                    s["mikrotik_session_id"] = (
                        s.get("session-id")
                        or s.get("session_id")
                        or s.get(".id")
                        or s.get("id")
                    )

            client.disconnect()
            return sessions + ppp_active
        # SSH
        connection_type_enum = ConnectionType(config_data["connection_type"])
        client = MikroTikSSHClient(
            host=config_data["host"],
            port=config_data["port"],
            username=config_data["username"],
            password=config_data["password"] if connection_type_enum == ConnectionType.SSH_PASSWORD else None,
            ssh_key_path=config_data["ssh_key_path"] if connection_type_enum == ConnectionType.SSH_KEY else None,
        )
        client.connect()
        sessions: List[Dict[str, Any]] = []

        # 1) User Manager sessions (если команда есть)
        # Оптимизация: запрашиваем только активные (флаг A), иначе вывод может быть очень большим
        output_um = client.execute_command("/user-manager session print detail where active")
        if _is_routeros_cli_error_output(output_um):
            # fallback: полный вывод (если where active не поддерживается)
            output_um = client.execute_command("/user-manager session print detail")
        if _is_routeros_cli_error_output(output_um):
            # fallback: старый путь
            output_um = client.execute_command("/tool user-manager session print detail where active")
            if _is_routeros_cli_error_output(output_um):
                output_um = client.execute_command("/tool user-manager session print detail")
        if not _is_routeros_cli_error_output(output_um):
            um = _parse_user_manager_session_output(output_um)
            for s in um:
                s["source"] = "user_manager_session"
            sessions.extend(um)

        # 2) PPP active sessions (фактические подключения)
        output_ppp = client.execute_command("/ppp active print detail")
        if not _is_routeros_cli_error_output(output_ppp):
            ppp = _parse_ppp_print_detail_output(output_ppp, username_key="name")
            for s in ppp:
                s["source"] = "ppp_active"
                s["active"] = True
                if "mikrotik_session_id" not in s:
                    s["mikrotik_session_id"] = (
                        s.get("session-id")
                        or s.get("session_id")
                        or s.get(".id")
                        or s.get("id")
                    )
            sessions.extend(ppp)

        client.disconnect()
        return sessions
    except Exception as e:
        raise MikroTikConnectionError(f"Failed to get User Manager sessions: {str(e)}")


def set_user_manager_user_disabled(db: Session, mikrotik_username: str, disabled: bool) -> None:
    """Включить/выключить пользователя в MikroTik User Manager (disabled=yes/no)."""
    config_data = _get_active_config_dict(db)
    value = "true" if disabled else "false"

    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                port=int(config_data["port"]),
                username=config_data["username"],
                password=config_data["password"] or "",
                use_https=(int(config_data["port"]) == 443),
            )
            client.connect()
            # 1) User Manager (если доступен)
            try:
                users = client.get("tool/user-manager/user")
                user_id = None
                for u in users:
                    if u.get("username") == mikrotik_username or u.get("name") == mikrotik_username:
                        user_id = u.get(".id")
                        break
                if user_id:
                    client.post(f"tool/user-manager/user/{user_id}", {"disabled": value})
                    client.disconnect()
                    return
            except Exception:
                pass

            # 2) fallback: PPP secret
            secrets = client.get("ppp/secret")
            secret_id = None
            for s in secrets:
                if s.get("name") == mikrotik_username:
                    secret_id = s.get(".id")
                    break
            if not secret_id:
                raise MikroTikConnectionError(f"VPN user '{mikrotik_username}' not found (no User Manager, no PPP secret)")
            client.post(f"ppp/secret/{secret_id}", {"disabled": value})
            client.disconnect()
            return

        # SSH
        connection_type_enum = ConnectionType(config_data["connection_type"])
        client = MikroTikSSHClient(
            host=config_data["host"],
            port=config_data["port"],
            username=config_data["username"],
            password=config_data["password"] if connection_type_enum == ConnectionType.SSH_PASSWORD else None,
            ssh_key_path=config_data["ssh_key_path"] if connection_type_enum == ConnectionType.SSH_KEY else None,
        )
        client.connect()
        # 1) User Manager
        # RouterOS v7 использует /user-manager и поле name=
        cmd = f'/user-manager user set [find name="{mikrotik_username}"] disabled={"yes" if disabled else "no"}'
        out = client.execute_command(cmd)
        if _is_routeros_cli_error_output(out):
            # fallback: старый путь (/tool user-manager)
            cmd_old = f'/tool user-manager user set [find username="{mikrotik_username}"] disabled={"yes" if disabled else "no"}'
            out_old = client.execute_command(cmd_old)
            if _is_routeros_cli_error_output(out_old):
                # 2) fallback: PPP secret
                cmd2 = f'/ppp secret set [find name="{mikrotik_username}"] disabled={"yes" if disabled else "no"}'
                out2 = client.execute_command(cmd2)
                if _is_routeros_cli_error_output(out2):
                    client.disconnect()
                    raise MikroTikConnectionError(
                        f"Failed to set VPN user '{mikrotik_username}' disabled={disabled}: {out2 or out_old or out}"
                    )
        client.disconnect()
    except Exception as e:
        raise MikroTikConnectionError(f"Failed to set User Manager user disabled={disabled}: {str(e)}")


def terminate_active_sessions_for_username(db: Session, mikrotik_username: str) -> None:
    """
    Попытаться принудительно завершить активные подключения пользователя на MikroTik.

    Важно: в RouterOS отключение user/secret не всегда мгновенно рвёт уже поднятую PPP-сессию,
    поэтому дополнительно пытаемся удалить активную PPP и/или UM session.
    """
    if not mikrotik_username:
        return

    config_data = _get_active_config_dict(db)
    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                port=int(config_data["port"]),
                username=config_data["username"],
                password=config_data["password"] or "",
                use_https=(int(config_data["port"]) == 443),
            )
            client.connect()
            try:
                # 1) PPP active
                try:
                    active = client.get("ppp/active") or []
                    for a in active:
                        name = a.get("name") or a.get("user") or a.get("username")
                        if name != mikrotik_username:
                            continue
                        rid = a.get(".id") or a.get("id")
                        if rid:
                            try:
                                client.delete(f"ppp/active/{rid}")
                            except Exception:
                                pass
                except Exception:
                    pass

                # 2) User Manager session (если доступно)
                for path in ("user-manager/session", "tool/user-manager/session"):
                    try:
                        um = client.get(path) or []
                    except Exception:
                        continue
                    for s in um:
                        u = s.get("user") or s.get("username") or s.get("name")
                        if u != mikrotik_username:
                            continue
                        b = _normalize_bool(s.get("active"))
                        if b is False:
                            continue
                        rid = s.get(".id") or s.get("id")
                        if rid:
                            try:
                                client.delete(f"{path}/{rid}")
                            except Exception:
                                pass
            finally:
                client.disconnect()
            return

        # SSH
        connection_type_enum = ConnectionType(config_data["connection_type"])
        client = MikroTikSSHClient(
            host=config_data["host"],
            port=config_data["port"],
            username=config_data["username"],
            password=config_data["password"] if connection_type_enum == ConnectionType.SSH_PASSWORD else None,
            ssh_key_path=config_data["ssh_key_path"] if connection_type_enum == ConnectionType.SSH_KEY else None,
        )
        client.connect()
        try:
            # 1) PPP active remove
            cmd_ppp = f'/ppp active remove [find name="{mikrotik_username}"]'
            out_ppp = client.execute_command(cmd_ppp)
            if _is_routeros_cli_error_output(out_ppp):
                # иногда user вместо name
                cmd_ppp2 = f'/ppp active remove [find user="{mikrotik_username}"]'
                client.execute_command(cmd_ppp2)

            # 2) User Manager session remove (разные пути на разных версиях)
            cmd_um = f'/user-manager session remove [find user="{mikrotik_username}" and active]'
            out_um = client.execute_command(cmd_um)
            if _is_routeros_cli_error_output(out_um):
                cmd_um2 = f'/tool user-manager session remove [find user="{mikrotik_username}"]'
                client.execute_command(cmd_um2)
        finally:
            client.disconnect()
    except Exception:
        # Не валим основной флоу — это best-effort
        return


def enable_user_manager_user(db: Session, mikrotik_username: str) -> None:
    """Разрешить пользователю подключение (disabled=no)."""
    set_user_manager_user_disabled(db, mikrotik_username, disabled=False)


def disable_user_manager_user(db: Session, mikrotik_username: str) -> None:
    """Запретить пользователю подключение (disabled=yes)."""
    set_user_manager_user_disabled(db, mikrotik_username, disabled=True)
