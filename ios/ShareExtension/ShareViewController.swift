import UIKit
import UniformTypeIdentifiers

/// Share Extension entry point.
///
/// Current state: NON-FUNCTIONAL scaffold.
/// The server URL is wired (reads from shared UserDefaults) and the URL
/// extraction logic is stubbed out. See ARCHITECTURE.md §"Share Extension
/// Implementation Checklist" for the remaining steps.
///
/// Connection point: reads `serverURL` from App Group suite
/// "group.com.ornery-kiwi.shared" (same suite written by SettingsStore).
class ShareViewController: UIViewController {

    // MARK: - Configuration (mirrors SettingsStore constants)

    private static let appGroupSuite = "group.com.ornery-kiwi.shared"
    private static let serverURLKey  = "serverURL"
    private static let defaultURL    = "http://localhost:8000"

    private var serverURL: String {
        UserDefaults(suiteName: Self.appGroupSuite)?
            .string(forKey: Self.serverURLKey) ?? Self.defaultURL
    }

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        setupUI()
    }

    // MARK: - Placeholder UI

    private func setupUI() {
        view.backgroundColor = .systemGroupedBackground

        let stack = UIStackView()
        stack.axis = .vertical
        stack.alignment = .center
        stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false

        let titleLabel = UILabel()
        titleLabel.text = "Ornery-Kiwi"
        titleLabel.font = .boldSystemFont(ofSize: 22)

        let serverLabel = UILabel()
        serverLabel.text = serverURL      // ← live URL from shared UserDefaults
        serverLabel.font = .monospacedSystemFont(ofSize: 12, weight: .regular)
        serverLabel.textColor = .secondaryLabel
        serverLabel.numberOfLines = 0
        serverLabel.textAlignment = .center

        let statusLabel = UILabel()
        statusLabel.text = "Share Extension — not yet active\nSee ARCHITECTURE.md for next steps"
        statusLabel.font = .systemFont(ofSize: 14)
        statusLabel.textColor = .secondaryLabel
        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center

        let cancelButton = UIButton(configuration: .bordered())
        cancelButton.setTitle("Dismiss", for: .normal)
        cancelButton.addTarget(self, action: #selector(dismiss_), for: .touchUpInside)

        [titleLabel, serverLabel, statusLabel, cancelButton].forEach { stack.addArrangedSubview($0) }
        view.addSubview(stack)

        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            stack.leadingAnchor.constraint(greaterThanOrEqualTo: view.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(lessThanOrEqualTo: view.trailingAnchor, constant: -24),
        ])
    }

    @objc private func dismiss_() {
        extensionContext?.cancelRequest(
            withError: NSError(domain: "OrneryKiwiShare", code: NSUserCancelledError)
        )
    }

    // MARK: - Planned implementation (non-functional)
    //
    // Step 1: Extract shared item from extensionContext?.inputItems
    //   - For web URLs: use UTType.url (kUTTypeURL)
    //   - For files:    use UTType.fileURL (kUTTypeFileURL)
    //   - For images:   use UTType.image
    //   - For movies:   use UTType.movie
    //
    // Step 2: Build IngestRequest
    //   - URL items  → POST { "url": "https://..." }
    //   - File items → POST { "url": fileURL.absoluteString }
    //     (file:// URLs; the API must be on the same machine or accessible)
    //
    // Step 3: POST to serverURL + "/ingest"
    //   - Use URLSession (network access must be enabled in extension entitlements)
    //   - Parse IngestResponse to get job_id
    //
    // Step 4: Optionally poll /ingest/status/{job_id} and show result
    //
    // Step 5: Call extensionContext?.completeRequest(returningItems: [])

    private func _extractURL(completion: @escaping (String?) -> Void) {
        guard let items = extensionContext?.inputItems as? [NSExtensionItem] else {
            completion(nil)
            return
        }
        for item in items {
            for provider in (item.attachments ?? []) {
                if provider.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
                    provider.loadItem(forTypeIdentifier: UTType.url.identifier) { item, _ in
                        if let url = item as? URL {
                            completion(url.absoluteString)
                        } else {
                            completion(nil)
                        }
                    }
                    return
                }
            }
        }
        completion(nil)
    }

    // Stub: will call POST /ingest when implemented
    private func _submitToAPI(urlString: String) {
        guard let endpoint = URL(string: serverURL + "/ingest") else { return }
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = ["url": urlString]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        // TODO: execute request and handle response
        _ = request  // suppress unused-variable warning until implemented
    }
}
