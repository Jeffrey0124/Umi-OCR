import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../Widgets"

Button_ {
    id: action
    property string glyph: "edit"
    implicitWidth: label.implicitWidth + size_.line + size_.spacing * 2.5
    implicitHeight: size_.line * 2.2
    Accessible.name: text_
    contentItem: RowLayout {
        spacing: size_.smallSpacing
        AiGlyph { glyph: action.glyph; stroke: action.textColor_; Layout.preferredWidth: size_.line; Layout.preferredHeight: size_.line }
        Text_ { id: label; textFormat: Text.PlainText; text: action.text_; color: action.textColor_; font.pixelSize: action.textSize }
    }
}
