import QtQuick 2.15
import QtQuick.Controls 2.15
import AiConfigConnector 1.0
import "../Widgets"

Item {
    id: root
    property string key: ""
    property var configs
    property string title: qsTr("AI 配置")
    property bool advanced: false
    property var profiles: []
    property var updateUI: refresh
    property string subscription: "aiProfileSelector-" + root.toString()
    anchors.left: parent.left; anchors.right: parent.right
    height: size_.line * 2.5

    AiConfigConnector { id: bridge }
    function refresh() {
        const values = qmlapp.globalConfigs.getValueDict()
        const config = {}
        const prefix = "ocr.AIOCR."
        for(let name in values) if(name.startsWith(prefix)) config[name.substring(prefix.length)] = values[name]
        const result = bridge.initialize(config)
        if(!result.store) return
        profiles = result.store.profiles.filter(p => p.enabled)
        const legacyKey = key.substring(0, key.lastIndexOf(".") + 1) + "a_l_provider"
        let selected = configs.getValue(key) || ""
        const legacy = configs.getValue(legacyKey)
        if(legacy) {
            if(!selected) {
                for(let i=0; i<profiles.length; i++)
                    if(profiles[i].provider === legacy || profiles[i].legacyProvider === legacy) { selected = profiles[i].id; break }
                configs.setValue(key, selected, false, true)
            }
            configs.setValue(legacyKey, "", false, true)
        }
        const ids = profiles.map(p => p.id)
        if(selected && ids.indexOf(selected) < 0) {
            selected = ""
            configs.setValue(key, "", false, true)
            qmlapp.popup.simple(qsTr("AI 配置已更新"), qsTr("本页原选配置已删除或禁用，已改为跟随全局。"))
        }
        selector.model = [qsTr("跟随全局默认")].concat(profiles.map(p => p.name + " · " + p.model))
        selector.currentIndex = selected ? ids.indexOf(selected) + 1 : 0
    }
    Component.onCompleted: {
        refresh()
        qmlapp.pubSub.subscribeGroup("<<aiProfilesChanged>>", root, "refresh", subscription)
    }
    Component.onDestruction: qmlapp.pubSub.unsubscribeGroup(subscription)
    Text_ { textFormat: Text.PlainText; text: root.title; anchors.verticalCenter: parent.verticalCenter }
    ComboBox {
        id: selector
        anchors.right: parent.right; width: parent.width * 0.67; height: parent.height
        palette.text: theme.textColor; palette.buttonText: theme.textColor; palette.base: theme.bgColor; palette.button: theme.bgColor
        font.family: theme.fontFamily; font.pixelSize: size_.text
        Accessible.name: root.title
        onActivated: configs.setValue(root.key, index === 0 ? "" : root.profiles[index-1].id, false, true)
        background: Rectangle { color: theme.bgColor; border.width: 1; border.color: selector.activeFocus ? theme.specialTextColor : theme.coverColor3; radius: size_.btnRadius }
        contentItem: Text_ { textFormat: Text.PlainText; text: selector.currentText; color: theme.textColor; leftPadding: size_.spacing; rightPadding: size_.line * 1.5; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
        delegate: ItemDelegate {
            width: selector.width
            contentItem: Text_ { textFormat: Text.PlainText; text: modelData; elide: Text.ElideRight; color: theme.textColor; verticalAlignment: Text.AlignVCenter }
            background: Rectangle { color: parent.highlighted ? theme.coverColor2 : theme.bgColor }
        }
        popup: Popup {
            y: selector.height; width: selector.width; padding: 1
            implicitHeight: Math.min(contentItem.implicitHeight + 2, size_.line * 16)
            contentItem: ListView { clip: true; implicitHeight: contentHeight; model: selector.popup.visible ? selector.delegateModel : null; currentIndex: selector.highlightedIndex; ScrollBar.vertical: ScrollBar {} }
            background: Rectangle { color: theme.bgColor; border.width: 1; border.color: theme.coverColor3 }
        }
    }
}
