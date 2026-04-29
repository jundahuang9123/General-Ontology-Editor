import SwiftUI

private let defaultEditorURL = "http://localhost:8010/"

struct ContentView: View {
    @AppStorage("editorURL") private var editorURLText = ""
    @State private var reloadToken = UUID()
    @State private var showingSettings = false

    private var editorURL: URL? {
        let trimmed = editorURLText.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : normalizedURL(from: trimmed)
    }

    var body: some View {
        NavigationStack {
            EditorWebView(url: editorURL, reloadToken: reloadToken)
                .ignoresSafeArea(.keyboard)
                .navigationTitle("General Ontology Editor")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItemGroup(placement: .navigationBarTrailing) {
                        Button {
                            reloadToken = UUID()
                        } label: {
                            Label("Reload", systemImage: "arrow.clockwise")
                        }

                        Button {
                            showingSettings = true
                        } label: {
                            Label("Server", systemImage: "gearshape")
                        }
                    }
                }
                .sheet(isPresented: $showingSettings) {
                    ServerSettingsView(editorURLText: $editorURLText) {
                        reloadToken = UUID()
                    }
                }
        }
    }
}

struct ServerSettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @Binding var editorURLText: String
    @State private var draftURL: String
    let onApply: () -> Void

    init(editorURLText: Binding<String>, onApply: @escaping () -> Void) {
        self._editorURLText = editorURLText
        self._draftURL = State(initialValue: editorURLText.wrappedValue)
        self.onApply = onApply
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Editor Server") {
                    TextField("Bundled local editor", text: $draftURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                Section {
                    Text("Leave blank to use the bundled editor. Enter a backend server URL only when you need RDF, OWL, and SHACL import support.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Server")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button("Apply") {
                        editorURLText = normalizedURLString(from: draftURL)
                        onApply()
                        dismiss()
                    }
                }
            }
        }
        .presentationDetents([.medium])
    }
}

private func normalizedURLString(from text: String) -> String {
    let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
    if trimmed.isEmpty {
        return ""
    }

    let withScheme = trimmed.contains("://") ? trimmed : "http://\(trimmed)"
    return withScheme.hasSuffix("/") ? withScheme : "\(withScheme)/"
}

private func normalizedURL(from text: String) -> URL? {
    let normalized = normalizedURLString(from: text)
    return normalized.isEmpty ? nil : URL(string: normalized)
}
