import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import Qt.labs.folderlistmodel

// An in-process, portrait-sized chooser using public Qt Quick controls.
// No desktop portal is needed; the backend still owns loading/atomic saving.
Dialog {
    id: root
    property bool saving: false
    property url selectedFile
    property url currentFolder: StandardPaths.writableLocation(StandardPaths.HomeLocation)
    property int containerWidth: 568
    property int containerHeight: 1232
    property bool confirmReplace: false
    onCurrentFolderChanged: confirmReplace = false

    modal: true
    focus: true
    popupType: Popup.Item
    closePolicy: Popup.CloseOnEscape
    width: Math.max(280, containerWidth - 32)
    height: Math.max(220, Math.min(700, containerHeight - 128))
    x: (containerWidth - width) / 2
    y: Math.max(8, (containerHeight - 56 - height) / 2)
    Overlay.modal: Rectangle { color: "#80000000" }
    background: Rectangle {
        color: backend.themeBackground
        border.color: backend.themeAccent
        radius: 12
    }
    padding: 16
    title: saving ? "Save file" : "Open file"

    function pick() {
        if (!filename.text.trim() || filename.text.indexOf("/") >= 0)
            return;
        var folder = currentFolder.toString().replace(/\/$/, "");
        selectedFile = folder + "/" + encodeURIComponent(filename.text);
        if (saving && backend.localFileExists(selectedFile) && !confirmReplace) {
            confirmReplace = true;
            return;
        }
        accept();
    }

    onOpened: {
        confirmReplace = false;
        var file = selectedFile.toString();
        if (saving && file.lastIndexOf("/") >= 0) {
            currentFolder = file.slice(0, file.lastIndexOf("/"));
            filename.text = decodeURIComponent(file.slice(file.lastIndexOf("/") + 1));
        } else {
            filename.text = "";
        }
        filename.forceActiveFocus();
        filename.selectAll();
    }

    FolderListModel {
        id: files
        folder: root.currentFolder
        showDotAndDotDot: false
        showDirsFirst: true
        showHidden: false
        nameFilters: ["*"]
    }

    contentItem: ColumnLayout {
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            Button {
                text: "Up"
                implicitHeight: 48
                enabled: files.parentFolder.toString() !== ""
                onClicked: { root.currentFolder = files.parentFolder; root.confirmReplace = false; }
            }
            Button {
                text: "Home"
                implicitHeight: 48
                onClicked: root.currentFolder = StandardPaths.writableLocation(StandardPaths.HomeLocation)
            }
            Label {
                Layout.fillWidth: true
                text: decodeURIComponent(root.currentFolder.toString().replace(/^file:\/\//, ""))
                elide: Text.ElideLeft
            }
        }
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: files
            ScrollBar.vertical: ScrollBar { }
            delegate: ItemDelegate {
                required property string fileName
                required property url fileUrl
                required property bool fileIsDir
                width: list.width
                height: 52
                text: (fileIsDir ? "▸  " : "") + fileName
                highlighted: !fileIsDir && filename.text === fileName
                background: Rectangle {
                    radius: 6
                    color: parent.highlighted ? backend.themeAccent : "transparent"
                }
                onClicked: {
                    root.confirmReplace = false;
                    if (fileIsDir) root.currentFolder = fileUrl;
                    else filename.text = fileName;
                }
            }
        }
        TextField {
            id: filename
            objectName: "handheldFileName"
            Layout.fillWidth: true
            implicitHeight: 52
            placeholderText: "File name"
            selectByMouse: true
            onTextEdited: root.confirmReplace = false
            onAccepted: root.pick()
        }
        Label {
            Layout.fillWidth: true
            visible: root.confirmReplace
            text: "This file exists. Replace it?"
            wrapMode: Text.Wrap
        }
        RowLayout {
            Layout.fillWidth: true
            Button {
                text: "Cancel"
                Layout.fillWidth: true
                implicitHeight: 52
                onClicked: root.reject()
            }
            Button {
                text: root.confirmReplace ? "Replace" : root.saving ? "Save" : "Open"
                Layout.fillWidth: true
                implicitHeight: 52
                enabled: filename.text.trim() !== "" && filename.text.indexOf("/") < 0
                onClicked: root.pick()
            }
        }
    }
}
