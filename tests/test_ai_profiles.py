import copy
import importlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "UmiOCR-data"
sys.path[:0] = [str(DATA), str(DATA / "site-packages"), str(DATA / "py_src/imports"), str(DATA / "plugins")]
profiles = importlib.import_module("AIOCR.profile_store")
service = importlib.import_module("AIOCR.config_service")
ai = importlib.import_module("AIOCR.ai_ocr")


def profile(id="one", **kwargs):
    result = dict(id=id, name="工作配置", provider="custom_openai", enabled=True,
                  api_base="https://example.invalid/proxy/v1", api_key="fake-key", model="custom-vision",
                  timeout=None, proxy_url=None)
    result.update(kwargs)
    return result


def store(*items, active="one"):
    return dict(version=1, activeId=active, profiles=list(items), installedBuiltins=["yaoji"])


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None):
        self.calls.append((url, headers))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, tuple):
            return dict(status_code=value[0], text=value[1])
        return dict(status_code=200, text=json.dumps(value))


class ProfileTests(unittest.TestCase):
    def test_migration_imports_current_and_configured_not_builtin_defaults(self):
        from AIOCR.ai_ocr_config import globalOptions
        old = {k: v.get("default") for k, v in globalOptions.items() if isinstance(v, dict) and "default" in v}
        old.update(a_provider="custom_openai", custom_openai_api_key="old-key", custom_openai_model="vision", ollama_model="local-vision")
        migrated = profiles.migrate_store(old)
        self.assertEqual(next(p for p in migrated["profiles"] if p["id"] == migrated["activeId"])["provider"], "yaoji")
        self.assertEqual({p["provider"] for p in migrated["profiles"]}, {"yaoji", "custom_openai", "ollama"})
        self.assertEqual(next(p for p in migrated["profiles"] if p["provider"] == "custom_openai")["api_key"], "old-key")
        old["a_profiles"] = json.dumps(migrated)
        self.assertEqual(profiles.migrate_store(old), migrated)

    def test_builtin_reuses_existing_credentials_and_id_and_sets_default_once(self):
        original = dict(version=1, activeId="other", profiles=[profile("other"), profile("work", api_base=profiles.BUILTIN_BASE, api_key="saved-secret", model="saved-model")])
        migrated = profiles.migrate_store({"a_profiles": original})
        self.assertEqual(migrated["activeId"], "work")
        work = next(p for p in migrated["profiles"] if p["id"] == "work")
        self.assertEqual(work["provider"], "yaoji")
        self.assertEqual(work["api_key"], "saved-secret")
        self.assertEqual(work["model"], "saved-model")
        self.assertEqual(original["profiles"][1]["provider"], "custom_openai")
        migrated["activeId"] = "other"
        self.assertEqual(profiles.migrate_store({"a_profiles": migrated}), migrated)
        resolved, _ = profiles.resolve_config({"a_profiles": migrated}, {"a_l_provider": "custom_openai", "a_l_profile": "work"})
        self.assertEqual(resolved["yaoji_model"], "saved-model")

    def test_fresh_builtin_default_has_no_embedded_key_and_supports_models(self):
        migrated = profiles.migrate_store({})
        self.assertEqual(len(migrated["profiles"]), 1)
        item = migrated["profiles"][0]
        self.assertEqual(item["provider"], "yaoji")
        self.assertEqual(item["name"], profiles.BUILTIN_NAME)
        self.assertEqual(item["api_key"], "")
        client = FakeClient({"data": [{"id": "private-vision"}]})
        item.update(api_key="fake", model="private-vision")
        self.assertEqual(service.list_models(item, client), ["private-vision"])
        self.assertEqual(client.calls[0][0], profiles.BUILTIN_BASE + "/models")
        provider = ai.ProviderFactory.create_provider("yaoji", "fake", model="private-vision")
        self.assertEqual(provider.api_base, profiles.BUILTIN_BASE)

    def test_explicit_empty_store_does_not_reimport_deleted_profiles(self):
        empty = store(active="")
        self.assertEqual(profiles.migrate_store({"a_profiles": json.dumps(empty), "openai_api_key": "old"}), empty)

    def test_corrupt_and_future_store_fail_without_overwrite(self):
        for raw in ("broken", {"version": 2, "profiles": []}, {"version": 1, "profiles": [None]}, store(profile(), profile())):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                profiles.migrate_store({"a_profiles": raw})

    def test_two_profiles_same_provider_and_override_do_not_mutate_global(self):
        config = {"a_profiles": store(profile(), profile("two", api_key="second-key", model="manual-model")), "a_timeout": 30}
        original = copy.deepcopy(config)
        override, _ = profiles.resolve_config(config, {"a_l_profile": "two"})
        default, _ = profiles.resolve_config(config, {})
        self.assertEqual(override["custom_openai_model"], "manual-model")
        self.assertEqual(default["custom_openai_model"], "custom-vision")
        self.assertEqual(config, original)

    def test_invalid_override_falls_back_with_warning_but_missing_default_fails(self):
        config = {"a_profiles": store(profile())}
        resolved, warning = profiles.resolve_config(config, {"a_l_profile": "deleted"})
        self.assertEqual(resolved["custom_openai_model"], "custom-vision")
        self.assertTrue(warning)
        config["a_profiles"]["profiles"][0]["enabled"] = False
        with self.assertRaisesRegex(ValueError, "默认配置"):
            profiles.resolve_config(config, {})

    def test_page_override_works_without_global_default_and_legacy_is_supported(self):
        config = {"a_profiles": store(profile(), active="")}
        resolved, _ = profiles.resolve_config(config, {"a_l_profile": "one"})
        self.assertEqual(resolved["a_provider"], "custom_openai")
        resolved, _ = profiles.resolve_config(config, {"a_l_provider": "custom_openai"})
        self.assertEqual(resolved["custom_openai_model"], "custom-vision")

    def test_advanced_overrides_inherit_and_can_disable_proxy(self):
        config = {"a_profiles": store(profile(timeout=55, proxy_url="")), "a_timeout": 30, "z_proxy_url": "http://proxy.invalid"}
        resolved, _ = profiles.resolve_config(config, {})
        self.assertEqual(resolved["a_timeout"], 55)
        self.assertEqual(resolved["z_proxy_url"], "")
        config["a_profiles"]["profiles"][0].update(timeout=None, proxy_url=None)
        resolved, _ = profiles.resolve_config(config, {})
        self.assertEqual(resolved["a_timeout"], 30)
        self.assertEqual(resolved["z_proxy_url"], "http://proxy.invalid")

    def test_saved_snapshot_survives_edits_and_page_interleaving(self):
        config = {"a_profiles": store(profile(), profile("two", model="second"))}
        api = ai.Api(config)
        first = api.snapshotConfig({"a_l_profile": "one"})
        second = api.snapshotConfig({"a_l_profile": "two"})
        api._base_global_config["a_profiles"]["profiles"][0]["model"] = "edited"
        try:
            self.assertEqual(api.start({"_ai_config_snapshot": first}), "")
            self.assertEqual(api.provider.model, "custom-vision")
            self.assertEqual(api.start({"_ai_config_snapshot": second}), "")
            self.assertEqual(api.provider.model, "second")
            self.assertEqual(api.start({"_ai_config_snapshot": first}), "")
            self.assertEqual(api.provider.model, "custom-vision")
            self.assertEqual(config["a_profiles"]["profiles"][0]["model"], "custom-vision")
        finally:
            api.stop()

    def test_manual_model_and_local_without_key(self):
        self.assertEqual(profiles.validate_profile(profile(model="my-private-model"))["model"], "my-private-model")
        for provider in ("ollama", "lmstudio", "llamacpp"):
            with self.subTest(provider=provider):
                self.assertEqual(profiles.validate_profile(profile(provider=provider, api_key=""))["api_key"], "")

    def test_queue_freezes_at_submission_and_new_queues_receive_saved_changes(self):
        from py_src.mission.mission_ocr import MissionOCR
        from py_src.mission.mission import Mission
        manager = type(MissionOCR)()
        original = {"a_profiles": store(profile())}
        manager._apiKey = "AIOCR"
        manager._api = ai.Api(original)
        manager._aiConfig = copy.deepcopy(original)
        first = {"argd": {}}
        second = {"argd": {}}
        with patch.object(Mission, "addMissionList", return_value="queued"):
            manager.addMissionList(first, [{"bytes": b"image"}])
            changed = {"ocr.AIOCR.a_profiles": store(profile(model="new-model"))}
            manager.updateAiConfig(changed)
            manager.addMissionList(second, [{"bytes": b"image"}])
        self.assertEqual(first["_aiConfigSnapshot"]["custom_openai_model"], "custom-vision")
        self.assertEqual(second["_aiConfigSnapshot"]["custom_openai_model"], "new-model")
        self.assertEqual(manager._api._base_global_config, original)

    def test_bad_address_timeout_and_missing_fields_are_rejected(self):
        for kwargs in ({"api_base": "ftp://invalid"}, {"api_base": "https://user:password@invalid"}, {"api_base": "https://invalid?key=secret"}, {"timeout": 121}, {"model": ""}, {"api_key": ""}, {"name": ""}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                profiles.validate_profile(profile(**kwargs))

    def test_document_pages_keep_the_document_submission_snapshot(self):
        from py_src.mission.mission_ocr import MissionOCR
        from py_src.mission.mission import Mission
        from py_src.mission import mission_doc
        manager = type(MissionOCR)()
        original = {"a_profiles": store(profile())}
        manager._apiKey = "AIOCR"
        manager._api = ai.Api(original)
        manager._aiConfig = original
        document = type(mission_doc.MissionDOC)()
        info = {"argd": {"doc.extractionMode": "fullPage"}}
        with patch.object(mission_doc, "MissionOCR", manager), patch.object(mission_doc.fitz, "open", return_value=SimpleNamespace(is_encrypted=False, page_count=2)), patch.object(Mission, "addMissionList", return_value="queued"):
            document.addMission(info, "example.pdf")
            manager.updateAiConfig({"ocr.AIOCR.a_profiles": store(profile(model="edited-after-submission"))})
            page = {"argd": {k: v for k, v in info["argd"].items() if k.startswith("ocr.")}}
            manager.addMissionList(page, [{"bytes": b"image"}])
        self.assertEqual(page["_aiConfigSnapshot"]["custom_openai_model"], "custom-vision")


class ModelListTests(unittest.TestCase):
    def test_model_metadata_uses_only_explicit_input_declarations(self):
        items = [
            {"id": "declared", "architecture": {"input_modalities": ["text", "image"]}},
            {"id": "unknown-vision-vl", "output_modalities": ["image"]},
            {"id": "bool", "supports_vision": True},
            {"id": "string", "supports_vision": "true"},
            {"id": "caps", "capabilities": {"image_input": True}},
            {"id": "declared", "architecture": {"input_modalities": ["text"]}},
        ]
        result = service.list_models(profile(), FakeClient({"data": items}), with_info=True)
        self.assertEqual(len(result["models"]), 5)
        for name in ("declared", "bool", "caps"):
            self.assertTrue(result["modelInfo"][name]["imageDeclared"])
        for name in ("unknown-vision-vl", "string"):
            self.assertFalse(result["modelInfo"][name]["imageDeclared"])

    def test_gemini_generation_method_is_not_an_image_declaration(self):
        result = service.list_models(profile(provider="gemini"), FakeClient({"models": [{"name": "models/gemini-test", "supportedGenerationMethods": ["generateContent"]}]}), with_info=True)
        self.assertFalse(result["modelInfo"]["gemini-test"]["imageDeclared"])

    def test_evidence_is_preserved_for_models_but_invalidated_for_credentials_or_endpoint(self):
        original = profile()
        original["modelEvidence"] = {"context": profiles.evidence_context(original), "models": {"custom-vision": {"imageDeclared": True, "ocrPassed": True, "arbitrary": "drop"}}}
        validated = profiles.validate_profile(original)
        self.assertEqual(validated["modelEvidence"]["models"]["custom-vision"], {"imageDeclared": True, "ocrPassed": True})
        self.assertIn("modelEvidence", profiles.validate_profile(dict(original, model="another")))
        for changes in ({"api_key": "changed"}, {"api_base": "https://another.invalid/v1"}, {"provider": "openai"}):
            with self.subTest(changes=changes):
                self.assertNotIn("modelEvidence", profiles.validate_profile(dict(original, **changes)))
        self.assertNotIn("fake-key", profiles.evidence_context(original))

    def test_ocr_badge_requires_expected_image_text(self):
        for text in ("unrelated response", "", "I cannot view images"):
            with self.subTest(text=text), patch.object(ai.Api, "runBytes", return_value={"code": 100, "data": [{"text": text}]}):
                result = service.execute("test", profile())
            self.assertFalse(result["ok"])
            self.assertFalse(result["ocrPassed"])
            self.assertEqual(result["model"], "custom-vision")
        with patch.object(ai.Api, "runBytes", return_value={"code": 100, "data": [{"text": "umi ocr test: 123"}]}):
            result = service.execute("test", profile())
        self.assertTrue(result["ocrPassed"])
        self.assertEqual(result["context"], profiles.evidence_context(profile()))

    def test_compatible_models_keep_prefix_and_full_ids_deduplicate(self):
        client = FakeClient({"data": [{"id": "vendor/custom-vision"}, {"id": "text-only"}, {"id": "vendor/custom-vision"}, {}, "bad"]})
        models = service.list_models(profile(api_key="first;second\nthird"), client)
        self.assertEqual(models, ["text-only", "vendor/custom-vision"])
        self.assertEqual(client.calls, [("https://example.invalid/proxy/v1/models", {"Authorization": "Bearer first"})])

    def test_url_join_never_duplicates_version_or_completion_suffix(self):
        for suffix in ("", "/", "/models", "/chat/completions", "/responses"):
            self.assertEqual(service.models_url("https://host.invalid/prefix/v1" + suffix, "custom_openai"), "https://host.invalid/prefix/v1/models")

    def test_gemini_paginates_and_strips_only_resource_prefix(self):
        client = FakeClient({"models": [{"name": "models/custom-vision"}], "nextPageToken": "a+b"}, {"models": [{"name": "models/other"}, {"name": "models/custom-vision"}]})
        models = service.list_models(profile(provider="gemini", api_base="https://google.invalid/v1beta"), client)
        self.assertEqual(models, ["custom-vision", "other"])
        self.assertTrue(client.calls[1][0].endswith("/models?pageToken=a%2Bb"))
        self.assertEqual(client.calls[0][1], {"x-goog-api-key": "fake-key"})

    def test_ollama_lists_models_without_key(self):
        client = FakeClient({"models": [{"name": "local-vl:latest"}]})
        self.assertEqual(service.list_models(profile(provider="ollama", api_key="", api_base="http://localhost:11434/api"), client), ["local-vl:latest"])
        self.assertEqual(client.calls[0][0], "http://localhost:11434/api/tags")

    def test_empty_list_is_not_an_error(self):
        self.assertEqual(service.list_models(profile(), FakeClient({"data": []})), [])

    def test_http_bad_json_and_wrong_shape_errors_are_actionable(self):
        for response, expected in (((401, "secret"), "密钥"), ((403, ""), "权限"), ((404, ""), "手动"), ((429, ""), "稍后"), ((200, "<html>"), "JSON"), ({"wrong": []}, "格式")):
            with self.subTest(response=response), self.assertRaisesRegex(ValueError, expected):
                service.list_models(profile(), FakeClient(response))

    def test_repeated_pagination_token_is_rejected(self):
        client = FakeClient(*[{"models": [], "nextPageToken": "same"}] * 2)
        with self.assertRaisesRegex(ValueError, "分页"):
            service.list_models(profile(provider="gemini"), client)

    def test_timeout_redacts_all_pool_keys_and_proxy_credentials(self):
        draft = profile(api_key="first-secret;second-secret")
        with patch.object(service, "list_models", side_effect=TimeoutError("first-secret second-secret https://user:pass@proxy.invalid?key=third")):
            result = service.execute("models", draft)
        self.assertFalse(result["ok"])
        for forbidden in ("first-secret", "second-secret", "user:pass", "third"):
            self.assertNotIn(forbidden, result["error"])

    def test_network_action_allows_unnamed_draft(self):
        with patch.object(service, "list_models", return_value=["manual"]):
            self.assertTrue(service.execute("models", profile(name=""))["ok"])

    def test_real_recognition_probe_uses_selected_model_and_image(self):
        observed = {}
        def recognize(api, image):
            observed.update(model=api.provider.model, image=image, key=api.provider.api_key, timeout=api.http_client.timeout)
            return {"code": 100, "data": [{"text": "UMI OCR TEST 123"}]}
        with patch.object(ai.Api, "runBytes", recognize):
            result = service.test_connection(profile(model="custom-model", enabled=False, timeout=45))
        self.assertEqual(result["text"], "UMI OCR TEST 123")
        self.assertEqual(observed["model"], "custom-model")
        self.assertEqual(observed["key"], "fake-key")
        self.assertEqual(observed["timeout"], 45)
        self.assertTrue(observed["image"].startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
