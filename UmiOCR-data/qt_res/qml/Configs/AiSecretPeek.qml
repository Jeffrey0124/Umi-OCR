import QtQuick 2.15
import QtQuick.Window 2.15
import "../Widgets"

Button_ {
    id: peek
    property bool holding: false
    readonly property bool revealed: holding && pressed && visible && enabled && Window.window && Window.window.active
    implicitWidth: size_.line * 2.3
    implicitHeight: implicitWidth
    radius: height / 2
    padding: size_.spacing
    Accessible.name: qsTr("按住显示 API 密钥")
    toolTip: qsTr("按住显示，松开隐藏")
    function conceal() { holding = false }
    onPressed: holding = true
    onReleased: conceal()
    onCanceled: conceal()
    onVisibleChanged: if(!visible) conceal()
    onEnabledChanged: if(!enabled) conceal()
    onActiveFocusChanged: if(!activeFocus) conceal()
    Connections {
        target: peek.Window.window
        function onActiveChanged() { if(!peek.Window.window.active) peek.conceal() }
    }
    contentItem: AiGlyph {
        glyph: peek.revealed ? "eye" : "eyeOff"
        stroke: peek.revealed ? theme.specialTextColor : theme.subTextColor
        scale: peek.revealed ? 1.08 : 1
        Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }
    }
}
