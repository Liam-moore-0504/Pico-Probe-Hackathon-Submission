"""Secret-storage interfaces and local Fernet implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken


class SecretBackend(ABC):
    @abstractmethod
    def encrypt(self, plaintext: str) -> str: ...

    @abstractmethod
    def decrypt(self, ciphertext: str) -> str: ...

    def delete(self, ciphertext: str) -> None:
        return None


class LocalFernetBackend(SecretBackend):
    def __init__(self, key: str):
        self.enabled = bool(key)
        self._fernet = Fernet(key.encode()) if key else None

    def encrypt(self, plaintext: str) -> str:
        if not self._fernet:
            raise RuntimeError("Credential vault is not configured")
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not self._fernet:
            raise RuntimeError("Credential vault is not configured")
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise RuntimeError("Stored credential could not be decrypted") from exc


KeyVault = LocalFernetBackend


class AWSSecretsBackend(SecretBackend):
    def __init__(self, prefix: str, region: str):
        import boto3

        self.client = boto3.client("secretsmanager", region_name=region or None)
        self.prefix = prefix
        self.enabled = True

    def encrypt(self, plaintext: str) -> str:
        name = f"{self.prefix}/credentials/{uuid4().hex}"
        response = self.client.create_secret(Name=name, SecretString=plaintext)
        return "aws-secrets://" + response["ARN"]

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext.startswith("aws-secrets://"):
            raise RuntimeError("Invalid AWS secret reference")
        return self.client.get_secret_value(SecretId=ciphertext.removeprefix("aws-secrets://"))["SecretString"]

    def delete(self, ciphertext: str) -> None:
        self.client.delete_secret(SecretId=ciphertext.removeprefix("aws-secrets://"), RecoveryWindowInDays=7)


class GCPSecretsBackend(SecretBackend):
    def __init__(self, prefix: str, project_id: str):
        from google.cloud import secretmanager

        self.client = secretmanager.SecretManagerServiceClient()
        self.project_id = project_id
        self.prefix = prefix.replace("/", "-")
        self.enabled = True

    def encrypt(self, plaintext: str) -> str:
        secret_id = f"{self.prefix}-{uuid4().hex}"
        parent = f"projects/{self.project_id}"
        secret = self.client.create_secret(request={"parent": parent, "secret_id": secret_id, "secret": {"replication": {"automatic": {}}}})
        version = self.client.add_secret_version(request={"parent": secret.name, "payload": {"data": plaintext.encode()}})
        return "gcp-secrets://" + version.name

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext.startswith("gcp-secrets://"):
            raise RuntimeError("Invalid GCP secret reference")
        return self.client.access_secret_version(request={"name": ciphertext.removeprefix("gcp-secrets://")}).payload.data.decode()

    def delete(self, ciphertext: str) -> None:
        version = ciphertext.removeprefix("gcp-secrets://")
        self.client.delete_secret(request={"name": version.rsplit("/versions/", 1)[0]})


class AzureKeyVaultBackend(SecretBackend):
    def __init__(self, prefix: str, vault_url: str):
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        self.client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
        self.prefix = prefix.replace("/", "-")
        self.enabled = True

    def encrypt(self, plaintext: str) -> str:
        name = f"{self.prefix}-{uuid4().hex}"
        self.client.set_secret(name, plaintext)
        return "azure-secrets://" + name

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext.startswith("azure-secrets://"):
            raise RuntimeError("Invalid Azure secret reference")
        return self.client.get_secret(ciphertext.removeprefix("azure-secrets://")).value

    def delete(self, ciphertext: str) -> None:
        self.client.begin_delete_secret(ciphertext.removeprefix("azure-secrets://")).wait()


def create_secret_backend(settings) -> SecretBackend:
    if settings.secret_backend == "aws":
        return AWSSecretsBackend(settings.secret_prefix, settings.aws_region)
    if settings.secret_backend == "gcp":
        return GCPSecretsBackend(settings.secret_prefix, settings.gcp_project_id)
    if settings.secret_backend == "azure":
        return AzureKeyVaultBackend(settings.secret_prefix, settings.azure_key_vault_url)
    if settings.secret_backend != "local":
        raise ValueError("ORCHESTRA_SECRET_BACKEND must be local, aws, gcp, or azure")
    return LocalFernetBackend(settings.vault_key)
