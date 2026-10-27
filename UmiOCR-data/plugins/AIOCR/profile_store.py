"""Versioned AI profiles and per-task resolution, independent of Qt."""
import copy
import json
import re
import uuid
import hashlib
from urllib.parse import urlsplit

VERSION = 1
LOCAL_PROVIDERS = {"ollama", "lmstudio", "llamacpp"}
BUILTIN_PROVIDER = "yaoji"
BUILTIN_NAME = "姚记「梅花工作室」"
BUILTIN_BASE = "https://llm-proxy.yuwan-game.com/v1"


def evidence_context(profile):
    # Bind evidence to an endpoint and credential pool, never to a display name.
    identity = [str(profile.get(key, "") or "").strip() for key in ("provider", "api_base", "api_key")]
    identity[1] = identity[1].rstrip("/")
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()


def install_builtin(store):
    """Install the new default once, preserving credentials, IDs and later choices."""
    if BUILTIN_PROVIDER in store.get("installedBuiltins", []):
        return store
    candidates = []
    for item in store["profiles"]:
        same_address = str(item.get("api_base", "")).rstrip("/") == BUILTIN_BASE
        if item["provider"] == BUILTIN_PROVIDER or (same_address and item["provider"] in ("openai", "custom_openai")):
            if item["provider"] != BUILTIN_PROVIDER:
                item["legacyProvider"] = item["provider"]
                item["provider"] = BUILTIN_PROVIDER
            if item.get("enabled", True):
                candidates.append(item)
    active = next((p for p in candidates if p["id"] == store.get("activeId")), None)
    active = active or next((p for p in candidates if p.get("api_key")), None)
    active = active or next(iter(candidates), None)
    if active is None:
        active = dict(id="builtin-yaoji", name=BUILTIN_NAME, provider=BUILTIN_PROVIDER,
                      enabled=True, api_base=BUILTIN_BASE, api_key="", model="",
                      timeout=None, proxy_url=None)
        # A user may already have used this ID for a disabled profile.
        if any(p["id"] == active["id"] for p in store["profiles"]):
            active["id"] = str(uuid.uuid4())
        store["profiles"].insert(0, active)
    store["activeId"] = active["id"]
    store["installedBuiltins"] = list(store.get("installedBuiltins", [])) + [BUILTIN_PROVIDER]
    return store


def decode_store(value):
    if isinstance(value, str):
        if not value:
            return None
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            raise ValueError("AI 配置无法读取，请恢复配置文件备份。")
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("version") != VERSION or not isinstance(value.get("profiles"), list):
        raise ValueError("AI 配置版本不受支持，请使用兼容版本的软件。")
    ids = set()
    for profile in value["profiles"]:
        if not isinstance(profile, dict) or not isinstance(profile.get("id"), str) or not profile["id"] or profile["id"] in ids or not isinstance(profile.get("provider"), str):
            raise ValueError("AI 配置内容损坏，请恢复配置文件备份。")
        ids.add(profile["id"])
    return copy.deepcopy(value)


def provider_catalog():
    from .ai_ocr_config import PROVIDER_CONFIGS, globalOptions
    concise = {"custom_openai": "OpenAI 兼容（自定义）", "alibaba": "阿里云百炼", "siliconflow": "硅基流动"}
    return [dict(id=key, name=concise.get(key, name), api_base=PROVIDER_CONFIGS[key]["api_base"],
                 model=globalOptions.get(key + "_model", {}).get("default", ""),
                 local=key in LOCAL_PROVIDERS)
            for key, name in globalOptions["a_provider"]["optionsList"]]


def migrate_store(config):
    existing = decode_store(config.get("a_profiles"))
    if existing is not None:
        return install_builtin(existing)
    from .ai_ocr_config import globalOptions
    current = config.get("a_provider") or config.get("provider") or BUILTIN_PROVIDER
    profiles = []
    active_id = ""
    for preset in provider_catalog():
        provider = preset["id"]
        key = str(config.get(provider + "_api_key", "") or "")
        model = str(config.get(provider + "_model", preset["model"]) or "")
        address = str(config.get(provider + "_api_base", preset["api_base"]) or preset["api_base"])
        default_model = globalOptions.get(provider + "_model", {}).get("default", "")
        configured = bool(key.strip() or (model and model != default_model) or address != preset["api_base"])
        if provider != current and not configured:
            continue
        profile_id = "legacy-" + provider
        profiles.append(dict(id=profile_id, name=preset["name"], provider=provider,
                             enabled=True, api_base=address, api_key=key, model=model,
                             timeout=None, proxy_url=None))
        if provider == current:
            active_id = profile_id
    return install_builtin(dict(version=VERSION, activeId=active_id, profiles=profiles))


