import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import AiConfigConnector 1.0
import "../Widgets"

Item {
    id: root
    objectName: "aiProfiles"
    property string key: ""
    property var configs
    property string title: qsTr("AI 模型配置")
    property bool advanced: false
    property var store: ({version: 1, activeId: "", profiles: []})
    property var providers: []
    property var orderedProfiles: {
        const items = store.profiles.slice()
        const index = items.findIndex(p => p.id === store.activeId && p.enabled)
        if(index > 0) items.unshift(items.splice(index, 1)[0])
        return items
    }
    property string loadError: ""
    property string statusText: ""
    property bool statusError: false
    property color accent: (theme.bgColor.r + theme.bgColor.g + theme.bgColor.b > 1.8) ? Qt.darker(theme.specialTextColor, 1.6) : theme.specialTextColor
    property string listTestId: ""
    property var listTestProfile: null
    property int sequence: 0
    property string prefix: key.substring(0, key.lastIndexOf(".") + 1)
    property var updateUI: initialize
    anchors.left: parent.left
    anchors.right: parent.right
    height: summary.implicitHeight + size_.line * 3.6

    function shortConfig() {
        const values = configs.getValueDict()
        const result = {}
        for(let name in values)
            if(name.startsWith(prefix)) result[name.substring(prefix.length)] = values[name]
        return result
    }
    function initialize() {
        const result = bridge.initialize(shortConfig())
        providers = result.providers || []
        loadError = result.error || ""
        if(result.store) {
            store = result.store
            const serialized = JSON.stringify(store)
            if(configs.getValue(key) !== serialized)
                configs.setValue(key, serialized, false, true)
            syncLegacy()
        }
    }
    function providerName(id) {
        for(let i=0; i<providers.length; i++) if(providers[i].id === id) return providers[i].name
        return id
    }
    function current() {
        for(let i=0; i<store.profiles.length; i++)
            if(store.profiles[i].id === store.activeId && store.profiles[i].enabled) return store.profiles[i]
        return null
    }
    function persist(next, apply) {
        store = next
        configs.setValue(key, JSON.stringify(next), false, true)
        syncLegacy()
        qmlapp.pubSub.publish("<<aiProfilesChanged>>")
        if(apply !== false) qmlapp.globalConfigs.ocrManager.requestAiApply()
    }
    function syncLegacy() {
        const active = current()
        if(active) {
            configs.setValue(prefix + "a_provider", active.provider, false, true)
            for(let i=0; i<3; i++) {
                const suffix = ["api_key", "api_base", "model"][i]
                const field = prefix + active.provider + "_" + suffix
                if(configs.originDict[field]) configs.setValue(field, active[suffix], false, true)
            }
        }
    }
    function changeProfile(id, operation) {
        const next = JSON.parse(JSON.stringify(store))
        const index = next.profiles.findIndex(p => p.id === id)
        if(index < 0) return
        if(operation === "default") next.activeId = id
        if(operation === "toggle") {
            next.profiles[index].enabled = !next.profiles[index].enabled
            if(!next.profiles[index].enabled && next.activeId === id) next.activeId = ""
        }
        if(operation === "delete") {
            next.profiles.splice(index, 1)
            if(next.activeId === id) next.activeId = ""
        }
        persist(next)
    }
    function newRequest() { sequence++; return String(Date.now()) + "-" + sequence }
    function effectiveDraft(profile) {
        const result = JSON.parse(JSON.stringify(profile))
        const global = shortConfig()
        if(result.timeout === null || result.timeout === undefined) result.timeout = global.a_timeout || 30
        if(result.proxy_url === null || result.proxy_url === undefined) result.proxy_url = global.z_proxy_url || ""
        return result
    }
    function testSaved(profile) {
        listTestId = newRequest()
        listTestProfile = JSON.parse(JSON.stringify(profile))
        statusError = false
        statusText = qsTr("正在测试 %1…").arg(profile.name)
        bridge.request(listTestId, "test", effectiveDraft(profile))
    }
    function mergeEvidence(profile, result, action) {
        const next = JSON.parse(JSON.stringify(profile))
        if(!result.context || result.context !== bridge.evidenceContext(next)) return next
        const old = next.modelEvidence
        const evidence = old && old.context === result.context ? old : {context:result.context, models:{}}
        const entries = Object.create(null)
        for(let model of Object.keys(evidence.models)) entries[model] = evidence.models[model]
        evidence.models = entries
        if(action === "models") {
            for(let model in evidence.models) evidence.models[model].imageDeclared = false
            const info = result.modelInfo || {}
            for(let i=0; i<(result.models || []).length; i++) {
                const model = result.models[i]
                const entry = evidence.models[model] || {}
                entry.imageDeclared = !!(info[model] && info[model].imageDeclared)
                evidence.models[model] = entry
            }
        } else if(result.model) {
            const entry = evidence.models[result.model] || {}
            entry.ocrPassed = result.ocrPassed === true
            evidence.models[result.model] = entry
        }
        next.modelEvidence = evidence
        return next
    }
    Component.onCompleted: initialize()

    AiConfigConnector {
        id: bridge
        onFinished: {
            if(action === "test" && requestId === root.listTestId && manager.opened) {
                root.listTestId = ""
                root.statusError = !result.ok
                root.statusText = result.ok ? qsTr("识别测试成功 · %1 秒\n%2").arg(result.elapsed).arg(result.text) : result.error
                const next = JSON.parse(JSON.stringify(root.store))
                const index = next.profiles.findIndex(p => root.listTestProfile && p.id === root.listTestProfile.id)
                if(index >= 0 && result.context === bridge.evidenceContext(next.profiles[index])) {
                    next.profiles[index] = root.mergeEvidence(next.profiles[index], result, "test")
                    root.persist(next, false)
                }
                root.listTestProfile = null
                return
            }
            if(!editor.opened) return
            if(action === "models" && requestId === editor.modelsRequest) {
                editor.modelsBusy = false
                editor.modelsRequest = ""
                editor.messageError = !result.ok
                if(result.ok) {
                    editor.draft = root.mergeEvidence(editor.readDraft(), result, "models")
                    editor.models = result.models
                    editor.showModels = result.models.length > 0
                    modelSearch.text = ""
                    editor.message = result.models.length ? qsTr("已获取 %1 个模型，请选择或手动填写。列表可用不代表模型支持识图。").arg(result.models.length) : qsTr("服务商返回了空列表，可以手动填写模型。")
                } else editor.message = result.error
            }
            if(action === "test" && requestId === editor.testRequest) {
                editor.testBusy = false
                editor.testRequest = ""
                editor.messageError = !result.ok
                editor.message = result.ok ? qsTr("识别测试成功 · %1 秒\n%2").arg(result.elapsed).arg(result.text) : result.error
                editor.draft = root.mergeEvidence(editor.readDraft(), result, "test")
            }
        }
    }
    Text_ { textFormat: Text.PlainText; id: heading; text: root.title; font.bold: true; font.pixelSize: size_.largeText }
    Text_ { textFormat: Text.PlainText;
        id: summary
        anchors.top: heading.bottom; anchors.topMargin: size_.spacing
        anchors.left: parent.left; anchors.right: manageButton.left; anchors.rightMargin: size_.spacing
        wrapMode: Text.Wrap
        color: root.loadError ? theme.noColor : theme.subTextColor
        text: {
            const p = root.current()
            return root.loadError || (p ? qsTr("默认：%1\n%2 · %3").arg(p.name).arg(root.providerName(p.provider)).arg(p.model || qsTr("未填写模型")) : qsTr("尚未选择默认配置\n添加服务商并选择模型后即可开始识别。"))
        }
    }
    Button_ {
        id: manageButton
        anchors.right: parent.right; anchors.verticalCenter: summary.verticalCenter
        height: size_.line * 2.3; width: size_.line * 7
        text_: qsTr("管理配置"); textColor_: root.accent; borderWidth: 1
        enabled: !root.loadError
        onClicked: manager.open()
    }

    Popup {
        id: manager
        objectName: "aiProfileManager"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(parent.width - size_.spacing * 2, 980 * size_.scale)
        height: Math.min(parent.height - size_.spacing * 2, 690 * size_.scale)
        modal: true; focus: true; padding: size_.spacing * 2
        closePolicy: Popup.CloseOnEscape
        onClosed: { root.listTestId = ""; root.listTestProfile = null; editor.close() }
        background: Rectangle { color: theme.bgColor; radius: size_.panelRadius; border.width: 1; border.color: theme.coverColor3 }
        contentItem: ColumnLayout {
            spacing: size_.spacing * 2
            RowLayout {
                Layout.fillWidth: true
                Text_ { textFormat: Text.PlainText; text: qsTr("AI 模型配置"); font.pixelSize: size_.largeText; font.bold: true; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight }
                Button_ { text_: qsTr("添加配置"); textColor_: root.accent; implicitWidth: size_.line * 5; implicitHeight: size_.line * 2.2; onClicked: editor.edit(null, false) }
                Button_ { text_: qsTr("关闭"); implicitWidth: size_.line * 3; implicitHeight: size_.line * 2.2; onClicked: manager.close() }
            }
            Text_ { textFormat: Text.PlainText; text: qsTr("全局默认用于所有识别页面；各页面也可单独选择配置。"); color: theme.subTextColor; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Text_ { textFormat: Text.PlainText; visible: !root.store.activeId; text: qsTr("请选择一套启用的配置作为全局默认。"); color: root.accent; wrapMode: Text.Wrap; Layout.fillWidth: true }
            ListView {
                id: profileList
                Layout.fillWidth: true; Layout.fillHeight: true
                model: root.orderedProfiles; clip: true; spacing: size_.spacing
                ScrollBar.vertical: ScrollBar {}
                Text_ { textFormat: Text.PlainText;
                    anchors.centerIn: parent; visible: profileList.count === 0
                    text: qsTr("还没有配置\n点击“添加配置”，填写接口并拉取模型。"); color: theme.subTextColor
                    horizontalAlignment: Text.AlignHCenter
                }
                delegate: Rectangle {
                    id: profileCard
                    property string profileId: modelData.id
                    property bool canSetDefault: modelData.enabled && root.store.activeId !== modelData.id
                    activeFocusOnTab: true
                    border.width: activeFocus ? 1 : 0
                    border.color: root.accent
                    Accessible.name: modelData.name
                    function openContextMenu(px, py) { if(canSetDefault) profileContextMenu.popup(px, py) }
                    Keys.onPressed: {
                        if(event.key === Qt.Key_Menu || (event.key === Qt.Key_F10 && (event.modifiers & Qt.ShiftModifier))) {
                            openContextMenu(width / 2, height / 2)
                            event.accepted = true
                        }
                    }
                    width: profileList.width - size_.spacing * 2
                    height: cardContent.implicitHeight + size_.spacing * 3
                    radius: size_.baseRadius
                    color: theme.coverColor1
                    ColumnLayout {
                        id: cardContent
                        anchors.fill: parent; anchors.margins: size_.spacing * 1.5; spacing: size_.spacing
                        RowLayout {
                            Layout.fillWidth: true
                            Text_ { textFormat: Text.PlainText; text: modelData.name; font.bold: true; elide: Text.ElideRight; Layout.fillWidth: true; opacity: modelData.enabled ? 1 : 0.6 }
                            Text_ { textFormat: Text.PlainText; text: root.store.activeId === modelData.id ? qsTr("默认") : (modelData.enabled ? "" : qsTr("已禁用")); color: root.accent; font.pixelSize: size_.smallText }
                        }
                        Text_ { textFormat: Text.PlainText; text: root.providerName(modelData.provider) + " · " + (modelData.model || qsTr("未填写模型")); color: theme.subTextColor; elide: Text.ElideRight; Layout.fillWidth: true }
                        Flow {
                            id: cardActions
                            Layout.fillWidth: true
                            spacing: size_.smallSpacing
                            leftPadding: Math.max(0, width - (testAction.width + editAction.width + cloneAction.width + toggleAction.width + deleteAction.width + spacing * 4))
                            AiActionButton { id: testAction; objectName: "aiTestSaved"; glyph: "link"; text_: qsTr("测试连接"); onClicked: root.testSaved(modelData) }
                            AiActionButton { id: editAction; glyph: "edit"; text_: qsTr("编辑"); textColor_: root.accent; onClicked: editor.edit(modelData, false) }
                            AiActionButton { id: cloneAction; glyph: "clone"; text_: qsTr("复制"); onClicked: editor.edit(modelData, true) }
                            AiActionButton { id: toggleAction; glyph: modelData.enabled ? "disable" : "enable"; text_: modelData.enabled ? qsTr("禁用") : qsTr("启用"); onClicked: root.changeProfile(modelData.id, "toggle") }
                            AiActionButton {
                                id: deleteAction; glyph: "trash"; text_: qsTr("删除"); textColor_: theme.noColor
                                onClicked: { deleteDialog.profileId = modelData.id; deleteDialog.profileName = modelData.name; deleteDialog.open() }
                            }
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.RightButton
                        onPressed: { profileCard.forceActiveFocus(); profileCard.openContextMenu(mouse.x, mouse.y) }
                    }
                    Menu {
                        id: profileContextMenu
                        objectName: "aiProfileContextMenu"
                        width: size_.line * 10
                        padding: size_.smallSpacing
                        background: Rectangle { color: theme.bgColor; border.width: 1; border.color: theme.coverColor3; radius: size_.btnRadius }
                        MenuItem {
                            objectName: "aiSetDefaultContextAction"
                            text: qsTr("设为默认")
                            enabled: profileCard.canSetDefault
                            implicitHeight: size_.line * 2.3
                            contentItem: RowLayout {
                                AiGlyph { glyph: "check"; stroke: theme.textColor; Layout.preferredWidth: size_.line; Layout.preferredHeight: size_.line }
                                Text_ { textFormat: Text.PlainText; text: qsTr("设为默认"); color: theme.textColor; Layout.fillWidth: true }
                            }
                            background: Rectangle { color: parent.highlighted ? theme.coverColor2 : "transparent"; radius: size_.btnRadius }
                            onTriggered: root.changeProfile(profileCard.profileId, "default")
                        }
                    }
                }
            }
            Text_ { textFormat: Text.PlainText; visible: text !== ""; text: root.statusText; color: root.statusError ? theme.noColor : theme.subTextColor; wrapMode: Text.Wrap; Layout.fillWidth: true; maximumLineCount: 4; elide: Text.ElideRight }
        }
    }
    Dialog {
        id: deleteDialog
        parent: Overlay.overlay; anchors.centerIn: parent; modal: true
        property string profileId: ""
        property string profileName: ""
        title: qsTr("删除配置")
        implicitHeight: size_.line * 11
        header: Text_ { textFormat: Text.PlainText; text: deleteDialog.title; font.bold: true; padding: size_.spacing * 2 }
        width: Math.min(400 * size_.scale, manager.width)
        contentItem: Text_ { textFormat: Text.PlainText; text: qsTr("删除“%1”？此操作会移除已保存的接口和密钥。").arg(deleteDialog.profileName); wrapMode: Text.Wrap }
        background: Rectangle { color: theme.bgColor; border.width: 1; border.color: theme.coverColor3; radius: size_.baseRadius }
        footer: RowLayout {
            Item { Layout.fillWidth: true }
            Button_ { text_: qsTr("取消"); implicitWidth: size_.line * 5; implicitHeight: size_.line * 2.3; onClicked: deleteDialog.close() }
            Button_ { text_: qsTr("删除"); textColor_: theme.noColor; implicitWidth: size_.line * 5; implicitHeight: size_.line * 2.3; onClicked: { root.changeProfile(deleteDialog.profileId, "delete"); deleteDialog.close() } }
        }
    }

    Popup {
        id: editor
        objectName: "aiProfileEditor"
        parent: Overlay.overlay; anchors.centerIn: parent
        width: Math.min(parent.width - size_.spacing * 2, 760 * size_.scale)
        height: Math.min(parent.height - size_.spacing * 2, 790 * size_.scale)
        modal: true; focus: true; padding: size_.spacing * 2; closePolicy: Popup.CloseOnEscape
        property var draft: ({})
        property bool adding: true
        property bool moreProviders: false
        property bool advancedOpen: false
        property bool modelsBusy: false
        property bool testBusy: false
        property bool showModels: false
        onShowModelsChanged: { if(showModels) modelsPopup.open(); else modelsPopup.close() }
        onWidthChanged: if(showModels) Qt.callLater(modelsPopup.position)
        onHeightChanged: if(showModels) Qt.callLater(modelsPopup.position)
        property var models: []
        property string modelsRequest: ""
        property string testRequest: ""
        property string message: ""
        property bool messageError: false
        function invalidate(connection) {
            testRequest = ""; testBusy = false; message = ""
            if(connection) {
                modelsRequest = ""; modelsBusy = false; models = []; showModels = false
                if(draft.modelEvidence) { const next = JSON.parse(JSON.stringify(draft)); delete next.modelEvidence; draft = next }
            }
        }
        function edit(profile, duplicate) {
            invalidate(true)
            adding = !profile || duplicate
            draft = profile ? JSON.parse(JSON.stringify(profile)) : {id: "", name: "姚记「梅花工作室」", provider: "yaoji", enabled: true, api_base: "https://llm-proxy.yuwan-game.com/v1", api_key: "", model: "", timeout: null, proxy_url: null}
            if(duplicate) { draft.id = ""; draft.name += qsTr(" 副本") }
            nameInput.text = draft.name
            baseInput.text = draft.api_base
            keyInput.text = draft.api_key
            modelInput.text = draft.model
            timeoutInput.text = draft.timeout === null || draft.timeout === undefined ? "" : String(draft.timeout)
            inheritProxy.checked = draft.proxy_url === null || draft.proxy_url === undefined
            proxyInput.text = draft.proxy_url || ""
            enabledInput.checked = draft.enabled
            if(draft.modelEvidence && draft.modelEvidence.context === bridge.evidenceContext(readDraft())) models = Object.keys(draft.modelEvidence.models)
            secretPeek.conceal(); moreProviders = false; providerSearch.text = ""; advancedOpen = false
            open()
            nameInput.forceActiveFocus()
        }
        function chooseProvider(preset) {
            secretPeek.conceal()
            nameInput.text = preset.name
            if(draft.provider === preset.id) return
            const next = JSON.parse(JSON.stringify(draft)); next.provider = preset.id
            draft = next
            baseInput.text = preset.api_base; modelInput.text = preset.model; keyInput.text = ""
            invalidate(true)
        }
        function modelFlags(model) {
            const evidence = draft.modelEvidence
            if(!evidence || evidence.context !== bridge.evidenceContext(readDraft())) return ({})
            return Object.prototype.hasOwnProperty.call(evidence.models, model) ? evidence.models[model] : ({})
        }
        function modelStatus(model) {
            const flags = modelFlags(model)
            const labels = []
            if(flags.imageDeclared) labels.push(qsTr("支持图片（服务商声明）"))
            if(flags.ocrPassed) labels.push(qsTr("OCR 测试通过"))
            else if(flags.ocrPassed === false) labels.push(qsTr("OCR 测试未通过"))
            return labels.length ? labels.join(" · ") : qsTr("能力未知／未测试")
        }
        function readDraft() {
            const result = JSON.parse(JSON.stringify(draft))
            result.name = nameInput.text; result.api_base = baseInput.text; result.api_key = keyInput.text
            result.model = modelInput.text; result.enabled = enabledInput.checked
            result.timeout = timeoutInput.text.trim() ? Number(timeoutInput.text) : null
            result.proxy_url = inheritProxy.checked ? null : proxyInput.text.trim()
            return result
        }
        function request(action) {
            const id = root.newRequest()
            message = action === "models" ? qsTr("正在拉取模型…") : qsTr("正在识别测试图片…")
            messageError = false
            if(action === "models") { modelsRequest = id; modelsBusy = true } else { testRequest = id; testBusy = true }
            bridge.request(id, action, root.effectiveDraft(readDraft()))
        }
        function save() {
            const result = bridge.validate(readDraft())
            if(result.error) { message = result.error; messageError = true; return }
            const next = JSON.parse(JSON.stringify(root.store))
            const profile = result.profile
            const index = next.profiles.findIndex(p => p.id === profile.id)
            if(index < 0) next.profiles.push(profile); else next.profiles[index] = profile
            if(!profile.enabled && next.activeId === profile.id) next.activeId = ""
            if(adding && next.profiles.length === 1 && profile.enabled) next.activeId = profile.id
            root.persist(next)
            close()
        }
        onClosed: { secretPeek.conceal(); invalidate(true) }

        Popup {
            id: modelsPopup
            objectName: "aiModelsPopup"
            parent: Overlay.overlay
            focus: true
            padding: size_.spacing
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
            property real room: 300 * size_.scale
            property bool adding: false
            property var choices: {
                const all = editor.models.slice()
                const current = modelInput.text.trim()
                if(current && all.indexOf(current) < 0) all.unshift(current)
                return all
            }
            width: modelField.width
            height: Math.min(room, size_.line * (adding ? 22 : 20))
            function position() {
                const overlay = Overlay.overlay
                const field = modelField.mapToItem(overlay, 0, 0)
                const bounds = editor.contentItem.mapToItem(overlay, 0, 0)
                const gap = size_.smallSpacing
                const bottom = bounds.y + editor.contentItem.height
                const below = bottom - field.y - modelField.height - gap
                const above = field.y - bounds.y - gap
                const desiredHeight = size_.line * (adding ? 22 : 20)
                const down = below >= Math.min(220 * size_.scale, desiredHeight) || below >= above
                room = Math.max(size_.line * 6, Math.min(320 * size_.scale, down ? below : above))
                const popupHeight = Math.min(room, desiredHeight)
                x = Math.max(bounds.x, Math.min(field.x, bounds.x + editor.contentItem.width - width))
                y = down ? field.y + modelField.height + gap : field.y - popupHeight - gap
                y = Math.max(bounds.y, Math.min(y, bottom - popupHeight))
            }
            function choose(model) {
                modelInput.text = model
                editor.invalidate(false)
                close()
                modelInput.forceActiveFocus()
            }
            function addManual() {
                const model = manualModel.text.trim()
                if(!model) { manualModel.forceActiveFocus(); return }
                if(editor.models.indexOf(model) < 0) editor.models = editor.models.concat([model])
                choose(model)
            }
            onAboutToShow: { adding = false; modelSearch.text = ""; position() }
            onOpened: { position(); modelSearch.forceActiveFocus(); Qt.callLater(position) }
            onHeightChanged: if(visible) Qt.callLater(position)
            onClosed: editor.showModels = false
            background: Rectangle { color: theme.bgColor; border.color: theme.coverColor3; border.width: 1; radius: size_.btnRadius }
            contentItem: ColumnLayout {
                spacing: size_.smallSpacing
                AiField {
                    id: modelSearch
                    placeholderText: qsTr("搜索模型")
                    Layout.fillWidth: true
                    Keys.onDownPressed: { modelsList.currentIndex = 0; modelsList.forceActiveFocus() }
                    onAccepted: { if(modelsList.count > 0) modelsPopup.choose(modelsList.model[0]); else { modelsPopup.adding = true; manualModel.text = text; manualModel.forceActiveFocus() } }
                }
                ListView {
                    id: modelsList
                    objectName: "aiModelsList"
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true
                    model: modelsPopup.choices.filter(m => m.toLowerCase().indexOf(modelSearch.text.toLowerCase()) >= 0)
                    currentIndex: -1
                    ScrollBar.vertical: ScrollBar {}
                    Keys.onReturnPressed: if(currentIndex >= 0) modelsPopup.choose(model[currentIndex])
                    Keys.onEnterPressed: if(currentIndex >= 0) modelsPopup.choose(model[currentIndex])
                    delegate: ItemDelegate {
                        width: modelsList.width
                        height: size_.line * 3.5
                        highlighted: hovered || ListView.isCurrentItem || modelInput.text === modelData
                        Accessible.name: modelData + " · " + editor.modelStatus(modelData)
                        background: Rectangle { color: parent.highlighted ? theme.coverColor2 : "transparent"; radius: size_.btnRadius }
                        contentItem: RowLayout {
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: size_.smallSpacing / 2
                                Text_ { textFormat: Text.PlainText; text: modelData; color: modelInput.text === modelData ? root.accent : theme.textColor; elide: Text.ElideRight; Layout.fillWidth: true }
                                Text_ { textFormat: Text.PlainText; text: editor.modelStatus(modelData); font.pixelSize: size_.smallText; color: editor.modelFlags(modelData).ocrPassed === false ? theme.noColor : theme.textColor; opacity: 0.85; elide: Text.ElideRight; Layout.fillWidth: true }
                            }
                            AiGlyph { glyph: "check"; stroke: root.accent; visible: modelInput.text === modelData; Layout.preferredWidth: size_.line; Layout.preferredHeight: size_.line }
                        }
                        ToolTip.visible: hovered && modelData.length > 35
                        ToolTip.text: modelData
                        onClicked: modelsPopup.choose(modelData)
                    }
                    Text_ { textFormat: Text.PlainText; anchors.fill: parent; visible: modelsList.count === 0; text: qsTr("没有匹配模型\n可在下方添加模型"); color: theme.subTextColor; wrapMode: Text.Wrap; verticalAlignment: Text.AlignVCenter; horizontalAlignment: Text.AlignHCenter }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: theme.coverColor3 }
                AiField { id: manualModel; visible: modelsPopup.adding; Layout.fillWidth: true; placeholderText: qsTr("填写模型 ID"); onAccepted: modelsPopup.addManual() }
                Button_ {
                    Layout.fillWidth: true; Layout.preferredHeight: size_.line * 2.2
                    text_: modelsPopup.adding ? qsTr("确认添加") : qsTr("添加模型")
                    textColor_: root.accent
                    contentItem: RowLayout {
                        AiGlyph { glyph: "add"; stroke: root.accent; Layout.preferredWidth: size_.line; Layout.preferredHeight: size_.line }
                        Text_ { textFormat: Text.PlainText; text: parent.parent.text_; color: root.accent; Layout.fillWidth: true }
                    }
                    onClicked: {
                        if(modelsPopup.adding) modelsPopup.addManual()
                        else { modelsPopup.adding = true; manualModel.text = modelSearch.text; manualModel.forceActiveFocus() }
                    }
                }
            }
        }
        Connections {
            target: modelRow
            function onYChanged() { if(modelsPopup.visible) Qt.callLater(modelsPopup.position) }
            function onWidthChanged() { if(modelsPopup.visible) Qt.callLater(modelsPopup.position) }
        }
        Connections {
            target: formScroll.contentItem
            function onContentYChanged() { if(modelsPopup.visible) Qt.callLater(modelsPopup.position) }
        }
        background: Rectangle { color: theme.bgColor; radius: size_.panelRadius; border.width: 1; border.color: theme.coverColor3 }
        contentItem: ColumnLayout {
            spacing: size_.spacing
            RowLayout {
                Layout.fillWidth: true
                Text_ { textFormat: Text.PlainText; text: editor.adding ? qsTr("添加 AI 配置") : qsTr("编辑 AI 配置"); font.pixelSize: size_.largeText; font.bold: true; Layout.fillWidth: true }
                Button_ { text_: qsTr("关闭"); implicitWidth: size_.line * 4; implicitHeight: size_.line * 2.2; onClicked: editor.close() }
            }
            ScrollView {
                id: formScroll
                Layout.fillWidth: true; Layout.fillHeight: true; contentWidth: availableWidth; clip: true
                ColumnLayout {
                    width: formScroll.availableWidth; spacing: size_.spacing
                    Text_ { textFormat: Text.PlainText; text: qsTr("基本信息"); font.bold: true; Layout.topMargin: size_.spacing; Layout.bottomMargin: size_.spacing }
                    Text_ { textFormat: Text.PlainText; text: qsTr("配置名称") }
                    AiField { id: nameInput; objectName: "aiProfileName"; placeholderText: qsTr("例如：工作中转 · 视觉识别"); Layout.fillWidth: true }
                    AiCheck { id: enabledInput; text: qsTr("启用此配置"); font.pixelSize: size_.text }
                    Text_ { textFormat: Text.PlainText; text: qsTr("服务商与接口"); font.bold: true; Layout.topMargin: size_.spacing * 2; Layout.bottomMargin: size_.spacing }
                    Flow {
                        Layout.fillWidth: true; spacing: size_.smallSpacing
                        Repeater {
                            model: root.providers.filter(p => ["yaoji", "openai", "custom_openai", "gemini", "alibaba", "siliconflow", "ollama"].indexOf(p.id) >= 0)
                            Button_ {
                                text_: modelData.name; implicitWidth: Math.max(size_.line * 5, implicitContentWidth + size_.spacing * 3); implicitHeight: size_.line * 2.1
                                textColor_: editor.draft.provider === modelData.id ? root.accent : theme.textColor
                                borderWidth: editor.draft.provider === modelData.id ? 1 : 0
                                bgColor_: theme.coverColor1
                                onClicked: editor.chooseProvider(modelData)
                            }
                        }
                        Button_ { text_: editor.moreProviders ? qsTr("收起服务商") : qsTr("更多服务商"); implicitWidth: size_.line * 7; implicitHeight: size_.line * 2.1; onClicked: editor.moreProviders = !editor.moreProviders }
                    }
                    Text_ { textFormat: Text.PlainText; text: qsTr("当前服务商：%1").arg(root.providerName(editor.draft.provider)); color: theme.subTextColor; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    AiField { id: providerSearch; visible: editor.moreProviders; placeholderText: qsTr("搜索服务商"); Layout.fillWidth: true }
                    Flow {
                        visible: editor.moreProviders; Layout.fillWidth: true; spacing: size_.smallSpacing
                        Repeater {
                            model: root.providers.filter(p => (p.name + " " + p.id).toLowerCase().indexOf(providerSearch.text.toLowerCase()) >= 0)
                            Button_ {
                                text_: modelData.name; implicitWidth: Math.max(size_.line * 5, implicitContentWidth + size_.spacing * 3); implicitHeight: size_.line * 2.1
                                textColor_: editor.draft.provider === modelData.id ? root.accent : theme.textColor
                                borderWidth: editor.draft.provider === modelData.id ? 1 : 0
                                onClicked: editor.chooseProvider(modelData)
                            }
                        }
                    }
                    Text_ { textFormat: Text.PlainText; text: qsTr("API 地址") }
                    AiField { id: baseInput; objectName: "aiProfileBase"; placeholderText: "https://api.example.com/v1"; Layout.fillWidth: true; onTextEdited: editor.invalidate(true) }
                    Text_ { textFormat: Text.PlainText; text: qsTr("API 密钥") }
                    Item {
                        Layout.fillWidth: true; Layout.preferredHeight: keyInput.implicitHeight
                        AiField { id: keyInput; objectName: "aiProfileKey"; anchors.fill: parent; rightPadding: height; echoMode: secretPeek.revealed ? TextInput.Normal : TextInput.Password; placeholderText: qsTr("本地服务可留空；多个密钥用逗号、分号或换行分隔"); onTextEdited: editor.invalidate(true) }
                        AiSecretPeek { id: secretPeek; objectName: "aiSecretPeek"; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: parent.height; height: parent.height }
                    }
                    Text_ { textFormat: Text.PlainText; text: qsTr("模型"); font.bold: true; Layout.topMargin: size_.spacing * 2; Layout.bottomMargin: size_.spacing }
                    RowLayout {
                        id: modelRow
                        Layout.fillWidth: true
                        Item {
                            id: modelField
                            Layout.fillWidth: true; Layout.preferredHeight: modelInput.implicitHeight
                            AiField { id: modelInput; objectName: "aiProfileModel"; anchors.fill: parent; rightPadding: height; placeholderText: qsTr("选择或填写模型 ID"); onTextEdited: editor.invalidate(false); Keys.onDownPressed: editor.showModels = true }
                            Button_ {
                                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                width: parent.height; height: parent.height
                                Accessible.name: qsTr("展开模型列表")
                                toolTip: qsTr("选择或添加模型")
                                contentItem: AiGlyph { glyph: "chevron"; stroke: theme.subTextColor }
                                onClicked: editor.showModels = !editor.showModels
                            }
                        }
                        Button_ {
                            objectName: "aiModelsRefresh"
                            Layout.preferredWidth: modelField.height; Layout.preferredHeight: modelField.height
                            enabled: !editor.modelsBusy; radius: height / 2
                            Accessible.name: qsTr("拉取模型")
                            toolTip: editor.modelsBusy ? qsTr("正在拉取模型…") : qsTr("拉取 / 刷新模型")
                            contentItem: AiGlyph {
                                id: refreshGlyph
                                glyph: "refresh"; stroke: root.accent
                                RotationAnimator on rotation { from: 0; to: 360; duration: 900; loops: Animation.Infinite; running: editor.modelsBusy }
                            }
                            onClicked: editor.request("models")
                        }
                    }
                    Text_ { textFormat: Text.PlainText; visible: modelInput.text.trim() !== ""; text: editor.modelStatus(modelInput.text.trim()); font.pixelSize: size_.smallText; color: theme.subTextColor; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Button_ { text_: editor.advancedOpen ? qsTr("收起高级设置") : qsTr("高级设置"); textColor_: theme.subTextColor; Layout.topMargin: size_.spacing * 2; Layout.preferredHeight: size_.line * 2.2; Layout.preferredWidth: size_.line * 8; onClicked: editor.advancedOpen = !editor.advancedOpen }
                    Text_ { textFormat: Text.PlainText; visible: editor.advancedOpen; text: qsTr("请求超时（秒）") }
                    AiField { id: timeoutInput; visible: editor.advancedOpen; placeholderText: qsTr("留空使用共享超时，默认 30 秒"); validator: IntValidator { bottom: 5; top: 120 } Layout.fillWidth: true; onTextEdited: editor.invalidate(true) }
                    AiCheck { id: inheritProxy; visible: editor.advancedOpen; text: qsTr("使用共享代理设置"); font.pixelSize: size_.text; onToggled: editor.invalidate(true) }
                    AiField { id: proxyInput; visible: editor.advancedOpen && !inheritProxy.checked; placeholderText: qsTr("代理 URL；留空使用系统网络设置"); Layout.fillWidth: true; onTextEdited: editor.invalidate(true) }
                    Item { Layout.preferredHeight: size_.spacing }
                }
            }
            Text_ { textFormat: Text.PlainText; visible: text !== ""; text: editor.message; color: editor.messageError ? theme.noColor : theme.subTextColor; wrapMode: Text.Wrap; Layout.fillWidth: true; maximumLineCount: 4; elide: Text.ElideRight }
            RowLayout {
                Layout.fillWidth: true; Layout.topMargin: size_.spacing
                Button_ { text_: editor.testBusy ? qsTr("测试中…") : qsTr("测试连接"); enabled: !editor.testBusy; textColor_: root.accent; implicitWidth: size_.line * 6; implicitHeight: size_.line * 2.4; onClicked: editor.request("test") }
                Item { Layout.fillWidth: true }
                Button_ { text_: qsTr("取消"); implicitWidth: size_.line * 3; implicitHeight: size_.line * 2.4; onClicked: editor.close() }
                Button_ { text_: qsTr("保存"); textColor_: root.accent; borderWidth: 1; implicitWidth: size_.line * 4; implicitHeight: size_.line * 2.4; onClicked: editor.save() }
            }
        }
    }
}
