import airAssignments 1.0
import InputAssignment 0.1
import OutputAssignment 0.1
import QtQuick 2.2

// MX5 Bridge 0.7 (inoffiziell). Keine Zuordnungen, nur Marker.
MidiAssignment {
	id: assignment
	objectName: "MX5 Bridge f_midi"

	Component.onCompleted: { console.warn("MX5Bridge[f_midi]: Assignments-Datei geladen") }
}
