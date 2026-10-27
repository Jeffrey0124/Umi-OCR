"""Qt 5.15 integration tests. Run with the bundled Python/PySide2 runtime.

All QSettings writes go to temporary directories, never the user's .settings.
Set AI_UI_CAPTURE_DIR to save the light/dark/compact rendered previews.
"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("QT_QPA_PLATFORM", "windows" if sys.platform == "win32" else "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "UmiOCR-data"
sys.path[:0] = [str(DATA), str(DATA / "site-packages"), str(DATA / "py_src/imports"), str(DATA / "plugins")]

from PySide2.QtCore import QObject, QUrl, QCoreApplication, QEvent, QEventLoop, QTimer, qInstallMessageHandler, QtMsgType, Qt, QPointF, QMetaObject
from PySide2.QtGui import QGuiApplication, QKeyEvent, QMouseEvent
from PySide2.QtQuick import QQuickWindow
from PySide2.QtQml import QQmlApplicationEngine, QQmlExpression, qmlRegisterType
from py_src.plugins_controller.ai_config_connector import AiConfigConnector
from py_src.utils.theme_connector import ThemeConnector
from py_src.event_bus.pubsub_connector import PubSubConnector
from AIOCR.ai_ocr_config import globalOptions, localOptions


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec_()


class AiQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setOrganizationName("UmiOcrProfileTests")
        cls.app.setApplicationName("UmiOcrProfileTests")
        qmlRegisterType(AiConfigConnector, "AiConfigConnector", 1, 0, "AiConfigConnector")
        qmlRegisterType(ThemeConnector, "ThemeConnector", 1, 0, "ThemeConnector")
        qmlRegisterType(PubSubConnector, "PubSubConnector", 1, 0, "PubSubConnector")
        cls.messages = []
        cls.old_handler = qInstallMessageHandler(lambda kind, context, message: cls.messages.append(message) if kind != QtMsgType.QtDebugMsg else None)

    @classmethod
    def tearDownClass(cls):
        qInstallMessageHandler(cls.old_handler)

    def setUp(self):
        self.old_cwd = os.getcwd()
        self.temp = tempfile.TemporaryDirectory(prefix="umi-ai-qml-")
        self.addCleanup(self.cleanup)
        os.chdir(self.temp.name)
        self.messages.clear()
        self.engine = QQmlApplicationEngine()
        options = {"ocr": {"title": "AI 设置", "type": "group", "AIOCR": copy.deepcopy(globalOptions)}}
        options["ocr"]["api"] = {"default": "AIOCR", "optionsList": [["AIOCR", "AI OCR"]]}
        self.engine.rootContext().setContextProperty("testOptions", options)
        self.engine.rootContext().setContextProperty("testLocalOptions", copy.deepcopy(localOptions))
        qml_root = (DATA / "qt_res/qml").as_uri()
        source = '''
import QtQuick 2.15
import QtQuick.Controls 2.15
import "%s/Configs"
import "%s/Themes"
import "%s/MainWindow"
import "%s/EventBus"
import "%s/ApiManager"
ApplicationWindow {
    id: mainWindowRoot
    visible: true; width: 1040; height: 840
    property Theme theme: Theme { Component.onCompleted: manager.switchTheme("Default Dark") }
    property Size_ size_: Size_ {}
    color: theme.bgColor
    Item { id: mainContainer }
    Item {
        id: qmlapp
        property alias globalConfigs: globalConfigs
        property bool enabledEffect: false
        property PubSub pubSub: PubSub {}
        property QtObject msnConnector: QtObject {
            property int active: 0
            property int paused: 0
            property int documents: 0
            property int applies: 0
            property int updates: 0
            function callPy(group, action, args) {
                if(action === "getStatus") return {missionListsLength: active ? {job:1} : {}, pausedMissionListsLength: paused ? {job:1} : {}, documentMissionListsLength: documents ? {doc:2} : {}}
                if(action === "updateAiConfig") { updates++; return }
                if(action === "setApi") { applies++; return "[Success]" }
            }
        }
        property QtObject popup: QtObject {
            property int notifications: 0
            function simple(a,b) { notifications++ }
            function message(a,b,c) {}
            function dialog(a,b,c,d,e) {}
        }
    }
    Configs {
        id: globalConfigs
        objectName: "testConfigs"
        anchors.fill: parent; anchors.margins: 24
        category_: "AiProfileTest"
        configDict: testOptions
        property OcrManager ocrManager: OcrManager { localOptions: ({AIOCR: testLocalOptions}) }
    }
    Configs {
        id: pageConfigs
        visible: false
        category_: "AiProfilePageTest"
        configDict: ({ocr: {title:"页面识别", type:"group", AIOCR:testLocalOptions}})
    }
}''' % (qml_root, qml_root, qml_root, qml_root, qml_root)
        self.engine.loadData(source.encode("utf-8"), QUrl.fromLocalFile(str(Path(self.temp.name) / "Harness.qml")))
        self.assertTrue(self.engine.rootObjects(), "\n".join(self.messages))
        self.window = self.engine.rootObjects()[0]
        wait(80)
        self.panel = self.window.findChild(QObject, "aiProfiles")
        self.assertIsNotNone(self.panel, "\n".join(self.messages))

    def cleanup(self):
        if hasattr(self, "window"):
            self.window.close()
        if hasattr(self, "engine"):
            self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        wait(10)
        os.chdir(self.old_cwd)
        self.temp.cleanup()

    def js(self, code):
        field = self.panel.findChild(QObject, "aiProfileName")
        expression = QQmlExpression(self.engine.contextForObject(field), self.panel, code)
        value = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        if isinstance(value, tuple):
            value = value[0]
        return value.toVariant() if hasattr(value, "toVariant") else value

    def mouse(self, kind, position, button, buttons):
        point = position if isinstance(position, QPointF) else QPointF(position["x"], position["y"])
        QCoreApplication.sendEvent(self.window, QMouseEvent(kind, point, button, buttons, Qt.NoModifier))

    def test_renderer_loads_grouped_settings_without_qml_errors(self):
        self.assertFalse(self.messages, "\n".join(self.messages))
        self.assertEqual(self.js("store.profiles.length"), 1)
        self.assertEqual(self.js("configs.compDict['ocr.AIOCR.openai_api_key'] === undefined"), True)
        self.assertEqual(self.js("configs.compDict['ocr.AIOCR.a_prompt_text_only'] !== undefined"), True)

    def test_selecting_provider_sets_editable_name_even_when_already_selected(self):
        self.js("manager.open(); editor.edit(null,false); nameInput.text='旧名字'; editor.chooseProvider(providers.find(p => p.id === 'openai'))")
        self.assertEqual(self.js("nameInput.text"), "OpenAI")
        self.js("nameInput.text='自定义工作配置'; keyInput.text='fake'; modelInput.text='vision'; editor.save(); editor.edit(store.profiles[1],false)")
        self.assertEqual(self.js("nameInput.text"), "自定义工作配置")
        self.js("editor.chooseProvider(providers.find(p => p.id === 'openai'))")
        self.assertEqual(self.js("nameInput.text"), "OpenAI")
        self.assertEqual(self.js("keyInput.text"), "fake")

    def test_model_evidence_has_distinct_labels_and_persists_on_save(self):
        self.js("manager.open(); editor.edit(null,false); keyInput.text='fake'; modelInput.text='known'; editor.modelsRequest='models'; bridge.finished('models','models',{ok:true,context:bridge.evidenceContext(editor.readDraft()),models:['known','unknown'],modelInfo:{known:{imageDeclared:true}}})")
        self.assertEqual(self.js("editor.modelStatus('known')"), "支持图片（服务商声明）")
        self.assertEqual(self.js("editor.modelStatus('unknown')"), "能力未知／未测试")
        self.js("editor.testRequest='probe'; bridge.finished('probe','test',{ok:true,context:bridge.evidenceContext(editor.readDraft()),model:'known',ocrPassed:true,text:'UMI OCR TEST 123',elapsed:0.1}); modelsPopup.close(); editor.save(); editor.edit(store.profiles[1],false)")
        self.assertIn("OCR 测试通过", self.js("editor.modelStatus('known')"))
        self.assertIn("支持图片（服务商声明）", self.js("editor.modelStatus('known')"))
        self.js("editor.close(); configs.settingsReload()")
        wait(40)
        self.panel = self.window.findChild(QObject, "aiProfiles")
        self.js("manager.open(); editor.edit(store.profiles[1],false)")
        self.assertIn("OCR 测试通过", self.js("editor.modelStatus('known')"))
        self.js("keyInput.text='changed'")
        self.assertEqual(self.js("editor.modelStatus('known')"), "能力未知／未测试")

    def test_draft_evidence_is_cancelled_and_late_test_cannot_mark_new_model(self):
        before = self.js("JSON.stringify(store)")
        self.js("manager.open(); editor.edit(null,false); keyInput.text='fake'; modelInput.text='one'; editor.testRequest='old'; modelInput.text='two'; editor.invalidate(false); bridge.finished('old','test',{ok:true,context:bridge.evidenceContext(editor.readDraft()),model:'one',ocrPassed:true,text:'UMI OCR TEST 123'}); editor.close()")
        self.assertEqual(self.js("JSON.stringify(store)"), before)
        self.assertEqual(self.js("editor.modelStatus('two')"), "能力未知／未测试")

    def test_saved_profile_test_marks_only_matching_endpoint_and_clears_failed_pass(self):
        self.js("manager.open(); listTestProfile=JSON.parse(JSON.stringify(store.profiles[0])); listTestId='saved'; bridge.finished('saved','test',{ok:true,context:bridge.evidenceContext(store.profiles[0]),model:'tested',ocrPassed:true,text:'UMI OCR TEST 123',elapsed:0.1})")
        self.assertTrue(self.js("store.profiles[0].modelEvidence.models.tested.ocrPassed"))
        self.js("listTestProfile=JSON.parse(JSON.stringify(store.profiles[0])); listTestId='failed'; bridge.finished('failed','test',{ok:false,context:bridge.evidenceContext(store.profiles[0]),model:'tested',ocrPassed:false,error:'测试未通过'})")
        self.assertFalse(self.js("store.profiles[0].modelEvidence.models.tested.ocrPassed"))
        self.js("listTestProfile=JSON.parse(JSON.stringify(store.profiles[0])); listTestId='wrong'; bridge.finished('wrong','test',{ok:true,context:'different-endpoint',model:'different',ocrPassed:true,text:'UMI OCR TEST 123'})")
        self.assertTrue(self.js("store.profiles[0].modelEvidence.models.different === undefined"))

    def test_card_exposes_actions_and_uses_only_one_default_marker(self):
        self.js("manager.open()")
        wait(40)
        card = self.js("profileList.itemAtIndex(0)")
        self.assertIsNotNone(card)
        controls = card.findChildren(QObject)
        labels = [item.property("text_") for item in controls if item.property("text_")]
        for label in ("测试连接", "编辑", "复制", "禁用", "删除"):
            self.assertIn(label, labels)
        self.assertNotIn("当前默认", labels)
        self.assertNotIn("更多", labels)
        self.assertIsNone(card.findChild(QObject, "aiSetDefault"))
        default = card.findChild(QObject, "aiSetDefaultContextAction")
        self.assertFalse(default.property("enabled"))

    def test_right_click_default_menu_moves_card_first_without_reordering_other_profiles(self):
        self.js("manager.open(); editor.edit(null,false); keyInput.text='fake'; modelInput.text='vision'; editor.save()")
        wait(40)
        selected = self.js("store.profiles[1].id")
        pos = self.js("profileList.itemAtIndex(1).mapToItem(Overlay.overlay,50,20)")
        self.mouse(QEvent.MouseButtonPress, pos, Qt.RightButton, Qt.RightButton)
        self.mouse(QEvent.MouseButtonRelease, pos, Qt.RightButton, Qt.NoButton)
        wait(30)
        card = self.js("profileList.itemAtIndex(1)")
        menu = card.findChild(QObject, "aiProfileContextMenu")
        self.assertTrue(menu.property("visible"))
        action = card.findChild(QObject, "aiSetDefaultContextAction")
        self.assertTrue(action.property("enabled"))
        action.triggered.emit()
        wait(40)
        self.assertEqual(self.js("store.activeId"), selected)
        self.assertEqual(self.js("profileList.itemAtIndex(0).profileId"), selected)
        self.assertEqual(self.js("store.profiles[1].id"), selected)
        self.js("configs.settingsReload()")
        wait(40)
        self.panel = self.window.findChild(QObject, "aiProfiles")
        self.assertEqual(self.js("orderedProfiles[0].id"), selected)

    def test_left_click_still_opens_edit_and_keyboard_opens_context_menu(self):
        self.js("manager.open(); editor.edit(null,false); keyInput.text='fake'; modelInput.text='vision'; editor.save()")
        wait(40)
        self.js("profileList.itemAtIndex(1).forceActiveFocus()")
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            QCoreApplication.sendEvent(self.window, QKeyEvent(kind, Qt.Key_F10, Qt.ShiftModifier))
        wait(20)
        card = self.js("profileList.itemAtIndex(1)")
        menu = card.findChild(QObject, "aiProfileContextMenu")
        self.assertTrue(menu.property("visible"))
        QMetaObject.invokeMethod(menu, "close", Qt.DirectConnection)
        # The right-button hit area must not intercept the normal edit button.
        controls = card.findChildren(QObject)
        edit = next(item for item in controls if item.property("text_") == "编辑")
        self.engine.rootContext().setContextProperty("testEditButton", edit)
        pos = self.js("testEditButton.mapToItem(Overlay.overlay,testEditButton.width/2,testEditButton.height/2)")
        self.mouse(QEvent.MouseButtonPress, pos, Qt.LeftButton, Qt.LeftButton)
        self.mouse(QEvent.MouseButtonRelease, pos, Qt.LeftButton, Qt.NoButton)
        wait(20)
        self.assertTrue(self.js("editor.opened"))

    def test_secret_eye_reveals_only_while_mouse_or_keyboard_is_held(self):
        self.js("manager.open(); editor.edit(null,false); keyInput.text='fake-private-key'")
        self.window.requestActivate()
        wait(60)
        pos = self.js("secretPeek.mapToItem(Overlay.overlay,secretPeek.width/2,secretPeek.height/2)")
        self.assertTrue(self.js("keyInput.echoMode === TextInput.Password"))
        self.mouse(QEvent.MouseButtonPress, pos, Qt.LeftButton, Qt.LeftButton)
        self.assertTrue(self.js("secretPeek.revealed"))
        self.assertTrue(self.js("keyInput.echoMode === TextInput.Normal"))
        self.mouse(QEvent.MouseButtonRelease, pos, Qt.LeftButton, Qt.NoButton)
        self.assertTrue(self.js("keyInput.echoMode === TextInput.Password"))
        self.js("secretPeek.forceActiveFocus()")
        QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyPress, Qt.Key_Space, Qt.NoModifier))
        self.assertTrue(self.js("secretPeek.revealed"))
        QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyRelease, Qt.Key_Space, Qt.NoModifier))
        self.assertFalse(self.js("secretPeek.revealed"))
        self.assertEqual(self.js("editor.readDraft().api_key"), "fake-private-key")

    def test_secret_eye_cancels_when_focus_or_editor_is_lost(self):
        self.js("manager.open(); editor.edit(null,false); keyInput.text='fake'; secretPeek.forceActiveFocus()")
        self.window.requestActivate()
        wait(40)
        QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyPress, Qt.Key_Space, Qt.NoModifier))
        self.assertTrue(self.js("secretPeek.revealed"))
        self.js("nameInput.forceActiveFocus()")
        self.assertFalse(self.js("secretPeek.revealed"))
        QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyRelease, Qt.Key_Space, Qt.NoModifier))
        self.js("secretPeek.forceActiveFocus()")
        QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyPress, Qt.Key_Space, Qt.NoModifier))
        self.js("editor.close()")
        self.assertFalse(self.js("secretPeek.revealed"))
        QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyRelease, Qt.Key_Space, Qt.NoModifier))

    def test_secret_eye_hides_when_pointer_leaves_and_window_is_hidden(self):
        self.js("manager.open(); editor.edit(null,false); keyInput.text='fake'")
        self.window.requestActivate()
        wait(80)
        pos = self.js("secretPeek.mapToItem(Overlay.overlay,secretPeek.width/2,secretPeek.height/2)")
        outside = self.js("nameInput.mapToItem(Overlay.overlay,10,10)")
        self.mouse(QEvent.MouseButtonPress, pos, Qt.LeftButton, Qt.LeftButton)
        self.assertTrue(self.js("secretPeek.revealed"))
        self.mouse(QEvent.MouseMove, outside, Qt.NoButton, Qt.LeftButton)
        self.assertFalse(self.js("secretPeek.revealed"))
        self.mouse(QEvent.MouseButtonRelease, outside, Qt.LeftButton, Qt.NoButton)
        wait(30)
        pos = self.js("secretPeek.mapToItem(Overlay.overlay,secretPeek.width/2,secretPeek.height/2)")
        self.mouse(QEvent.MouseMove, pos, Qt.NoButton, Qt.NoButton)
        self.mouse(QEvent.MouseButtonPress, pos, Qt.LeftButton, Qt.LeftButton)
        self.assertTrue(self.js("secretPeek.revealed"), self.js("JSON.stringify({pressed:secretPeek.pressed,holding:secretPeek.holding,focused:secretPeek.activeFocus})"))
        self.window.hide()
        wait(30)
        self.assertFalse(self.js("secretPeek.revealed"))
        self.window.show()
        self.window.requestActivate()
        wait(30)
        self.assertFalse(self.js("secretPeek.revealed"))
        self.mouse(QEvent.MouseButtonRelease, pos, Qt.LeftButton, Qt.NoButton)

    def test_cancel_preserves_store_and_save_adds_same_provider_profile(self):
        before = self.js("JSON.stringify(store)")
        self.js("manager.open(); editor.edit(null, false); nameInput.text='取消的草稿'; editor.close()")
        self.assertEqual(self.js("JSON.stringify(store)"), before)
        self.js("editor.edit(null, false); nameInput.text='第三方工作配置'; keyInput.text='fake-secret'; modelInput.text='manual-vision'; editor.save()")
        self.assertEqual(self.js("store.profiles.length"), 2)
        self.assertEqual(self.js("store.profiles[1].model"), "manual-vision")
        self.assertTrue(self.js("!editor.opened"))
        raw = self.js("configs.getValue(key)")
        self.assertEqual(json.loads(raw)["profiles"][1]["api_key"], "fake-secret")

    def test_default_disable_and_delete_clear_default(self):
        self.js("manager.open(); changeProfile(store.profiles[0].id, 'toggle')")
        self.assertEqual(self.js("store.activeId"), "")
        self.js("changeProfile(store.profiles[0].id, 'toggle'); changeProfile(store.profiles[0].id, 'default')")
        self.assertTrue(self.js("store.activeId !== ''"))
        self.js("changeProfile(store.profiles[0].id, 'delete')")
        self.assertEqual(self.js("store.activeId"), "")
        self.assertEqual(self.js("store.profiles.length"), 0)
        self.js("initialize()")
        self.assertEqual(self.js("store.profiles.length"), 0)

    def test_multikey_draft_preserves_separators_and_key_is_masked(self):
        self.js("manager.open(); editor.edit(null,false); keyInput.text='first;second,third\\nfourth'")
        self.assertEqual(self.js("editor.readDraft().api_key"), "first;second,third\nfourth")
        self.assertTrue(self.js("keyInput.echoMode === TextInput.Password"))

    def test_keyboard_tab_space_and_escape_preserve_cancelled_draft(self):
        before = self.js("JSON.stringify(store)")
        self.js("manager.open(); editor.edit(null,false)")
        wait(30)
        self.assertTrue(self.js("nameInput.activeFocus"))
        for key in (Qt.Key_Tab, Qt.Key_Space):
            QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier))
            QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier))
        self.assertTrue(self.js("enabledInput.activeFocus"))
        self.assertFalse(self.js("enabledInput.checked"))
        QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyRelease, Qt.Key_Escape, Qt.NoModifier))
        wait(20)
        self.assertFalse(self.js("editor.opened"))
        self.assertEqual(self.js("JSON.stringify(store)"), before)

    def test_large_model_list_search_preserves_manual_model(self):
        self.js("manager.open(); editor.edit(null,false); modelInput.text='manual-private'; editor.models=Array.from({length:1500}, (_,i) => 'model-' + String(i)); editor.showModels=true; modelSearch.text='model-149'")
        wait(20)
        self.assertEqual(self.js("modelsList.count"), 11)
        self.assertEqual(self.js("modelInput.text"), "manual-private")

    def test_model_popup_is_bounded_and_manual_add_selects_model(self):
        self.js("manager.open(); editor.edit(null,false); modelInput.text='manual-kept'; editor.models=['model-one','model-two']; editor.showModels=true")
        wait(80)
        self.assertTrue(self.js("modelsPopup.opened"))
        self.assertEqual(self.js("modelsPopup.width"), self.js("modelField.width"))
        self.assertTrue(self.js("modelsPopup.y >= editor.contentItem.mapToItem(Overlay.overlay,0,0).y"))
        self.assertTrue(self.js("modelsPopup.y + modelsPopup.height <= editor.contentItem.mapToItem(Overlay.overlay,0,0).y + editor.contentItem.height + 1"))
        self.assertTrue(self.js("Math.min(Math.abs(modelsPopup.y + modelsPopup.height - modelField.mapToItem(Overlay.overlay,0,0).y), Math.abs(modelsPopup.y - modelField.mapToItem(Overlay.overlay,0,modelField.height).y)) <= size_.smallSpacing + 1"), self.js("JSON.stringify({popupY:modelsPopup.y,popupHeight:modelsPopup.height,field:modelField.mapToItem(Overlay.overlay,0,0),fieldHeight:modelField.height})"))
        self.js("modelsPopup.adding=true; manualModel.text='private-added'; modelsPopup.addManual()")
        self.assertEqual(self.js("modelInput.text"), "private-added")
        self.assertIn("private-added", self.js("editor.models"))
        self.assertFalse(self.js("modelsPopup.opened"))

    def test_model_popup_keyboard_selection_and_escape(self):
        self.js("manager.open(); editor.edit(null,false); editor.models=['model-one','model-two']; editor.showModels=true")
        wait(30)
        for key in (Qt.Key_Down, Qt.Key_Return):
            QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier))
            QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier))
        self.assertEqual(self.js("modelInput.text"), "model-one")
        self.js("editor.showModels=true")
        wait(20)
        QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        QCoreApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyRelease, Qt.Key_Escape, Qt.NoModifier))
        self.assertFalse(self.js("modelsPopup.opened"))
        self.assertTrue(self.js("editor.opened"))

    def test_saved_profiles_and_default_survive_settings_reload(self):
        self.js("manager.open(); editor.edit(null,false); nameInput.text='持久保存'; keyInput.text='fake-persisted'; modelInput.text='private-vision'; editor.save(); changeProfile(store.profiles[1].id,'default')")
        saved = self.js("JSON.stringify(store)")
        self.js("configs.settingsReload()")
        wait(40)
        self.panel = self.window.findChild(QObject, "aiProfiles")
        self.assertEqual(self.js("JSON.stringify(store)"), saved)
        self.assertEqual(self.js("current().model"), "private-vision")

    def test_late_model_response_and_closed_editor_are_ignored(self):
        self.js("manager.open(); editor.edit(null,false); editor.modelsRequest='old'; editor.modelsBusy=true; editor.invalidate(true)")
        self.js("bridge.finished('old', 'models', {ok:true,models:['stale']})")
        self.assertEqual(self.js("editor.models.length"), 0)
        self.js("editor.modelsRequest='new'; bridge.finished('new','models',{ok:true,models:['custom-a','custom-b']})")
        self.assertEqual(self.js("editor.models.length"), 2)
        self.js("editor.modelsRequest='closed'; editor.close(); bridge.finished('closed','models',{ok:true,models:['late']})")
        self.assertEqual(self.js("editor.models.length"), 0)

    def test_page_migration_and_disabled_profile_fallback(self):
        self.js("manager.open(); editor.edit(null,false); editor.chooseProvider(providers.find(p => p.id === 'custom_openai')); nameInput.text='第三方'; keyInput.text='fake'; modelInput.text='vision'; editor.save()")
        self.js("pageConfigs.setValue('ocr.AIOCR.a_l_provider','custom_openai',false,true); pageConfigs.compDict['ocr.AIOCR.a_l_profile'].refresh()")
        self.assertEqual(self.js("pageConfigs.getValue('ocr.AIOCR.a_l_profile')"), self.js("store.profiles[1].id"))
        self.assertEqual(self.js("pageConfigs.getValue('ocr.AIOCR.a_l_provider')"), "")
        active = self.js("store.activeId")
        self.js("changeProfile(store.profiles[1].id,'toggle')")
        self.assertEqual(self.js("pageConfigs.getValue('ocr.AIOCR.a_l_profile')"), "")
        self.assertEqual(self.js("store.activeId"), active)
        self.assertGreater(self.js("qmlapp.popup.notifications"), 0)

    def test_apply_is_deferred_for_running_and_paused_queues(self):
        self.js("qmlapp.msnConnector.active=1; qmlapp.globalConfigs.ocrManager.requestAiApply()")
        self.assertEqual(self.js("qmlapp.msnConnector.applies"), 0)
        self.assertTrue(self.js("qmlapp.globalConfigs.ocrManager.aiApplyPending"))
        self.js("qmlapp.msnConnector.active=0; qmlapp.msnConnector.paused=1; qmlapp.globalConfigs.ocrManager.applyAiWhenIdle()")
        self.assertEqual(self.js("qmlapp.msnConnector.applies"), 0)
        self.js("qmlapp.msnConnector.paused=0; qmlapp.msnConnector.documents=1; qmlapp.globalConfigs.ocrManager.applyAiWhenIdle()")
        self.assertEqual(self.js("qmlapp.msnConnector.applies"), 0)
        self.js("qmlapp.msnConnector.documents=0; qmlapp.globalConfigs.ocrManager.applyAiWhenIdle()")
        self.assertEqual(self.js("qmlapp.msnConnector.applies"), 1)
        self.assertFalse(self.js("qmlapp.globalConfigs.ocrManager.aiApplyPending"))

    def test_async_model_fetch_and_real_ocr_probe_against_local_server(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                calls.append((self.path, self.headers.get("Authorization")))
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({"data": [{"id": "private-model"}, {"id": "other-model"}]}).encode())

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append((self.path, body))
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({"choices": [{"message": {"content": "UMI OCR TEST 123"}}]}).encode())

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.js("manager.open(); editor.edit(null,false); keyInput.text='fake-local-key'; baseInput.text=%s; modelInput.text='private-model'; editor.request('models')" % json.dumps("http://127.0.0.1:%s/proxy/v1" % server.server_port))
            for _ in range(150):
                wait(20)
                if not self.js("editor.modelsBusy"):
                    break
            self.assertEqual(self.js("editor.models.length"), 2, self.js("editor.message"))
            self.assertEqual(calls[0], ("/proxy/v1/models", "Bearer fake-local-key"))
            self.js("editor.request('test')")
            for _ in range(150):
                wait(20)
                if not self.js("editor.testBusy"):
                    break
            self.assertFalse(self.js("editor.messageError"), self.js("editor.message"))
            self.assertIn("UMI OCR TEST 123", self.js("editor.message"))
            self.assertEqual(calls[1][0], "/proxy/v1/chat/completions")
            self.assertEqual(calls[1][1]["model"], "private-model")
            self.assertEqual(self.js("editor.modelStatus('private-model')"), "OCR 测试通过")
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_themes_and_compact_render(self):
        capture = os.environ.get("AI_UI_CAPTURE_DIR")
        if capture:
            Path(capture).mkdir(parents=True, exist_ok=True)
        self.js("manager.open(); editor.edit(null,false); nameInput.text='第三方中转 · 图片文字识别'; keyInput.text='fake-key'; modelInput.text='vendor/custom-vision'")
        for theme, width, height, label in (("Default Dark",1040,840,"editor-dark"), ("Default Light",1040,840,"editor-light"), ("Default Dark",540,620,"editor-compact")):
            self.window.setWidth(width); self.window.setHeight(height)
            self.js("theme.manager.switchTheme(%s)" % json.dumps(theme))
            wait(80)
            self.assertGreater(self.js("editor.width"), 0)
            self.assertLessEqual(self.js("editor.width"), width)
            if capture:
                self.assertTrue(self.window.grabWindow().save(str(Path(capture) / (label + ".png"))))
            self.js("formScroll.contentItem.contentY=Math.max(0, modelField.mapToItem(formScroll.contentItem.contentItem,0,0).y-formScroll.height+modelField.height+size_.spacing); editor.models=['vendor/custom-vision','declared-image-model','untested-model','long-provider/long-model-name-for-visual-overflow-check']; editor.draft=mergeEvidence(editor.readDraft(),{context:bridge.evidenceContext(editor.readDraft()),models:editor.models,modelInfo:{'vendor/custom-vision':{imageDeclared:true},'declared-image-model':{imageDeclared:true}}},'models'); editor.draft=mergeEvidence(editor.readDraft(),{context:bridge.evidenceContext(editor.readDraft()),model:'vendor/custom-vision',ocrPassed:true},'test'); editor.showModels=true")
            wait(50)
            self.assertTrue(self.js("modelsPopup.opened"))
            if capture:
                self.assertTrue(self.window.grabWindow().save(str(Path(capture) / (label + "-models.png"))))
            self.js("modelsPopup.close()")
        self.window.setWidth(1040); self.window.setHeight(840)
        self.js("editor.close()")
        self.js("const next=JSON.parse(JSON.stringify(store)); next.profiles[0].name='工作中转'; next.profiles[0].provider='custom_openai'; next.profiles[0].model='vendor/custom-vision'; next.profiles.push({id:'local-preview',name:'本地视觉识别',provider:'ollama',model:'qwen-vl:latest',enabled:true,api_base:'http://localhost:11434/api',api_key:'',timeout:null,proxy_url:null}); next.profiles.push({id:'backup-preview',name:'备用中转',provider:'custom_openai',model:'vision-fallback',enabled:false,api_base:'https://example.invalid/v1',api_key:'',timeout:null,proxy_url:null}); persist(next)")
        wait(80)
        if capture:
            self.assertTrue(self.window.grabWindow().save(str(Path(capture) / "manager-dark.png")))
            self.js("theme.manager.switchTheme('Default Light')")
            wait(60)
            self.assertTrue(self.window.grabWindow().save(str(Path(capture) / "manager-light.png")))
            self.js("profileList.itemAtIndex(1).openContextMenu(80,30)")
            wait(30)
            self.assertTrue(self.window.grabWindow().save(str(Path(capture) / "manager-context-menu.png")))
            card = self.js("profileList.itemAtIndex(1)")
            menu = card.findChild(QObject, "aiProfileContextMenu")
            QMetaObject.invokeMethod(menu, "close", Qt.DirectConnection)
            self.window.setWidth(540); self.window.setHeight(620)
            wait(60)
            self.assertTrue(self.window.grabWindow().save(str(Path(capture) / "manager-compact.png")))
        self.assertFalse(self.messages, "\n".join(self.messages))


if __name__ == "__main__":
    unittest.main()
