from __future__ import annotations
import os
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
        else:
            self.secret_key = os.environ.get("CC_SECRET_KEY", "dev-secret-change-me")
        self.site_title = os.environ.get("CC_SITE_TITLE", "My Catalogue")
        self.site_author = os.environ.get("CC_SITE_AUTHOR", "")
        self.static_dir = Path(os.environ.get("CC_STATIC_DIR", str(Path(__file__).resolve().parents[3] / "web" / "dist")))
        self.cookie_secure = os.environ.get("CC_COOKIE_SECURE", "true").lower() not in ("0", "false", "no")
        self.max_upload_bytes = int(os.environ.get("CC_MAX_UPLOAD_BYTES", str(1024 * 1024 * 1024)))
        self.max_zip_member_bytes = int(os.environ.get("CC_MAX_ZIP_MEMBER_BYTES", str(500 * 1024 * 1024)))
        self.max_zip_total_bytes = int(os.environ.get("CC_MAX_ZIP_TOTAL_BYTES", str(1024 * 1024 * 1024)))

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
