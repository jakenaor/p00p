pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// p00p terminal thingy. the shader is real. the hacker invisibility is still not.
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
    readonly property bool shaderEnabled: backend.shaderEnabled
    property int currentPage: 0 // 0 vault, 1 settings
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

    function playSound(cue) {
        // everything lands on one python hook, then the procedural audio goblin takes over.
        backend.requestSound(cue)
    }

    // tiny doors keep the modal from reaching sideways for a context property.
    // qmllint likes the qualification and the editor gets less spaghetti-shaped.
    function selectedEntry() {
        return backend.selectedEntry()
    }
    function generatePassword(length, symbols) {
        return backend.generatePassword(length, symbols)
    }
    function passwordHealth(password) {
        return backend.passwordHealth(password)
    }
    function saveEntry(editing, originalName, name, username, password, notes) {
        return editing
            ? backend.editEntry(originalName, name, username, password, notes)
            : backend.addEntry(name, username, password, notes)
    }

    //MARK: reusable terminal thingies
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
        Connections {
            target: control
            function onClicked() { backend.requestSound("ui_click") }
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
        // keyboard focus still needs the custom mouse ready before the next move.
        onActiveFocusChanged: {
            if (activeFocus)
                window.customCursorActive = true
        }
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
        onActiveFocusChanged: {
            if (activeFocus)
                window.customCursorActive = true
        }
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

    component TerminalSpin: SpinBox {
        id: spin
        editable: true
        implicitWidth: 132
        implicitHeight: 38
        leftPadding: 36
        rightPadding: 36
        font.family: "Menlo"
        font.pixelSize: 11

        // the native mac stepper eats half the number, so this one gets actual boxes.
        contentItem: TextInput {
            text: spin.textFromValue(spin.value, spin.locale)
            color: window.textColor
            selectionColor: window.accentColor
            selectedTextColor: window.buttonTextColor
            font: spin.font
            horizontalAlignment: TextInput.AlignHCenter
            verticalAlignment: TextInput.AlignVCenter
            readOnly: !spin.editable
            validator: spin.validator
            inputMethodHints: spin.inputMethodHints
            selectByMouse: true
        }
        down.indicator: Rectangle {
            x: 0
            y: 0
            width: 34
            height: spin.height
            color: spin.down.pressed ? "#223425" : window.panelColor
            border.width: 1
            border.color: window.borderColor
            TerminalText {
                anchors.centerIn: parent
                text: "−"
                font.pixelSize: 17
                color: spin.enabled ? window.textColor : window.mutedColor
            }
        }
        up.indicator: Rectangle {
            x: spin.width - width
            y: 0
            width: 34
            height: spin.height
            color: spin.up.pressed ? "#223425" : window.panelColor
            border.width: 1
            border.color: window.borderColor
            TerminalText {
                anchors.centerIn: parent
                text: "+"
                font.pixelSize: 17
                color: spin.enabled ? window.textColor : window.mutedColor
            }
        }
        background: Rectangle {
            color: window.panelHighColor
            border.width: spin.activeFocus ? 2 : 1
            border.color: spin.activeFocus ? window.accentColor : window.borderColor
        }
    }

    component TerminalCombo: Control {
        id: combo
        property var model: []
        property int currentIndex: 0
        readonly property string currentText: model.length > currentIndex
                                              ? String(model[currentIndex]) : ""
        property bool expanded: false
        signal activated(int index)
        implicitWidth: 130
        implicitHeight: 34
        z: expanded ? 8000 : 0
        focus: expanded
        activeFocusOnTab: true
        font.family: "Menlo"
        font.pixelSize: 11
        Accessible.role: Accessible.ComboBox
        Accessible.name: currentText

        function openMenu() {
            optionList.currentIndex = combo.currentIndex
            combo.expanded = true
            combo.forceActiveFocus()
        }
        function choose(index) {
            if (index < 0 || index >= combo.model.length)
                return
            combo.currentIndex = index
            combo.activated(index)
            combo.expanded = false
        }
        function moveHighlight(amount) {
            var count = combo.model.length
            if (count === 0)
                return
            optionList.currentIndex = (optionList.currentIndex + amount + count) % count
            optionList.positionViewAtIndex(optionList.currentIndex, ListView.Contain)
        }
        Keys.onPressed: function(event) {
            if (event.key === Qt.Key_Escape && combo.expanded) {
                combo.expanded = false
                event.accepted = true
            } else if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
                if (!combo.expanded)
                    combo.openMenu()
                combo.moveHighlight(event.key === Qt.Key_Down ? 1 : -1)
                event.accepted = true
            } else if (event.key === Qt.Key_Home && combo.expanded) {
                optionList.currentIndex = 0
                event.accepted = true
            } else if (event.key === Qt.Key_End && combo.expanded) {
                optionList.currentIndex = combo.model.length - 1
                event.accepted = true
            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                       || event.key === Qt.Key_Space) {
                if (combo.expanded)
                    combo.choose(optionList.currentIndex)
                else
                    combo.openMenu()
                event.accepted = true
            }
        }
        onActiveFocusChanged: {
            if (!activeFocus)
                expanded = false
        }
        contentItem: Text {
            leftPadding: 10
            rightPadding: 28
            text: combo.currentText.toUpperCase()
            color: window.textColor
            font: combo.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        Text {
            x: combo.width - width - 9
            anchors.verticalCenter: parent.verticalCenter
            text: combo.expanded ? "▲" : "▼"
            color: window.accentColor
            font.family: "Menlo"
            font.pixelSize: 10
        }
        background: Rectangle {
            color: window.panelHighColor
            border.width: 1
            border.color: window.borderColor
        }
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: window.customCursorActive
                         ? Qt.BlankCursor : Qt.PointingHandCursor
            onEntered: window.setHoverCursor(1, true)
            onExited: window.setHoverCursor(1, false)
            onClicked: {
                if (combo.expanded)
                    combo.expanded = false
                else
                    combo.openMenu()
            }
        }
        Rectangle {
            id: dropdown
            // the list has to live at the crt scene root. qt draws children outside a
            // control, but it will not send those children mouse clicks out there.
            parent: uiRoot
            x: combo.mapToItem(uiRoot, 0, 0).x + uiRoot.width * 0
            y: combo.mapToItem(uiRoot, 0, combo.height).y + uiRoot.height * 0
            width: combo.width
            height: Math.min(optionList.contentHeight + 2, 160)
            visible: combo.expanded
            z: 8001
            color: window.panelHighColor
            border.width: 1
            border.color: window.borderColor
            ListView {
                id: optionList
                anchors.fill: parent
                anchors.margins: 1
                clip: true
                model: combo.model
                currentIndex: combo.currentIndex
                delegate: Rectangle {
                    id: option
                    required property int index
                    required property string modelData
                    width: ListView.view.width
                    height: 32
                    color: optionMouse.containsMouse || optionList.currentIndex === index
                           ? window.accentColor : window.panelHighColor
                    Text {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        text: option.modelData.toUpperCase()
                        color: optionMouse.containsMouse || optionList.currentIndex === option.index
                               ? window.buttonTextColor : window.textColor
                        font.family: "Menlo"
                        font.pixelSize: 11
                        verticalAlignment: Text.AlignVCenter
                    }
                    MouseArea {
                        id: optionMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: window.customCursorActive
                                     ? Qt.BlankCursor : Qt.PointingHandCursor
                        onEntered: window.setHoverCursor(1, true)
                        onExited: window.setHoverCursor(1, false)
                        onClicked: {
                            combo.choose(option.index)
                        }
                    }
                }
            }
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

    Shortcut { sequences: [StandardKey.New]; enabled: !backend.privacyCurtain; onActivated: backend.newVault() }
    Shortcut { sequences: [StandardKey.Open]; enabled: !backend.privacyCurtain; onActivated: backend.openVault() }
    Shortcut { sequence: "Ctrl+Shift+N"; enabled: !backend.privacyCurtain; onActivated: editor.openNew() }
    Shortcut { sequence: "Meta+Shift+N"; enabled: !backend.privacyCurtain; onActivated: editor.openNew() }
    Shortcut {
        sequences: [StandardKey.Find]
        enabled: !editor.visible && !backend.privacyCurtain
        onActivated: searchField.forceActiveFocus()
    }
    Shortcut {
        sequence: "Ctrl+E"
        enabled: !editor.visible && !backend.privacyCurtain && backend.selectedName !== "—"
        onActivated: editor.openEdit()
    }
    Shortcut {
        sequence: "Meta+E"
        enabled: !editor.visible && !backend.privacyCurtain && backend.selectedName !== "—"
        onActivated: editor.openEdit()
    }
    Shortcut {
        sequences: [StandardKey.Save]
        enabled: editor.visible && !backend.privacyCurtain
        onActivated: editor.save()
    }
    Shortcut {
        sequences: [StandardKey.Undo]
        enabled: !editor.visible && !backend.privacyCurtain && backend.canUndo
        onActivated: backend.undo()
    }
    Shortcut {
        sequences: [StandardKey.Redo]
        enabled: !editor.visible && !backend.privacyCurtain && backend.canRedo
        onActivated: backend.redo()
    }
    Shortcut { sequence: "Meta+,"; enabled: !backend.privacyCurtain; onActivated: window.currentPage = 1 }
    Shortcut { sequence: "Ctrl+,"; enabled: !backend.privacyCurtain; onActivated: window.currentPage = 1 }
    Shortcut {
        sequences: ["Meta+L", "Ctrl+L"]
        enabled: backend.hasVault && !backend.privacyCurtain
        onActivated: backend.dropPrivacyCurtain("KEYBOARD")
    }
    Shortcut {
        sequence: "Escape"
        enabled: window.customCursorActive && !editor.visible && !backend.privacyCurtain
        onActivated: window.customCursorActive = false
    }

    //MARK: everything the fake crt eats
    Item {
        id: uiRoot
        anchors.fill: parent
        anchors.margins: 12
        layer.enabled: window.shaderEnabled
        // crunchy pixels stay crunchy while the whole screen becomes one texture.
        layer.smooth: false
        layer.effect: ShaderEffect {
            // one shader keeps every panel inside the same gross old monitor.
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
            // text fields steal window events sometimes, so qml remembers the mouse too.
            onPointChanged: {
                window.cursorX = point.scenePosition.x
                window.cursorY = point.scenePosition.y
                window.cursorInside = true
            }
            onHoveredChanged: {
                if (hovered)
                    window.cursorInside = true
            }
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
                        // apple's poop is the only poop allowed in this logo.
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
                        fillColor: window.currentPage === 0
                                   ? window.accentColor : window.panelHighColor
                        labelColor: window.currentPage === 0
                                    ? window.buttonTextColor : window.textColor
                        onClicked: window.currentPage = 0
                    }
                    TerminalButton {
                        text: "SETTINGS"
                        Layout.fillWidth: true
                        fillColor: window.currentPage === 1
                                   ? window.accentColor : window.panelHighColor
                        labelColor: window.currentPage === 1
                                    ? window.buttonTextColor : window.textColor
                        onClicked: window.currentPage = 1
                    }
                    Item { Layout.fillHeight: true }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12
                visible: window.currentPage === 0

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
                            text: "UNDO"
                            enabled: backend.canUndo
                            ToolTip.visible: hovered
                            ToolTip.text: backend.undoText
                            onClicked: backend.undo()
                        }
                        TerminalButton {
                            text: "REDO"
                            enabled: backend.canRedo
                            ToolTip.visible: hovered
                            ToolTip.text: backend.redoText
                            onClicked: backend.redo()
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
                                activeFocusOnTab: true
                                Keys.onPressed: function(event) {
                                    if (event.key === Qt.Key_Up || event.key === Qt.Key_Down) {
                                        backend.selectRelative(event.key === Qt.Key_Down ? 1 : -1)
                                        event.accepted = true
                                    } else if (event.key === Qt.Key_Home) {
                                        backend.selectRow(0)
                                        event.accepted = true
                                    } else if (event.key === Qt.Key_End) {
                                        backend.selectRow(entryList.count - 1)
                                        event.accepted = true
                                    } else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                                               && backend.selectedName !== "—") {
                                        editor.openEdit()
                                        event.accepted = true
                                    }
                                }
                                Connections {
                                    target: backend
                                    function onSelectionMoved(index) {
                                        entryList.positionViewAtIndex(index, ListView.Contain)
                                    }
                                }
                                // the vault can get tall without making the whole window scroll.
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
                                    Accessible.role: Accessible.ListItem
                                    Accessible.name: modelData.name + ", " + modelData.username
                                    Accessible.selected: modelData.name === backend.selectedName
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
                                        onClicked: {
                                            entryList.forceActiveFocus()
                                            backend.selectEntry(modelData.name)
                                        }
                                        onDoubleClicked: {
                                            // select first so editEntry reads the row that was actually clicked.
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
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: window.currentPage === 1
                color: window.panelColor
                border.width: 2
                border.color: window.borderColor

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 48
                        color: window.titleBarColor
                        TerminalText {
                            anchors.fill: parent
                            anchors.leftMargin: 15
                            text: "SYSTEM SETTINGS"
                            color: window.buttonTextColor
                            font.pixelSize: 16
                            font.bold: true
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        contentWidth: availableWidth

                        ColumnLayout {
                            width: parent.width
                            spacing: 14

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.leftMargin: 18
                                Layout.rightMargin: 18
                                Layout.topMargin: 18
                                Layout.preferredHeight: 345
                                color: window.panelHighColor
                                border.width: 1
                                border.color: window.borderColor

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 16
                                    spacing: 12
                                    TerminalText {
                                        text: "AUDIO + PRIVACY TIMERS // BEEP BOOPS"
                                        color: window.accentColor
                                        font.pixelSize: 12
                                        font.bold: true
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        TerminalText {
                                            text: "SFX MASTER"
                                            color: window.mutedColor
                                            font.pixelSize: 10
                                        }
                                        Item { Layout.fillWidth: true }
                                        TerminalButton {
                                            text: backend.sfxEnabled ? "ON" : "OFF"
                                            fillColor: backend.sfxEnabled
                                                       ? window.accentColor : window.panelColor
                                            labelColor: backend.sfxEnabled
                                                        ? window.buttonTextColor : window.textColor
                                            onClicked: backend.setSfxEnabled(!backend.sfxEnabled)
                                        }
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 12
                                        TerminalText {
                                            text: "MASTER VOLUME"
                                            color: window.mutedColor
                                            font.pixelSize: 10
                                            Layout.preferredWidth: 125
                                        }
                                        Slider {
                                            id: volumeSlider
                                            Layout.fillWidth: true
                                            from: 0
                                            to: 100
                                            stepSize: 1
                                            value: backend.volume
                                            enabled: backend.sfxEnabled
                                            opacity: enabled ? 1.0 : 0.35
                                            onMoved: backend.setVolume(Math.round(value))
                                            background: Rectangle {
                                                x: volumeSlider.leftPadding
                                                y: volumeSlider.topPadding + volumeSlider.availableHeight / 2 - height / 2
                                                width: volumeSlider.availableWidth
                                                height: 8
                                                color: "#020603"
                                                border.width: 1
                                                border.color: window.borderColor
                                                Rectangle {
                                                    width: volumeSlider.visualPosition * parent.width
                                                    height: parent.height
                                                    color: window.accentColor
                                                }
                                            }
                                            handle: Rectangle {
                                                x: volumeSlider.leftPadding
                                                   + volumeSlider.visualPosition
                                                   * (volumeSlider.availableWidth - width)
                                                y: volumeSlider.topPadding
                                                   + volumeSlider.availableHeight / 2 - height / 2
                                                width: 18
                                                height: 24
                                                color: volumeSlider.pressed
                                                       ? window.accentHoverColor : window.accentColor
                                                border.width: 1
                                                border.color: window.buttonTextColor
                                            }
                                        }
                                        TerminalText {
                                            text: backend.volume + "%"
                                            opacity: backend.sfxEnabled ? 1.0 : 0.35
                                            font.bold: true
                                            Layout.preferredWidth: 48
                                            horizontalAlignment: Text.AlignRight
                                        }
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        TerminalText {
                                            text: "CLIPBOARD"
                                            color: window.mutedColor
                                            font.pixelSize: 9
                                        }
                                        TerminalSpin {
                                            from: 5
                                            to: 120
                                            value: backend.clipboardSeconds
                                            Layout.preferredWidth: 132
                                            textFromValue: function(value, locale) {
                                                return value + " SEC"
                                            }
                                            valueFromText: function(text, locale) {
                                                return parseInt(text)
                                            }
                                            onValueModified: backend.setClipboardSeconds(value)
                                        }
                                        TerminalText {
                                            text: "REVEAL"
                                            color: window.mutedColor
                                            font.pixelSize: 9
                                            Layout.leftMargin: 10
                                        }
                                        TerminalSpin {
                                            from: 5
                                            to: 120
                                            value: backend.revealSeconds
                                            Layout.preferredWidth: 132
                                            textFromValue: function(value, locale) {
                                                return value + " SEC"
                                            }
                                            valueFromText: function(text, locale) {
                                                return parseInt(text)
                                            }
                                            onValueModified: backend.setRevealSeconds(value)
                                        }
                                        Item { Layout.fillWidth: true }
                                        TerminalButton {
                                            text: "TEST SOUND"
                                            enabled: backend.sfxEnabled
                                            onClicked: backend.requestSound("ui_click")
                                        }
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        TerminalText {
                                            text: "IDLE CURTAIN"
                                            color: window.mutedColor
                                            font.pixelSize: 9
                                        }
                                        TerminalSpin {
                                            from: 30
                                            to: 3600
                                            stepSize: 30
                                            value: backend.idleSeconds
                                            Layout.preferredWidth: 150
                                            textFromValue: function(value, locale) {
                                                return value < 60 ? value + " SEC"
                                                     : Math.floor(value / 60) + " MIN"
                                            }
                                            valueFromText: function(text, locale) {
                                                var number = parseInt(text)
                                                return text.toUpperCase().includes("MIN")
                                                       ? number * 60 : number
                                            }
                                            onValueModified: backend.setIdleSeconds(value)
                                        }
                                        Item { Layout.fillWidth: true }
                                        TerminalButton {
                                            text: "DROP CURTAIN NOW"
                                            enabled: backend.hasVault
                                            onClicked: backend.dropPrivacyCurtain("MANUAL BUTTON")
                                        }
                                    }
                                    TerminalText {
                                        text: "THE CURTAIN HIDES THE UI + CLEARS P00P'S OWN CLIPBOARD TEXT. IT IS NOT A LOGIN SCREEN."
                                        color: window.mutedColor
                                        font.pixelSize: 9
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 18
                                Layout.rightMargin: 18
                                Layout.preferredHeight: 130
                                spacing: 14

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    color: window.panelHighColor
                                    border.width: 1
                                    border.color: window.borderColor

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 16
                                        spacing: 10
                                        TerminalText {
                                            text: "DISPLAY // CRT CREATURE"
                                            color: window.accentColor
                                            font.pixelSize: 12
                                            font.bold: true
                                        }
                                        RowLayout {
                                            Layout.fillWidth: true
                                            TerminalText {
                                                text: "CRT SHADER"
                                                color: window.mutedColor
                                                font.pixelSize: 10
                                            }
                                            Item { Layout.fillWidth: true }
                                            TerminalButton {
                                                text: backend.shaderEnabled ? "ENABLED" : "BYPASSED"
                                                fillColor: backend.shaderEnabled
                                                           ? window.accentColor : window.panelColor
                                                labelColor: backend.shaderEnabled
                                                            ? window.buttonTextColor : window.textColor
                                                onClicked: backend.setShaderEnabled(!backend.shaderEnabled)
                                            }
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    color: window.panelHighColor
                                    border.width: 1
                                    border.color: window.borderColor

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 16
                                        TerminalText {
                                            text: "APP GUTS"
                                            color: window.accentColor
                                            font.pixelSize: 12
                                            font.bold: true
                                        }
                                        DetailLine {
                                            fieldName: "VERSION"
                                            fieldValue: backend.versionText
                                        }
                                        DetailLine {
                                            fieldName: "BAD IDEAS"
                                            fieldValue: backend.commonPasswordCount + " COMMON PASSWORDS LOADED"
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.leftMargin: 18
                                Layout.rightMargin: 18
                                Layout.preferredHeight: 505
                                color: window.panelHighColor
                                border.width: 1
                                border.color: window.borderColor

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 16
                                    spacing: 9
                                    TerminalText {
                                        text: "VAULT UTILITIES // TINY HOSPITAL + LIFEBOAT DOCK"
                                        color: window.accentColor
                                        font.pixelSize: 12
                                        font.bold: true
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        TerminalButton {
                                            text: "RUN 12-CHECK DOCTOR"
                                            Layout.fillWidth: true
                                            enabled: backend.hasVault
                                            onClicked: backend.runDoctor()
                                        }
                                        TerminalButton {
                                            text: "LAUNCH LIFEBOAT SNAPSHOT"
                                            Layout.fillWidth: true
                                            enabled: backend.hasVault
                                            fillColor: window.accentColor
                                            hoverFillColor: window.accentHoverColor
                                            labelColor: window.buttonTextColor
                                            outlineColor: window.accentColor
                                            onClicked: backend.backupVault()
                                        }
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        TerminalButton {
                                            text: "NEW 24-ENTRY DECOY BOWL"
                                            Layout.fillWidth: true
                                            onClicked: backend.newDecoyVault()
                                        }
                                        TerminalButton {
                                            text: "REROLL CAMOUFLAGE"
                                            Layout.fillWidth: true
                                            enabled: backend.hasVault
                                            onClicked: backend.rerollCamouflage()
                                        }
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        TerminalButton {
                                            text: "EXPORT SAFE REPORT"
                                            Layout.fillWidth: true
                                            enabled: backend.hasVault
                                            onClicked: backend.exportSafeReport()
                                        }
                                        TerminalButton {
                                            text: "RUN 10-ROUND STORAGE LAB"
                                            Layout.fillWidth: true
                                            enabled: backend.hasVault
                                            onClicked: backend.runStorageLab()
                                        }
                                    }
                                    TerminalButton {
                                        text: "MERGE ANOTHER BOWL INTO A THIRD BOWL"
                                        Layout.fillWidth: true
                                        enabled: backend.hasVault
                                        onClicked: backend.mergeAnotherVault()
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        TerminalButton {
                                            text: "STAMP BYTE SEAL"
                                            Layout.fillWidth: true
                                            enabled: backend.hasVault
                                            onClicked: backend.stampVaultSeal()
                                        }
                                        TerminalButton {
                                            text: "VERIFY BYTE SEAL"
                                            Layout.fillWidth: true
                                            enabled: backend.hasVault
                                            onClicked: backend.verifyVaultSeal()
                                        }
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        TerminalButton {
                                            objectName: "ledgerStampButton"
                                            text: "STAMP LEDGER CHECKPOINT"
                                            Layout.fillWidth: true
                                            enabled: backend.hasVault
                                            onClicked: backend.stampLedgerCheckpoint()
                                        }
                                        TerminalButton {
                                            objectName: "ledgerVerifyButton"
                                            text: "VERIFY BOWL LEDGER"
                                            Layout.fillWidth: true
                                            enabled: backend.hasVault
                                            onClicked: backend.verifyVaultLedger()
                                        }
                                    }
                                    DetailLine {
                                        fieldName: "DOCTOR"
                                        fieldValue: backend.doctorSummary
                                    }
                                    DetailLine {
                                        fieldName: "BOWL STATS"
                                        fieldValue: backend.statsSummary
                                    }
                                    DetailLine {
                                        fieldName: "BYTE SEAL"
                                        fieldValue: backend.sealSummary
                                    }
                                    DetailLine {
                                        fieldName: "FORMAT LAB"
                                        fieldValue: backend.labSummary
                                    }
                                    DetailLine {
                                        fieldName: "BOWL LEDGER"
                                        fieldValue: backend.ledgerSummary
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 3
                                        TerminalText {
                                            text: "LAST LIFEBOAT"
                                            color: window.mutedColor
                                            font.pixelSize: 9
                                            font.bold: true
                                        }
                                        TerminalText {
                                            text: backend.lastLifeboat
                                            color: window.textColor
                                            font.pixelSize: 9
                                            elide: Text.ElideMiddle
                                            Layout.fillWidth: true
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.leftMargin: 18
                                Layout.rightMargin: 18
                                Layout.bottomMargin: 18
                                Layout.preferredHeight: 175
                                color: "#180909"
                                border.width: 2
                                border.color: "#6f2420"

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 16
                                    spacing: 9
                                    TerminalText {
                                        text: "DANGER ZONE // EXTREMELY SERIOUS BUTTONS"
                                        color: window.dangerColor
                                        font.pixelSize: 12
                                        font.bold: true
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        TerminalButton {
                                            text: "CLEAR CLIPBOARD"
                                            Layout.fillWidth: true
                                            onClicked: backend.clearClipboard()
                                        }
                                        TerminalButton {
                                            text: "RESET SETTINGS"
                                            Layout.fillWidth: true
                                            onClicked: backend.resetSettings()
                                        }
                                    }
                                    TerminalButton {
                                        text: "DELETE ALL VAULT ENTRIES"
                                        Layout.fillWidth: true
                                        enabled: backend.hasEntries
                                        fillColor: "#3c1110"
                                        hoverFillColor: "#5a1916"
                                        labelColor: window.dangerColor
                                        outlineColor: "#6f2420"
                                        onClicked: backend.deleteAllEntries()
                                    }
                                    TerminalText {
                                        visible: backend.hasEntries
                                        text: "THIS ASKS ONCE. SESSION UNDO CAN BRING IT BACK UNTIL U OPEN ANOTHER VAULT."
                                        color: window.mutedColor
                                        font.pixelSize: 9
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        Item {
            id: customCursor
            // qt popups live in overlay land, so the mouse has to live there too.
            parent: Overlay.overlay
            z: 1000000
            visible: window.customCursorActive && window.cursorInside
            readonly property int hotspotX: window.customCursorMode === 1 ? 12
                                              : window.customCursorMode === 2 ? 8 : 0
            readonly property int hotspotY: window.customCursorMode === 2 ? 12 : 0
            // overlay uses the same window coordinates that python reports.
            x: Math.round(window.cursorX) - hotspotX
            y: Math.round(window.cursorY) - hotspotY
            width: 32
            height: 32

            Canvas {
                anchors.fill: parent
                antialiasing: false
                readonly property int pixelSize: 4
                // f is the dark outline, c is the light fill, and dots are air.
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
                    // repaint the whole 8x8 sprite. tiny enough that clever caching is pointless.
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

    //MARK: add and edit entry thingy
    Item {
        id: editor
        anchors.fill: parent
        z: 9000
        visible: false
        enabled: visible
        focus: visible
        property bool editMode: false
        property string originalName: ""

        function open() {
            // normal item visibility keeps the editor inside the crt render pass.
            visible = true
            window.playSound("dialog_open")
            forceActiveFocus()
        }
        function close() {
            visible = false
            window.playSound("dialog_close")
            // do not leave an ibeam cursor stuck over the normal vault screen.
            window.customCursorMode = 0
        }

        function openNew() {
            editMode = false
            originalName = ""
            nameField.text = ""
            usernameField.text = ""
            passwordField.text = ""
            notesField.text = ""
            open()
            Qt.callLater(function() { nameField.forceActiveFocus() })
        }
        function openEdit() {
            var entry = window.selectedEntry()
            if (!entry.name)
                return
            editMode = true
            originalName = entry.name
            nameField.text = entry.name
            usernameField.text = entry.username
            passwordField.text = entry.password
            notesField.text = entry.notes
            open()
            Qt.callLater(function() { nameField.forceActiveFocus() })
        }

        function save() {
            var saved = window.saveEntry(
                editMode, originalName, nameField.text, usernameField.text,
                passwordField.text, notesField.text)
            if (saved)
                close()
        }

        Keys.onEscapePressed: function(event) {
            // eat escape here so the global shortcut does not also disable the cursor.
            close()
            event.accepted = true
        }

        Rectangle {
            anchors.fill: parent
            color: "#a0000000"
        }

        MouseArea {
            // stop clicks from leaking through the modal into the vault behind it.
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: window.customCursorActive ? Qt.BlankCursor : Qt.ArrowCursor
        }

        Rectangle {
            id: editorPanel
            width: 570
            height: Math.min(650, editor.height - 24)
            anchors.centerIn: parent
            color: window.panelColor
            border.width: 2
            border.color: window.accentColor

            ColumnLayout {
                anchors.fill: parent
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
                                var generated = window.generatePassword(lengthBox.value, symbolBox.checked)
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
                        TerminalSpin {
                            id: lengthBox
                            from: 12
                            to: 256
                            value: 24
                            Layout.preferredWidth: 132
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
                            text: window.passwordHealth(passwordField.text).text
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
                            onClicked: editor.save()
                        }
                    }
                }
            }
        }
    }

    //MARK: deliberately fake lock screen thingy
    Item {
        id: privacyCurtain
        objectName: "privacyCurtain"
        anchors.fill: parent
        z: 20000
        visible: backend.privacyCurtain
        enabled: visible
        focus: visible

        onVisibleChanged: {
            if (visible)
                Qt.callLater(function() { liftCurtainButton.forceActiveFocus() })
        }

        Rectangle {
            anchors.fill: parent
            color: "#f5030604"
        }

        MouseArea {
            // eat clicks so nothing under the curtain edits itself in the dark.
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: window.customCursorActive ? Qt.BlankCursor : Qt.ArrowCursor
        }

        Rectangle {
            width: Math.min(610, privacyCurtain.width - 56)
            height: 350
            anchors.centerIn: parent
            color: window.panelColor
            border.width: 3
            border.color: window.accentColor

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 28
                spacing: 14

                TerminalText {
                    text: "//// PRIVACY CURTAIN DROPPED ////"
                    color: window.accentColor
                    font.pixelSize: 23
                    font.bold: true
                    Layout.alignment: Qt.AlignHCenter
                }
                TerminalText {
                    text: "THE BOWL IS STILL OPEN UNDER HERE"
                    color: window.textColor
                    font.pixelSize: 13
                    font.bold: true
                    Layout.alignment: Qt.AlignHCenter
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 82
                    color: "#120d08"
                    border.width: 1
                    border.color: window.dangerColor
                    TerminalText {
                        anchors.fill: parent
                        anchors.margins: 13
                        text: "THIS IS A COSMETIC SCREEN COVER, NOT AUTHENTICATION, ENCRYPTION, OR A MASTER PASSWORD. ANYONE CAN PRESS THE BUTTON."
                        color: window.dangerColor
                        font.pixelSize: 11
                        font.bold: true
                        wrapMode: Text.Wrap
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                TerminalText {
                    text: "P00P-OWNED CLIPBOARD TEXT WAS CLEARED. THE IDLE CLOCK RESTARTS AFTER U LIFT THIS."
                    color: window.mutedColor
                    font.pixelSize: 10
                    wrapMode: Text.Wrap
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }
                Item { Layout.fillHeight: true }
                TerminalButton {
                    id: liftCurtainButton
                    objectName: "liftCurtainButton"
                    text: "LIFT CURTAIN // NO PASSWORD REQUIRED"
                    Layout.fillWidth: true
                    fillColor: window.accentColor
                    hoverFillColor: window.accentHoverColor
                    labelColor: window.buttonTextColor
                    outlineColor: window.accentColor
                    onClicked: backend.liftPrivacyCurtain()
                }
            }
        }
    }
    }
}
