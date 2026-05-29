import SwiftUI

/// Primary settings screen. The server URL field is the integration point
/// between the iOS app and the Ornery-Kiwi API — it is read by both
/// APIClient (main app) and ShareViewController (Share Extension) at runtime.
struct SettingsView: View {

    @EnvironmentObject private var settings: SettingsStore
    @State private var editedURL: String = ""
    @State private var isSaved = false
    @State private var serverReachable: Bool? = nil
    @State private var checkInProgress = false

    var body: some View {
        NavigationStack {
            Form {
                serverURLSection
                statusSection
                aboutSection
            }
            .navigationTitle("Settings")
            .onAppear { editedURL = settings.serverURL }
        }
    }

    // MARK: - Sections

    private var serverURLSection: some View {
        Section {
            TextField("http://mac-mini.local:8000", text: $editedURL)
                .keyboardType(.URL)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)

            Button(action: save) {
                HStack {
                    Text("Save")
                    Spacer()
                    if isSaved {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                    }
                }
            }
        } header: {
            Text("API Server URL")
        } footer: {
            Text("This URL is shared with the Share Extension. Changes take effect immediately.")
                .font(.caption)
        }
    }

    private var statusSection: some View {
        Section("Connection") {
            HStack {
                Text("Status")
                Spacer()
                if checkInProgress {
                    ProgressView().controlSize(.small)
                } else if let ok = serverReachable {
                    Label(ok ? "Reachable" : "Unreachable",
                          systemImage: ok ? "wifi" : "wifi.slash")
                        .foregroundStyle(ok ? .green : .red)
                        .font(.subheadline)
                } else {
                    Text("—").foregroundStyle(.secondary)
                }
            }

            Button("Check Connection") {
                Task { await checkHealth() }
            }
            .disabled(checkInProgress)
        }
    }

    private var aboutSection: some View {
        Section("About") {
            LabeledContent("Agent", value: "Ornery-Kiwi v1.0.0")
            LabeledContent("Ingest endpoint", value: "/ingest")
            LabeledContent("Status endpoint", value: "/ingest/status/{job_id}")
        }
    }

    // MARK: - Actions

    private func save() {
        settings.serverURL = editedURL
        withAnimation { isSaved = true }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            withAnimation { isSaved = false }
        }
    }

    private func checkHealth() async {
        checkInProgress = true
        serverReachable = nil
        do {
            _ = try await APIClient.shared.health()
            serverReachable = true
        } catch {
            serverReachable = false
        }
        checkInProgress = false
    }
}

#Preview {
    SettingsView()
        .environmentObject(SettingsStore())
}
