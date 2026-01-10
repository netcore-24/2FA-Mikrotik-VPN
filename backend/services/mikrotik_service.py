"""
Сервис для взаимодействия с MikroTik роутером через SSH и REST API.
"""
import paramiko
import requests
import json
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
    
    def connect(self) -> None:
        """Подключиться к MikroTik."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.ssh_key_path:
                # Подключение по SSH ключу
                key = paramiko.RSAKey.from_private_key_file(self.ssh_key_path)
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    pkey=key,
                    timeout=10,
                )
            elif self.password:
                # Подключение по паролю
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=10,
                )
            else:
                raise MikroTikConnectionError("No password or SSH key provided")
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
    
    def __init__(self, host: str, username: str, password: str, use_https: bool = False):
        self.host = host
        self.username = username
        self.password = password
        self.protocol = "https" if use_https else "http"
        self.base_url = f"{self.protocol}://{self.host}/rest"
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
                username=username,
                password=password or "",
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
    """Получить список пользователей из MikroTik User Manager."""
    config_data = _get_active_config_dict(db)
    
    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                username=config_data["username"],
                password=config_data["password"] or "",
            )
            client.connect()
            users = client.get("user")
            client.disconnect()
            return users
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
            # Выполняем команду для получения пользователей
            output = client.execute_command("/user print detail")
            client.disconnect()
            # Парсим вывод (упрощенный вариант)
            users = _parse_user_output(output)
            return users
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


def create_mikrotik_user(
    db: Session,
    username: str,
    password: str,
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    """Создать пользователя в MikroTik User Manager."""
    config_data = _get_active_config_dict(db)
    
    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                username=config_data["username"],
                password=config_data["password"] or "",
            )
            client.connect()
            data = {
                "name": username,
                "password": password,
            }
            if profile:
                data["profile"] = profile
            result = client.post("user", data)
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
            # Формируем команду создания пользователя
            cmd = f'/user add name="{username}" password="{password}"'
            if profile:
                cmd += f' profile="{profile}"'
            client.execute_command(cmd)
            client.disconnect()
            return {"name": username, "status": "created"}
    except Exception as e:
        raise MikroTikConnectionError(f"Failed to create MikroTik user: {str(e)}")


def delete_mikrotik_user(
    db: Session,
    username: str,
) -> None:
    """Удалить пользователя из MikroTik User Manager."""
    config_data = _get_active_config_dict(db)
    
    try:
        if config_data["connection_type"] == ConnectionType.REST_API.value:
            client = MikroTikRESTClient(
                host=config_data["host"],
                username=config_data["username"],
                password=config_data["password"] or "",
            )
            client.connect()
            # Находим пользователя по имени
            users = client.get("user")
            user_id = None
            for user in users:
                if user.get("name") == username:
                    user_id = user.get(".id")
                    break
            
            if not user_id:
                raise MikroTikConnectionError(f"User {username} not found")
            
            client.delete(f"user/{user_id}")
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
            client.execute_command(f'/user remove [find name="{username}"]')
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
                username=config_data["username"],
                password=config_data["password"] or "",
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
                rules = [r for r in rules if comment in r.get("comment", "")]
            
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
                rules = [r for r in rules if comment in r.get("comment", "")]
            
            return rules
    except Exception as e:
        raise MikroTikConnectionError(f"Failed to get firewall rules: {str(e)}")


def _parse_firewall_output(output: str) -> List[Dict[str, Any]]:
    """Парсинг вывода команды firewall print (упрощенный вариант)."""
    rules = []
    lines = output.split('\n')
    current_rule = {}
    
    for line in lines:
        line = line.strip()
        if line.startswith('Flags:'):
            if current_rule:
                rules.append(current_rule)
                current_rule = {}
        elif '=' in line:
            parts = line.split('=', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                current_rule[key] = value
    
    if current_rule:
        rules.append(current_rule)
    
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
                username=config_data["username"],
                password=config_data["password"] or "",
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
                username=config_data["username"],
                password=config_data["password"] or "",
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
