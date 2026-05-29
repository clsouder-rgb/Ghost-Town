import Foundation

/// Single source of truth for user-configurable settings.
/// Written to a shared App Group suite so the Share Extension can read them.
final class SettingsStore: ObservableObject {

    static let appGroupSuite = "group.com.ornery-kiwi.shared"
    static let serverURLKey  = "serverURL"
    static let defaultURL    = "http://localhost:8000"

    // Convenience accessor for non-SwiftUI contexts (e.g. APIClient, ShareExtension)
    static var current: SettingsStore { _shared }
    private static let _shared = SettingsStore()

    private let defaults: UserDefaults

    @Published var serverURL: String {
        didSet { defaults.set(serverURL, forKey: Self.serverURLKey) }
    }

    init() {
        defaults = UserDefaults(suiteName: Self.appGroupSuite) ?? .standard
        serverURL = defaults.string(forKey: Self.serverURLKey) ?? Self.defaultURL
    }
}
