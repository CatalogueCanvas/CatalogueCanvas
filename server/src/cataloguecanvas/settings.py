from __future__ import annotations
import os
import secrets
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.data_dir = Path(os.environ.get("CC_DATA_DIR", "/data"))
        self.db_path = Path(os.environ.get("CC_DB_PATH", str(self.data_dir / "catalogue.db")))
        self.storage_dir = Path(os.environ.get("CC_STORAGE_DIR", str(self.data_dir / "storage")))
        self.admin_password = os.environ.get("CC_ADMIN_PASSWORD", "")
        self.admin_username = os.environ.get("CC_ADMIN_USERNAME", "admin")
        secret_key_file = os.environ.get("CC_SECRET_KEY_FILE")
        if secret_key_file:
            self.secret_key = Path(secret_key_file).read_text().strip()
        elif os.environ.get("CC_SECRET_KEY"):
            self.secret_key = os.environ["CC_SECRET_KEY"]
        else:
            # No secret configured: generate a random one and persist it under
            # data_dir so sessions stay valid across restarts. Never fall back to
            # a hard-coded default, which would make session tokens forgeable.
            self.secret_key = self._load_or_create_secret()
        self.site_title = os.environ.get("CC_SITE_TITLE", "My Catalogue")
        self.site_author = os.environ.get("CC_SITE_AUTHOR", "")
        self.static_dir = Path(os.environ.get("CC_STATIC_DIR", str(Path(__file__).resolve().parents[3] / "web" / "dist")))
        self.cookie_secure = os.environ.get("CC_COOKIE_SECURE", "true").lower() not in ("0", "false", "no")
        self.max_upload_bytes = int(os.environ.get("CC_MAX_UPLOAD_BYTES", str(1024 * 1024 * 1024)))
        self.max_zip_member_bytes = int(os.environ.get("CC_MAX_ZIP_MEMBER_BYTES", str(500 * 1024 * 1024)))
        self.max_zip_total_bytes = int(os.environ.get("CC_MAX_ZIP_TOTAL_BYTES", str(1024 * 1024 * 1024)))
        self.max_zip_entries = int(os.environ.get("CC_MAX_ZIP_ENTRIES", "10000"))
        self.git_sha = os.environ.get("CC_GIT_SHA", "unknown")
        self.build_date = os.environ.get("CC_BUILD_DATE", "unknown")

    def _load_or_create_secret(self) -> str:
        key_path = self.data_dir / "secret.key"
        if key_path.exists():
            existing = key_path.read_text().strip()
            if existing:
                return existing
        secret = secrets.token_urlsafe(48)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(secret)
        key_path.chmod(0o600)
        return secret

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
