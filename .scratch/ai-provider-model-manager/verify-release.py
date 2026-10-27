"""Read-only release checks; credentials stay in memory and are never printed."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "UmiOCR-data/site-packages")]
from PySide2.QtCore import QSettings

version_data = json.loads((ROOT / "UmiOCR-data/about.json").read_text(encoding="utf-8-sig"))["version"]
version = ".".join(str(version_data[k]) for k in ("major", "minor", "patch"))
artifact = ROOT / "dist" / ("Umi-OCR-Team-Setup_" + version + ".exe")
generated = ROOT / "installer/generated/team.settings"
log_path = ROOT / "logs/inno-team-installer-build.log"
sensitive = re.compile(r"api.?key|token|secret|password|credential|authorization", re.I)
allowed = re.compile(r"(api_base|base_url|endpoint|address|model|url)$", re.I)

payload = generated.read_bytes()
keys = [line.split("=", 1)[0].strip() for line in payload.decode("utf-8-sig").splitlines() if "=" in line]
assert keys and all(allowed.search(k) and not sensitive.search(k) for k in keys), "Unexpected generated settings keys"
assert not any("a_profiles" in k for k in keys), "Profile collection in generated settings"

secrets = set()


def collect(value, secret=False):
    if isinstance(value, dict):
        for key, child in value.items():
            collect(child, bool(sensitive.search(str(key))))
    elif isinstance(value, (list, tuple)):
        for child in value:
            collect(child, secret)
    elif isinstance(value, str):
        if secret and value.strip():
            secrets.add(value)
            secrets.update(part.strip() for part in re.split(r"[,;\r\n]+", value) if part.strip())
        elif not secret and value.lstrip().startswith(("{", "[")):
            try:
                collect(json.loads(value))
            except (ValueError, TypeError):
                pass


for filename in (".settings", ".pre_settings"):
    settings_path = ROOT / "UmiOCR-data" / filename
    if not settings_path.exists():
        continue
    settings = QSettings(str(settings_path), QSettings.IniFormat)
    settings.setIniCodec("UTF-8")
    for key in settings.allKeys():
        collect(settings.value(key), bool(sensitive.search(key)))

binary = artifact.read_bytes()
for secret in secrets:
    for encoding in ("utf-8", "utf-16-le"):
        needle = secret.encode(encoding)
        assert needle not in payload, "Credential found in generated settings; value withheld"
        assert needle not in binary, "Credential found in installer; value withheld"

log = log_path.read_text(encoding="utf-8-sig")
required = ["Umi-OCR.exe", "UmiOCR-data/main.py", "installer/generated/team.settings",
            "UmiOCR-data/about.json", "UmiOCR-data/qt_res/qml/Configs/AiProfiles.qml",
            "UmiOCR-data/qt_res/qml/Configs/AiSecretPeek.qml",
            "UmiOCR-data/plugins/AIOCR/profile_store.py",
            "UmiOCR-data/plugins/AIOCR/config_service.py",
            "UmiOCR-data/py_src/plugins_controller/ai_config_connector.py"]
normalized_log = log.replace("\\", "/").lower()
assert all(entry.lower() in normalized_log for entry in required), "Required build input missing in compiler log"
assert not re.search(r"UmiOCR-data/(?:\.settings|\.pre_settings|logs/|temp_doc/)", normalized_log, re.I), "User data included in compiler log"
assert len(binary) > 0, "Empty installer"

result = {
    "version": version,
    "artifact": str(artifact),
    "bytes": len(binary),
    "sha256": hashlib.sha256(binary).hexdigest(),
    "generatedSettingsAllowedKeys": len(keys),
    "credentialComparison": "passed (generated settings and raw installer bytes, UTF-8/UTF-16LE)",
    "compilerInputCheck": "passed",
    "requiredInputs": required,
    "validationLimit": "Compiler inputs and raw bytes checked; installer was not installed or extracted.",
}
report = Path(__file__).with_name("release-" + version + ".json")
report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
