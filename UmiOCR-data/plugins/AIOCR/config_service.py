"""Network actions for the configuration editor; called on a worker thread."""
import json
import time
import re
from io import BytesIO
from urllib.parse import urlencode, urlsplit, urlunsplit

from .profile_store import validate_profile, redact, evidence_context, BUILTIN_PROVIDER


def models_url(base, provider):
    parts = urlsplit(base.rstrip("/"))
    path = parts.path.rstrip("/")
    # Accept pasted completion URLs without losing a reverse proxy's prefix.
    for suffix in ("/chat/completions", "/responses", "/models", "/tags"):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break
    if provider == "ollama":
        path += "/tags" if path.endswith("/api") else "/api/tags"
    else:
        path += "/models"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def declares_image_input(item):
    """Use explicit input capabilities only; names and output modalities are not evidence."""
    architecture = item.get("architecture")
    capabilities = item.get("capabilities")
    modalities = [item.get("input_modalities"), item.get("supportedInputModalities")]
    if isinstance(architecture, dict):
        modalities.append(architecture.get("input_modalities"))
    if isinstance(capabilities, dict):
        if capabilities.get("vision") is True or capabilities.get("image_input") is True:
            return True
        modalities.append(capabilities.get("input_modalities"))
    elif isinstance(capabilities, list) and "vision" in capabilities:
        return True
    if item.get("supports_vision") is True or item.get("supports_image_input") is True:
        return True
    return any(isinstance(values, list) and any(isinstance(v, str) and v.lower() == "image" for v in values) for values in modalities)


def list_models(profile, client=None, with_info=False):
    from .ai_ocr import HTTPClient, BaseProvider
    profile = validate_profile(profile, require_model=False)
    provider = profile["provider"]
    if provider in {"mineru", "paddle", "paddle_vl_16", "pp_structure_v3", "glm_ocr"}:
        raise ValueError("此专用 OCR 接口不提供模型列表，请使用预设模型或手动填写。")
    client = client or HTTPClient(profile.get("timeout") or 30, profile.get("proxy_url") or "")
    keys = BaseProvider._split_api_keys(profile.get("api_key", ""))
    headers = {"Authorization": "Bearer " + keys[0]} if keys else {}
    if provider == "gemini":
        headers = {"x-goog-api-key": keys[0]} if keys else {}
    url = models_url(profile["api_base"], provider)
    models, seen, page_tokens, info = [], set(), set(), {}
    while True:
        response = client.get(url, headers=headers)
        status = response["status_code"]
        if status != 200:
            messages = {401: "密钥无效或已过期", 403: "没有读取模型列表的权限", 404: "接口不提供模型列表，请检查地址或手动填写", 429: "请求过于频繁，请稍后重试"}
            raise ValueError("拉取模型失败（HTTP %s）：%s。" % (status, messages.get(status, "服务商返回错误")))
        try:
            data = json.loads(response["text"])
        except (TypeError, ValueError):
            raise ValueError("服务商返回的内容不是 JSON，请检查 API 地址或手动填写模型。")
        field = "models" if provider in ("gemini", "ollama") else "data"
        if not isinstance(data, dict) or not isinstance(data.get(field), list):
            raise ValueError("模型列表格式不受支持，可以手动填写模型。")
        for item in data[field]:
            if not isinstance(item, dict):
                continue
            model = item.get("name") if provider in ("gemini", "ollama") else item.get("id")
            if provider == "gemini" and isinstance(model, str) and model.startswith("models/"):
                model = model[len("models/"):]
            if isinstance(model, str) and model.strip():
                if model not in seen:
                    seen.add(model)
                    models.append(model)
                declared = declares_image_input(item) or info.get(model, {}).get("imageDeclared", False)
                info[model] = {"imageDeclared": declared}
        token = data.get("nextPageToken") if provider == "gemini" else None
        if not token:
            break
        if token in page_tokens or len(page_tokens) >= 100:
            raise ValueError("模型列表分页异常，请稍后重试。")
        page_tokens.add(token)
        url = models_url(profile["api_base"], provider) + "?" + urlencode({"pageToken": token})
    models.sort(key=str.casefold)
    return {"models": models, "modelInfo": info} if with_info else models


def test_connection(profile):
    from PIL import Image, ImageDraw
    from .ai_ocr import Api
    profile = validate_profile(profile)
    profile["enabled"] = True  # A disabled saved profile can still be tested explicitly.
    provider = profile["provider"]
    config = {"a_provider": provider, "a_timeout": profile.get("timeout") or 30,
              "z_proxy_url": profile.get("proxy_url") or "",
              "a_profiles": {"version": 1, "activeId": profile["id"], "profiles": [profile],
                             "installedBuiltins": [BUILTIN_PROVIDER]}}
    api = Api(config)
    try:
        error = api.start({"dual_strategy": "ai_high_precision_text_only", "output_format": "text_only", "language": "en"})
        if error:
            raise ValueError(error)
        image = Image.new("RGB", (160, 40), "white")
        ImageDraw.Draw(image).text((8, 14), "UMI OCR TEST 123", fill="black")
        image = image.resize((480, 120), Image.NEAREST)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        result = api.runBytes(buffer.getvalue())
        if result.get("code") != 100:
            if result.get("code") == 101:
                raise ValueError("接口已响应，但未识别到测试图片文字，请确认模型支持图片识别。")
            raise ValueError(result.get("data", "识别请求失败"))
        text = "\n".join(str(block.get("text", "")) for block in result.get("data", []))
        if "umiocrtest123" not in re.sub(r"[^a-z0-9]", "", text.lower()):
            raise ValueError("接口已响应，但测试图片文字与预期不符，OCR 测试未通过。")
        return {"text": text[:500], "ocrPassed": True}
    finally:
        api.stop()


def execute(action, profile):
    started = time.monotonic()
    try:
        profile = dict(profile)
        profile["name"] = profile.get("name") or "未命名配置"
        result = list_models(profile, with_info=True) if action == "models" else test_connection(profile)
        if isinstance(result, list):
            result = {"models": result}
        if "text" in result:
            result["text"] = redact(result["text"], profile)
        result["ok"] = True
    except Exception as error:
        message = redact(error, profile)
        if isinstance(error, TimeoutError) or "timed out" in message.lower():
            message = "请求超时，请检查 API 地址、网络或代理后重试。\n" + message
        result = {"ok": False, "error": message}
    result["context"] = evidence_context(profile)
    if action == "test":
        result["model"] = str(profile.get("model", "")).strip()
        result["ocrPassed"] = bool(result.get("ok") and result.get("ocrPassed"))
    result["elapsed"] = round(time.monotonic() - started, 2)
    return result
