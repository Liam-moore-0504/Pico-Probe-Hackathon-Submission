"""Signed marketplace packages that only execute inside the configured sandbox."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import ConfigDict

from orchestra.plugins.base import Plugin, PluginManifest
from orchestra.repositories.repository import Repository, dumps, loads, now


class SandboxedPackagePlugin(Plugin):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    package_path: str
    sandbox: object

    def execute(self, payload: dict) -> dict:
        with zipfile.ZipFile(self.package_path) as archive:
            source = archive.read(self.manifest.entrypoint).decode("utf-8")
        wrapper = (
            source
            + "\n\nif __name__ == '__main__':\n"
            + " import json\n"
            + f" _result = execute(json.loads({json.dumps(json.dumps(payload))}))\n"
            + " print('__ORCHESTRA_RESULT__' + json.dumps(_result, separators=(',', ':')))\n"
        )
        result = self.sandbox.execute_python(wrapper, self.manifest.timeout_seconds, self.manifest.memory_mb)
        if result["status"] != "success":
            raise RuntimeError("Sandboxed plugin execution failed")
        marker = next((line for line in reversed(result["stdout"].splitlines()) if line.startswith("__ORCHESTRA_RESULT__")), None)
        if not marker:
            raise ValueError("Plugin did not return a JSON result")
        output = json.loads(marker.removeprefix("__ORCHESTRA_RESULT__"))
        if not isinstance(output, dict):
            raise ValueError("Plugin result must be an object")
        return {**output, "execution_mode": "local", "sandbox": result["sandbox"]}


class PluginMarketplace:
    def __init__(self, repository: Repository, registry, sandbox, package_root: str):
        self.repo, self.registry, self.sandbox = repository, registry, sandbox
        self.root = Path(package_root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.load_enabled()

    def install(self, actor: UUID, manifest_data: dict, package_bytes: bytes, source: str) -> dict:
        manifest = PluginManifest.model_validate(manifest_data)
        digest = hashlib.sha256(package_bytes).hexdigest()
        if manifest.checksum and manifest.checksum.lower() != digest:
            raise ValueError("Plugin package checksum does not match its manifest")
        self._validate_archive(manifest, package_bytes)
        package_id = str(uuid4())
        path = self.root / f"{digest}.zip"
        if not path.exists():
            path.write_bytes(package_bytes)
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO plugin_packages(id,plugin_id,version,manifest,checksum,source,enabled,approval_status,installed_by,installed_at,package_path) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (package_id, manifest.plugin_id, manifest.version, dumps(manifest.model_dump(mode="json")), digest, source, 0, "pending", str(actor), now(), str(path)),
            )
            connection.execute(
                "INSERT INTO plugin_audit VALUES(?,?,?,?,?,?)",
                (str(uuid4()), package_id, str(actor), "installed", dumps({"checksum": digest, "source": source, "signed": bool(manifest.signature)}), now()),
            )
        return {"id": package_id, "plugin_id": manifest.plugin_id, "version": manifest.version, "checksum": digest, "enabled": False, "approval_status": "pending", "signature_present": bool(manifest.signature)}

    def approve(self, actor: UUID, package_id: str) -> dict:
        package = self._package(package_id)
        manifest = PluginManifest.model_validate(loads(package["manifest"], {}))
        self._verify_signature(manifest, package["checksum"])
        with self.repo.database.transaction() as connection:
            connection.execute("UPDATE plugin_packages SET approval_status='approved' WHERE id=?", (package_id,))
            connection.execute("INSERT INTO plugin_audit VALUES(?,?,?,?,?,?)", (str(uuid4()), package_id, str(actor), "approved", dumps({}), now()))
        return {"id": package_id, "approval_status": "approved"}

    def set_enabled(self, actor: UUID, package_id: str, enabled: bool) -> dict:
        package = self._package(package_id)
        if enabled and package["approval_status"] != "approved":
            raise ValueError("Only approved signed packages may be enabled")
        manifest = PluginManifest.model_validate(loads(package["manifest"], {}))
        if enabled:
            self._verify_signature(manifest, package["checksum"])
            self.registry.register(SandboxedPackagePlugin(manifest=manifest, package_path=package["package_path"], sandbox=self.sandbox))
        else:
            try:
                self.registry.set_enabled(manifest.plugin_id, False)
            except KeyError:
                pass
        with self.repo.database.transaction() as connection:
            connection.execute("UPDATE plugin_packages SET enabled=? WHERE id=?", (int(enabled), package_id))
            connection.execute("INSERT INTO plugin_audit VALUES(?,?,?,?,?,?)", (str(uuid4()), package_id, str(actor), "enabled" if enabled else "disabled", dumps({}), now()))
        return {"id": package_id, "enabled": enabled}

    def load_enabled(self) -> None:
        for package in self.repo.all("SELECT * FROM plugin_packages WHERE enabled=1 AND approval_status='approved'"):
            manifest = PluginManifest.model_validate(loads(package["manifest"], {}))
            try:
                self._verify_signature(manifest, package["checksum"])
                self.registry.register(SandboxedPackagePlugin(manifest=manifest, package_path=package["package_path"], sandbox=self.sandbox))
            except Exception:
                self.repo.execute("UPDATE plugin_packages SET enabled=0 WHERE id=?", (package["id"],))

    def list(self) -> list[dict]:
        rows = self.repo.all("SELECT * FROM plugin_packages ORDER BY installed_at DESC")
        for row in rows:
            row["manifest"] = loads(row["manifest"], {})
            row["enabled"] = bool(row["enabled"])
            row.pop("package_path", None)
        return rows

    def _package(self, package_id: str) -> dict:
        package = self.repo.one("SELECT * FROM plugin_packages WHERE id=?", (package_id,))
        if not package:
            raise ValueError("Plugin package not found")
        if not package.get("package_path") or not Path(package["package_path"]).is_file():
            raise ValueError("Plugin package content is unavailable")
        if hashlib.sha256(Path(package["package_path"]).read_bytes()).hexdigest() != package["checksum"]:
            raise ValueError("Plugin package integrity check failed")
        return package

    @staticmethod
    def _verify_signature(manifest: PluginManifest, digest: str) -> None:
        if manifest.signature_algorithm != "ed25519" or not manifest.publisher_public_key or not manifest.signature:
            raise ValueError("Publisher Ed25519 signature is required for activation")
        message = f"{manifest.plugin_id}\n{manifest.version}\n{digest}".encode()
        try:
            key = Ed25519PublicKey.from_public_bytes(base64.b64decode(manifest.publisher_public_key, validate=True))
            key.verify(base64.b64decode(manifest.signature, validate=True), message)
        except Exception as exc:
            raise ValueError("Publisher signature is invalid") from exc

    @staticmethod
    def _validate_archive(manifest: PluginManifest, content: bytes) -> None:
        if manifest.network_domains or manifest.filesystem_access not in {"none", "temporary"}:
            raise ValueError("Marketplace plugins cannot request network or persistent filesystem access")
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                total = 0
                names = set()
                for item in archive.infolist():
                    path = PurePosixPath(item.filename)
                    if path.is_absolute() or ".." in path.parts or stat.S_ISLNK(item.external_attr >> 16):
                        raise ValueError("Plugin archive contains an unsafe path")
                    total += item.file_size
                    names.add(item.filename)
                if total > 50 * 1024 * 1024:
                    raise ValueError("Plugin archive expands beyond the size limit")
                if manifest.entrypoint not in names or not manifest.entrypoint.endswith(".py"):
                    raise ValueError("Plugin archive is missing its Python entrypoint")
                archive.read(manifest.entrypoint).decode("utf-8")
        except (zipfile.BadZipFile, UnicodeDecodeError) as exc:
            raise ValueError("Plugin package must be a valid UTF-8 Python ZIP archive") from exc
