import QtQuick 2.15
import QtQuick.Controls 2.15
import "../Widgets"

TextField_ {
    implicitHeight: size_.line * 2.3
    color: theme.textColor
    placeholderTextColor: theme.subTextColor
    leftPadding: size_.spacing
    rightPadding: size_.spacing
    focus: false
    Accessible.name: placeholderText
    borderColor: activeFocus ? theme.specialTextColor : theme.coverColor3
}
