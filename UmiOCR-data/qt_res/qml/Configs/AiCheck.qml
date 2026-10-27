import QtQuick 2.15
import QtQuick.Controls 2.15
import "../Widgets"

CheckBox {
    id: control
    implicitHeight: size_.line * 2.2
    spacing: size_.spacing
    padding: 0
    contentItem: Text_ { textFormat: Text.PlainText;
        text: control.text
        leftPadding: control.indicator.width + control.spacing
        verticalAlignment: Text.AlignVCenter
        font.pixelSize: control.font.pixelSize > 0 ? control.font.pixelSize : size_.text
    }
    indicator: Rectangle {
        implicitWidth: size_.line * 1.2
        implicitHeight: size_.line * 1.2
        x: 0; y: (control.height - height) / 2
        radius: size_.baseRadius * 0.5
        color: control.checked ? theme.specialBgColor : theme.bgColor
        border.width: 1
        border.color: control.activeFocus ? theme.specialTextColor : theme.subTextColor
        Item {
            anchors.centerIn: parent; width: size_.line; height: size_.line
            visible: control.checked
            // Geometry also renders with Qt's software backend, without shaders.
            Rectangle { x: size_.line * 0.12; y: size_.line * 0.56; width: size_.line * 0.4; height: Math.max(2, 2 * size_.scale); rotation: 45; color: theme.textColor }
            Rectangle { x: size_.line * 0.34; y: size_.line * 0.44; width: size_.line * 0.7; height: Math.max(2, 2 * size_.scale); rotation: -45; color: theme.textColor }
        }
    }
}
