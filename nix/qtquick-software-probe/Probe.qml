import QtQuick

Rectangle {
    id: root
    width: 1232
    height: 568
    color: "#161b28"
    property bool negativeControl: false
    property bool selected: false
    property bool moved: false

    Rectangle {
        id: header
        width: parent.width
        height: 80
        color: "#26344c"
        Text {
            anchors.centerIn: parent
            text: "Qt Quick software probe"
            color: "#f2f6ff"
            font.pixelSize: 30
        }
    }

    Flickable {
        id: list
        x: 20
        y: 96
        width: 580
        height: 452
        contentHeight: items.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: items
            width: list.width
            spacing: 12
            Repeater {
                model: 20
                Rectangle {
                    width: items.width
                    height: 74
                    radius: 12
                    color: index === 0 && root.selected ? "#4b6ea8" : "#31415d"
                    Text {
                        anchors.centerIn: parent
                        text: "Scroll row " + (index + 1)
                        color: "#f2f6ff"
                        font.pixelSize: 24
                    }
                    TapHandler { onTapped: root.selected = !root.selected }
                }
            }
        }
    }

    Rectangle {
        x: 628; y: 96
        width: 584; height: 90
        radius: 12; color: "#31415d"
        TextInput {
            id: editor
            anchors.fill: parent
            anchors.margins: 22
            text: "Tap to edit"
            color: "#ffffff"
            selectionColor: "#79a8ef"
            font.pixelSize: 27
            verticalAlignment: TextInput.AlignVCenter
            activeFocusOnPress: true
        }
    }

    Rectangle {
        id: moving
        x: root.moved ? root.width - width - 20 : 628
        y: 206
        width: 172; height: 90
        radius: 14
        color: root.moved ? "#9bcfff" : "#f9c67a"
        opacity: root.moved ? 0.7 : 1.0
        Behavior on x { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 280 } }
        Text { anchors.centerIn: parent; text: "Tap / retarget"; color: "#18243a"; font.pixelSize: 19 }
        TapHandler { onTapped: root.moved = !root.moved }
    }

    Rectangle {
        x: 628; y: 316; width: 584; height: 112
        color: "#31415d"; radius: 12
        Image {
            id: tileImage
            x: 20; anchors.verticalCenter: parent.verticalCenter
            width: 64; height: 64; source: "tile.png"
            fillMode: Image.PreserveAspectFit
        }
        Text {
            x: 100; anchors.verticalCenter: parent.verticalCenter
            text: root.negativeControl ? "ShaderEffect negative control below" : "Software-safe solid rectangle"
            color: "#f2f6ff"; font.pixelSize: 19
        }
    }
    ShaderEffect {
        x: 628; y: 448; width: 96; height: 64
        visible: root.negativeControl
        property variant source: tileImage
    }
    Rectangle {
        x: 740; y: 448; width: 96; height: 64; color: "#ff5b79"
    }
}
