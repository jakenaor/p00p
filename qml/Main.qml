pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 1180
    height: 760
    minimumWidth: 980
    minimumHeight: 640
    visible: true
    title: "p00p — shader terminal"
    color: "#010302"

    readonly property color backgroundColor: "#030604"
    readonly property color panelColor: "#071009"
    readonly property color panelHighColor: "#0c180e"
    readonly property color borderColor: "#558b4e"
    readonly property color titleBarColor: "#748275"
    readonly property color textColor: "#d9f7cb"
    readonly property color mutedColor: "#789276"
    readonly property color accentColor: "#b8ff78"
    readonly property color accentHoverColor: "#d5ffad"
    readonly property color buttonTextColor: "#061007"
    readonly property color dangerColor: "#ff766d"
    property bool shaderEnabled: true
    property bool customCursorActive: false
    property bool cursorInside: false
    property bool cursorPressed: false
    property real cursorX: width / 2
    property real cursorY: height / 2
    property int customCursorMode: 0 // 0 arrow, 1 hand, 2 ibeam

    onCustomCursorActiveChanged: backend.setCustomCursorActive(customCursorActive)

    function setHoverCursor(mode, hovering) {
        if (hovering)
            customCursorMode = mode
        else if (customCursorMode === mode)
            customCursorMode = 0
    }

    component TerminalText: Text {
        color: window.textColor
        font.family: "Menlo"
        font.pixelSize: 12
        renderType: Text.NativeRendering
    }

    component TerminalButton: Button {
        id: control
        property color fillColor: window.panelHighColor
        property color hoverFillColor: "#17271a"
        property color labelColor: window.textColor
        property color outlineColor: window.borderColor
        implicitHeight: 38
        implicitWidth: 112
        font.family: "Menlo"
        font.pixelSize: 11
        font.bold: true
        background: Rectangle {
            color: !control.enabled ? "#08100a"
                 : control.down ? Qt.darker(control.hoverFillColor, 1.15)
                 : control.hovered ? control.hoverFillColor
                 : control.fillColor
            border.width: 1
            border.color: !control.enabled ? "#263b29" : control.outlineColor
        }
        contentItem: Text {
            text: control.text
            color: !control.enabled ? "#425a44" : control.labelColor
            font: control.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        HoverHandler {
            onHoveredChanged: window.setHoverCursor(1, hovered)
            cursorShape: window.customCursorActive
                         ? Qt.BlankCursor : Qt.PointingHandCursor
        }
    }

    component TerminalField: TextField {
        id: field
        implicitHeight: 40
        color: window.textColor
        placeholderTextColor: window.mutedColor
        selectionColor: window.accentColor
        selectedTextColor: window.buttonTextColor
        font.family: "Menlo"
        font.pixelSize: 12
        leftPadding: 11
        rightPadding: 11
        background: Rectangle {
            color: window.panelHighColor
            border.width: field.activeFocus ? 2 : 1
            border.color: field.activeFocus ? window.accentColor : window.borderColor
        }
        HoverHandler {
            onHoveredChanged: window.setHoverCursor(2, hovered)
            cursorShape: window.customCursorActive
                         ? Qt.BlankCursor : Qt.IBeamCursor
        }
    }

    component TerminalArea: TextArea {
        id: area
        color: window.textColor
        selectionColor: window.accentColor
        selectedTextColor: window.buttonTextColor
        placeholderTextColor: window.mutedColor
        font.family: "Menlo"
        font.pixelSize: 12
        wrapMode: TextEdit.Wrap
        padding: 11
        background: Rectangle {
            color: window.panelHighColor
            border.width: area.activeFocus ? 2 : 1
            border.color: area.activeFocus ? window.accentColor : window.borderColor
        }
        HoverHandler {
            onHoveredChanged: window.setHoverCursor(2, hovered)
            cursorShape: window.customCursorActive
                         ? Qt.BlankCursor : Qt.IBeamCursor
        }
    }

    component TerminalCombo: ComboBox {
        id: combo
        implicitWidth: 130
        implicitHeight: 34
        font.family: "Menlo"
        font.pixelSize: 11
        contentItem: Text {
            leftPadding: 10
            rightPadding: 28
            text: combo.displayText.toUpperCase()
            color: window.textColor
            font: combo.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        indicator: Text {
            x: combo.width - width - 9
            anchors.verticalCenter: parent.verticalCenter
            text: "▼"
            color: window.accentColor
            font.family: "Menlo"
            font.pixelSize: 10
        }
        background: Rectangle {
            color: window.panelHighColor
            border.width: 1
            border.color: window.borderColor
        }
        delegate: ItemDelegate {
            width: combo.width
            height: 32
            contentItem: Text {
                text: modelData.toUpperCase()
                color: highlighted ? window.buttonTextColor : window.textColor
                font.family: "Menlo"
                font.pixelSize: 11
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                color: highlighted ? window.accentColor : window.panelHighColor
            }
        }
        popup: Popup {
            y: combo.height
            width: combo.width
            implicitHeight: contentItem.implicitHeight
            padding: 1
            background: Rectangle {
                color: window.panelHighColor
                border.width: 1
                border.color: window.borderColor
            }
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: combo.popup.visible ? combo.delegateModel : null
                currentIndex: combo.highlightedIndex
            }
        }
        HoverHandler {
            onHoveredChanged: window.setHoverCursor(1, hovered)
            cursorShape: window.customCursorActive
                         ? Qt.BlankCursor : Qt.PointingHandCursor
        }
    }

    component DetailLine: RowLayout {
        property string fieldName: ""
        property string fieldValue: ""
        spacing: 12
        TerminalText {
            text: fieldName
            color: window.mutedColor
            font.pixelSize: 9
            font.bold: true
            Layout.preferredWidth: 82
        }
        TerminalText {
            text: fieldValue
            Layout.fillWidth: true
            font.pixelSize: 12
            elide: Text.ElideRight
        }
    }

    Shortcut { sequences: [StandardKey.New]; onActivated: backend.newVault() }
    Shortcut { sequences: [StandardKey.Open]; onActivated: backend.openVault() }
    Shortcut { sequence: "Ctrl+Shift+N"; onActivated: editor.openNew() }
    Shortcut { sequence: "Meta+Shift+N"; onActivated: editor.openNew() }
    Shortcut { sequence: "F8"; onActivated: window.shaderEnabled = !window.shaderEnabled }
    Shortcut {
        sequence: "Escape"
        enabled: window.customCursorActive && !editor.visible
        onActivated: window.customCursorActive = false
    }

    Item {
        id: uiRoot
        anchors.fill: parent
        anchors.margins: 12
        layer.enabled: window.shaderEnabled
        layer.smooth: false
        layer.effect: ShaderEffect {
            property real time: 0.0
            property size resolution: Qt.size(uiRoot.width, uiRoot.height)
            property real curvature: 0.020
            property real scanlineStrength: 0.24
            property real noiseStrength: 0.009
            property real chromaStrength: 1.0
            fragmentShader: "shaders/crt.frag.qsb"
            NumberAnimation on time {
                from: 0.0
                to: 3600.0
                duration: 3600000
                loops: Animation.Infinite
                running: window.shaderEnabled
            }
        }

        HoverHandler {
            id: cursorTracker
            acceptedDevices: PointerDevice.Mouse
            cursorShape: window.customCursorActive
                         ? Qt.BlankCursor : Qt.ArrowCursor
        }

        Rectangle {
            anchors.fill: parent
            color: window.backgroundColor
        }

        RowLayout {
            anchors.fill: parent
            spacing: 14

            Rectangle {
                Layout.preferredWidth: 202
                Layout.fillHeight: true
                color: "#050a06"
                border.width: 2
                border.color: window.borderColor

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 15
                    spacing: 4

                    Text {
                        text: "💩"
                        font.family: "Apple Color Emoji"
                        font.pixelSize: 50
                        Layout.topMargin: 8
                    }
                    TerminalText {
                        text: "P00P"
                        font.pixelSize: 29
                        font.bold: true
                    }
                    TerminalText {
                        text: "WEIRD STORAGE // 02"
                        color: window.accentColor
                        font.pixelSize: 9
                        font.bold: true
                        Layout.bottomMargin: 34
                    }
                    TerminalButton {
                        text: "VAULT"
                        Layout.fillWidth: true
                        fillColor: window.panelHighColor
                        labelColor: window.textColor
                    }
                    Item { Layout.fillHeight: true }
                    TerminalText {
                        text: window.shaderEnabled
                              ? "SHADER // ACTIVE\nBACKEND // METAL\nREFRESH // VSYNC\nF8 // BYPASS"
                              : "SHADER // BYPASSED\nF8 // ENABLE"
                        color: window.mutedColor
                        font.pixelSize: 9
                        lineHeight: 1.35
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 72
                    color: window.panelColor
                    border.width: 2
                    border.color: window.borderColor

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            TerminalText {
                                text: "ACTIVE VAULT //"
                                color: window.accentColor
                                font.pixelSize: 9
                                font.bold: true
                            }
                            TerminalText {
                                text: backend.vaultPath
                                font.pixelSize: 14
                                font.bold: true
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }
                        }
                        TerminalButton {
                            text: "NEW VAULT"
                            onClicked: backend.newVault()
                        }
                        TerminalButton {
                            text: "OPEN VAULT"
                            fillColor: window.accentColor
                            hoverFillColor: window.accentHoverColor
                            labelColor: window.buttonTextColor
                            onClicked: backend.openVault()
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 14

                    Rectangle {
                        Layout.fillHeight: true
                        Layout.preferredWidth: 345
                        Layout.minimumWidth: 315
                        color: window.panelColor
                        border.width: 2
                        border.color: window.borderColor

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 0

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 43
                                color: window.titleBarColor
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 12
                                    anchors.rightMargin: 6
                                    TerminalText {
                                        text: "VAULT INDEX"
                                        color: window.buttonTextColor
                                        font.pixelSize: 15
                                        font.bold: true
                                        Layout.fillWidth: true
                                    }
                                    TerminalButton {
                                        text: "ADD ENTRY +"
                                        implicitWidth: 112
                                        implicitHeight: 30
                                        fillColor: window.accentColor
                                        hoverFillColor: window.accentHoverColor
                                        labelColor: window.buttonTextColor
                                        outlineColor: window.accentColor
                                        onClicked: editor.openNew()
                                    }
                                }
                            }

                            TerminalField {
                                id: searchField
                                Layout.fillWidth: true
                                Layout.margins: 11
                                placeholderText: "SEARCH VAULT..."
                                onTextChanged: backend.setQuery(text)
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 12
                                Layout.rightMargin: 12
                                Layout.bottomMargin: 7
                                spacing: 8
                                TerminalText {
                                    text: "SORT //"
                                    color: window.mutedColor
                                    font.pixelSize: 10
                                }
                                TerminalCombo {
                                    model: ["NAME", "USERNAME", "HEALTH", "UPDATED"]
                                    onCurrentTextChanged: backend.setSort(currentText)
                                }
                                Item { Layout.fillWidth: true }
                                TerminalButton {
                                    text: "⇅"
                                    implicitWidth: 36
                                    implicitHeight: 34
                                    onClicked: backend.toggleSort()
                                }
                            }

                            TerminalText {
                                text: backend.summaryText
                                color: window.mutedColor
                                font.pixelSize: 9
                                Layout.leftMargin: 12
                                Layout.bottomMargin: 8
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 12
                                Layout.rightMargin: 18
                                Layout.bottomMargin: 5
                                TerminalText { text: "NAME"; color: window.mutedColor; font.pixelSize: 9; font.bold: true; Layout.fillWidth: true }
                                TerminalText { text: "USER"; color: window.mutedColor; font.pixelSize: 9; font.bold: true; Layout.preferredWidth: 82 }
                                TerminalText { text: "HEALTH"; color: window.mutedColor; font.pixelSize: 9; font.bold: true; Layout.preferredWidth: 78 }
                            }

                            ListView {
                                id: entryList
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.leftMargin: 9
                                Layout.rightMargin: 7
                                Layout.bottomMargin: 9
                                clip: true
                                spacing: 4
                                model: backend.entries
                                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                                delegate: Rectangle {
                                    required property var modelData
                                    width: entryList.width - 8
                                    height: 52
                                    color: modelData.name === backend.selectedName
                                           ? window.accentColor : window.panelHighColor
                                    border.width: 1
                                    border.color: modelData.name === backend.selectedName
                                                  ? window.accentColor : window.borderColor
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 11
                                        anchors.rightMargin: 7
                                        spacing: 7
                                        TerminalText {
                                            text: modelData.name
                                            color: modelData.name === backend.selectedName
                                                   ? window.buttonTextColor : window.textColor
                                            font.bold: true
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }
                                        TerminalText {
                                            text: modelData.username
                                            color: modelData.name === backend.selectedName
                                                   ? window.buttonTextColor : window.textColor
                                            Layout.preferredWidth: 82
                                            elide: Text.ElideRight
                                        }
                                        TerminalText {
                                            text: modelData.healthText
                                            color: modelData.name === backend.selectedName
                                                   ? window.buttonTextColor : window.textColor
                                            font.bold: true
                                            Layout.preferredWidth: 78
                                            elide: Text.ElideRight
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: window.customCursorActive
                                                     ? Qt.BlankCursor : Qt.PointingHandCursor
                                        onEntered: window.setHoverCursor(1, true)
                                        onExited: window.setHoverCursor(1, false)
                                        onClicked: backend.selectEntry(modelData.name)
                                        onDoubleClicked: {
                                            backend.selectEntry(modelData.name)
                                            editor.openEdit()
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: window.panelColor
                        border.width: 2
                        border.color: window.borderColor

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 0
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 43
                                color: window.titleBarColor
                                TerminalText {
                                    anchors.fill: parent
                                    anchors.leftMargin: 13
                                    text: "ENTRY OUTPUT"
                                    color: window.buttonTextColor
                                    font.pixelSize: 15
                                    font.bold: true
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.margins: 18
                                spacing: 10
                                DetailLine { fieldName: "NAME"; fieldValue: backend.selectedName }
                                DetailLine { fieldName: "USERNAME"; fieldValue: backend.selectedUsername }
                                DetailLine { fieldName: "PASSWORD"; fieldValue: backend.selectedPassword }
                                DetailLine { fieldName: "UPDATED"; fieldValue: backend.selectedUpdated }
                                DetailLine { fieldName: "HEALTH"; fieldValue: backend.selectedHealth }
                                TerminalText {
                                    text: "NOTES"
                                    color: window.mutedColor
                                    font.pixelSize: 9
                                    font.bold: true
                                    Layout.topMargin: 8
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 95
                                    color: window.panelHighColor
                                    border.width: 1
                                    border.color: window.borderColor
                                    TerminalText {
                                        anchors.fill: parent
                                        anchors.margins: 11
                                        text: backend.selectedNotes
                                        wrapMode: Text.Wrap
                                        color: window.textColor
                                    }
                                }
                                Item { Layout.fillHeight: true }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    TerminalButton {
                                        text: backend.passwordVisible ? "HIDE" : "REVEAL"
                                        Layout.fillWidth: true
                                        enabled: backend.selectedName !== "—"
                                        onClicked: backend.togglePassword()
                                    }
                                    TerminalButton {
                                        text: "COPY PASSWORD"
                                        Layout.fillWidth: true
                                        enabled: backend.selectedName !== "—"
                                        onClicked: backend.copyPassword()
                                    }
                                    TerminalButton {
                                        text: "COPY USERNAME"
                                        Layout.fillWidth: true
                                        enabled: backend.selectedName !== "—"
                                        onClicked: backend.copyUsername()
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    TerminalButton {
                                        text: "EDIT ENTRY"
                                        Layout.fillWidth: true
                                        fillColor: window.accentColor
                                        hoverFillColor: window.accentHoverColor
                                        labelColor: window.buttonTextColor
                                        outlineColor: window.accentColor
                                        enabled: backend.selectedName !== "—"
                                        onClicked: editor.openEdit()
                                    }
                                    TerminalButton {
                                        text: "REMOVE"
                                        Layout.preferredWidth: 155
                                        fillColor: "#260e0e"
                                        hoverFillColor: "#3c1514"
                                        labelColor: window.dangerColor
                                        outlineColor: "#491918"
                                        enabled: backend.selectedName !== "—"
                                        onClicked: backend.removeEntry()
                                    }
                                }
                            }
                        }
                    }
                }

                TerminalText {
                    text: backend.statusText
                    color: window.mutedColor
                    font.pixelSize: 9
                    Layout.leftMargin: 3
                }
            }
        }

        Item {
            id: customCursor
            z: 9999
            visible: window.customCursorActive && window.cursorInside
            readonly property int hotspotX: window.customCursorMode === 1 ? 12
                                              : window.customCursorMode === 2 ? 8 : 0
            readonly property int hotspotY: window.customCursorMode === 2 ? 12 : 0
            x: Math.round(window.cursorX - uiRoot.x) - hotspotX
            y: Math.round(window.cursorY - uiRoot.y) - hotspotY
            width: 32
            height: 32

            Canvas {
                anchors.fill: parent
                antialiasing: false
                readonly property int pixelSize: 4
                readonly property var arrowPixels: [
                    "ff......",
                    "fcf.....",
                    "fccf....",
                    "fcccf...",
                    "fccccf..",
                    "fcccf...",
                    "fcfccf..",
                    ".f.fcf.."
                ]
                readonly property var handPixels: [
                    "...f....",
                    "..fcf...",
                    "..fcff..",
                    ".ffcccf.",
                    "fcfccccf",
                    ".fcccccf",
                    "..fcccf.",
                    "...fff.."
                ]
                readonly property var pressedHandPixels: [
                    "........",
                    "...f....",
                    "..fcff..",
                    ".ffcccf.",
                    "fcfccccf",
                    ".fcccccf",
                    "..fcccf.",
                    "...fff.."
                ]
                readonly property var ibeamPixels: [
                    ".fff....",
                    "fcccf...",
                    ".fcf....",
                    ".fcf....",
                    ".fcf....",
                    ".fcf....",
                    "fcccf...",
                    ".fff...."
                ]
                readonly property var pixels: window.customCursorMode === 1
                    ? (window.cursorPressed ? pressedHandPixels : handPixels)
                    : window.customCursorMode === 2 ? ibeamPixels : arrowPixels

                onPixelsChanged: requestPaint()

                onPaint: {
                    var context = getContext("2d")
                    context.clearRect(0, 0, width, height)
                    for (var row = 0; row < pixels.length; ++row) {
                        for (var column = 0; column < pixels[row].length; ++column) {
                            var pixel = pixels[row][column]
                            if (pixel === ".")
                                continue
                            context.fillStyle = pixel === "f" ? "#333c57" : "#f4f4f4"
                            context.fillRect(column * pixelSize, row * pixelSize,
                                             pixelSize, pixelSize)
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: editor
        parent: Overlay.overlay
        modal: true
        focus: true
        width: 570
        height: 650
        x: Math.round((window.width - width) / 2)
        y: Math.round((window.height - height) / 2)
        padding: 0
        closePolicy: Popup.CloseOnEscape
        property bool editMode: false
        property string originalName: ""

        function openNew() {
            editMode = false
            originalName = ""
            nameField.text = ""
            usernameField.text = ""
            passwordField.text = ""
            notesField.text = ""
            open()
            nameField.forceActiveFocus()
        }
        function openEdit() {
            var entry = backend.selectedEntry()
            if (!entry.name)
                return
            editMode = true
            originalName = entry.name
            nameField.text = entry.name
            usernameField.text = entry.username
            passwordField.text = entry.password
            notesField.text = entry.notes
            open()
            nameField.forceActiveFocus()
        }

        background: Rectangle {
            color: window.panelColor
            border.width: 2
            border.color: window.accentColor
        }
        contentItem: ColumnLayout {
            spacing: 10
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 46
                color: window.titleBarColor
                TerminalText {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    text: editor.editMode ? "EDIT VAULT ENTRY" : "ADD VAULT ENTRY"
                    color: window.buttonTextColor
                    font.pixelSize: 16
                    font.bold: true
                    verticalAlignment: Text.AlignVCenter
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.bottomMargin: 20
                spacing: 7
                TerminalText { text: "NAME"; color: window.mutedColor; font.pixelSize: 9; font.bold: true }
                TerminalField { id: nameField; Layout.fillWidth: true }
                TerminalText { text: "USERNAME"; color: window.mutedColor; font.pixelSize: 9; font.bold: true; Layout.topMargin: 3 }
                TerminalField { id: usernameField; Layout.fillWidth: true }
                TerminalText { text: "PASSWORD"; color: window.mutedColor; font.pixelSize: 9; font.bold: true; Layout.topMargin: 3 }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    TerminalField {
                        id: passwordField
                        Layout.fillWidth: true
                        echoMode: showPassword.checked ? TextInput.Normal : TextInput.Password
                    }
                    TerminalButton {
                        text: "GENERATE"
                        fillColor: window.accentColor
                        hoverFillColor: window.accentHoverColor
                        labelColor: window.buttonTextColor
                        outlineColor: window.accentColor
                        onClicked: {
                            var generated = backend.generatePassword(lengthBox.value, symbolBox.checked)
                            if (generated)
                                passwordField.text = generated
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 13
                    CheckBox { id: showPassword; text: "SHOW"; checked: false }
                    TerminalText { text: "LENGTH"; color: window.mutedColor; font.pixelSize: 10 }
                    SpinBox {
                        id: lengthBox
                        from: 12
                        to: 256
                        value: 24
                        editable: true
                        font.family: "Menlo"
                    }
                    CheckBox { id: symbolBox; text: "SYMBOLS"; checked: true }
                    Item { Layout.fillWidth: true }
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 46
                    color: window.panelHighColor
                    border.width: 1
                    border.color: window.borderColor
                    TerminalText {
                        anchors.fill: parent
                        anchors.margins: 9
                        text: backend.passwordHealth(passwordField.text).text
                        color: window.accentColor
                        font.pixelSize: 9
                        wrapMode: Text.Wrap
                    }
                }
                TerminalText { text: "NOTES"; color: window.mutedColor; font.pixelSize: 9; font.bold: true }
                TerminalArea { id: notesField; Layout.fillWidth: true; Layout.fillHeight: true }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    spacing: 8
                    TerminalButton {
                        text: "CANCEL"
                        Layout.fillWidth: true
                        onClicked: editor.close()
                    }
                    TerminalButton {
                        text: "SAVE ENTRY"
                        Layout.fillWidth: true
                        fillColor: window.accentColor
                        hoverFillColor: window.accentHoverColor
                        labelColor: window.buttonTextColor
                        outlineColor: window.accentColor
                        onClicked: {
                            var saved = editor.editMode
                                ? backend.editEntry(editor.originalName, nameField.text,
                                                    usernameField.text, passwordField.text,
                                                    notesField.text)
                                : backend.addEntry(nameField.text, usernameField.text,
                                                   passwordField.text, notesField.text)
                            if (saved)
                                editor.close()
                        }
                    }
                }
            }
        }
    }
}