def validate_profile(profile, require_model=True):
    profile = copy.deepcopy(profile)
    catalog = {p["id"]: p for p in provider_catalog()}
    provider = profile.get("provider")
    if provider not in catalog:
        raise ValueError("请选择有效的服务商。")
    for key in ("name", "api_base", "model"):
        profile[key] = str(profile.get(key, "") or "").strip()
    if not profile["name"]:
        raise ValueError("请填写配置名称。")
    profile["api_base"] = profile["api_base"] or catalog[provider]["api_base"]
    try:
        url = urlsplit(profile["api_base"])
        valid_url = url.scheme in ("http", "https") and bool(url.hostname) and not url.username and not url.password and not url.query and not url.fragment
        url.port
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ValueError("API 地址须为有效的 HTTP(S) 基础地址，不含账号、查询参数或片段。")
    if provider not in LOCAL_PROVIDERS and not str(profile.get("api_key", "")).strip():
        raise ValueError("请填写 API 密钥。")
    if require_model and not profile["model"]:
        raise ValueError("请选择或填写模型名称。")
    timeout = profile.get("timeout")
    if timeout is not None:
        try:
            timeout = int(timeout)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("请求超时须为 5–120 秒。")
        if not 5 <= timeout <= 120:
            raise ValueError("请求超时须为 5–120 秒。")
        profile["timeout"] = timeout
    profile["id"] = str(profile.get("id") or uuid.uuid4())
    profile["enabled"] = bool(profile.get("enabled", True))
    evidence = profile.get("modelEvidence")
    if evidence is not None:
        if not isinstance(evidence, dict) or evidence.get("context") != evidence_context(profile) or not isinstance(evidence.get("models"), dict):
            profile.pop("modelEvidence", None)
        else:
            clean = {}
            for model, info in evidence["models"].items():
                if not isinstance(model, str) or not isinstance(info, dict):
                    continue
                clean[model] = {key: info[key] for key in ("imageDeclared", "ocrPassed") if type(info.get(key)) is bool}
            profile["modelEvidence"] = {"context": evidence["context"], "models": clean}
    return profile


def resolve_config(config, local):
    """Return an isolated effective config. Never mutate the shared defaults."""
    result = copy.deepcopy(config)
    store = migrate_store(config)
    profiles = {p["id"]: p for p in store["profiles"] if p.get("enabled", True)}
    selected = local.get("a_l_profile", "")
    # Legacy per-page provider choice only applies before that page is migrated.
    if not selected and local.get("a_l_provider"):
        selected = next((p["id"] for p in profiles.values()
                         if p["provider"] == local["a_l_provider"] or p.get("legacyProvider") == local["a_l_provider"]), "")
    warning = ""
    if selected and selected not in profiles:
        warning = "页面所选 AI 配置已删除或禁用，已跟随全局默认。"
    profile = profiles.get(selected) or profiles.get(store.get("activeId"))
    if profile is None:
        raise ValueError("请在 AI 模型配置中选择一套启用的默认配置。")
    provider = profile["provider"]
    result.update(a_provider=provider, provider=provider)
    for suffix in ("api_key", "api_base", "model"):
        result[provider + "_" + suffix] = profile.get(suffix, "")
    if profile.get("timeout") is not None:
        result["a_timeout"] = profile["timeout"]
    if profile.get("proxy_url") is not None:
        result["z_proxy_url"] = profile["proxy_url"]
    return result, warning


def redact(message, profile):
    """Scrub credentials, including key pools and URLs echoed by upstream errors."""
    text = str(message)
    secrets = [profile.get("api_key", "")]
    secrets += re.split(r"[,;\n]", str(profile.get("api_key", "")))
    for secret in sorted(set(str(s).strip() for s in secrets if s), key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[密钥已隐藏]")
    text = re.sub(r"(?i)([?&](?:key|api_key|token)=)[^\s&]+", r"\1[已隐藏]", text)
    text = re.sub(r"(https?://)[^/\s@]+@", r"\1[已隐藏]@", text)
    return text[:1500]
