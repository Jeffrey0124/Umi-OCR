import QtQuick 2.15

Image {
    property string glyph: "refresh"
    property color stroke: theme.subTextColor
    property var paths: ({
        refresh: '<path d="M20 7v5h-5M4 17v-5h5M6.1 7a7 7 0 0 1 11.6-1.1L20 9M4 15l2.3 3.1A7 7 0 0 0 17.9 17"/>',
        chevron: '<path d="m6 9 6 6 6-6"/>',
        check: '<path d="m5 12 4 4L19 6"/>',
        add: '<path d="M12 5v14M5 12h14"/>',
        edit: '<path d="m15 4 5 5M4 20l5-1 11-11a2 2 0 0 0-5-5L4 15z"/>',
        clone: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M15 8V4H4v11h4"/>',
        link: '<path d="m10 13 4-4M8 16l-1 1a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0M16 8l1-1a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0" transform="translate(1 1) scale(.9)"/>',
        disable: '<circle cx="12" cy="12" r="8"/><path d="m6 6 12 12"/>',
        enable: '<path d="M12 3v8M7 5a8 8 0 1 0 10 0"/>',
        trash: '<path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>',
        eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
        eyeOff: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/><path d="m3 3 18 18"/>'
    })
    source: "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="' + stroke + '" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' + paths[glyph] + '</svg>')
    sourceSize.width: 24 * size_.scale
    sourceSize.height: 24 * size_.scale
    fillMode: Image.PreserveAspectFit
    smooth: true
}
