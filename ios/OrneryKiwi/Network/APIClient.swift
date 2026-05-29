import Foundation

/// Thin async/await wrapper around the Ornery-Kiwi REST API.
/// The base URL is read live from shared UserDefaults on every call
/// so that changing the server URL in Settings takes effect immediately.
actor APIClient {
    static let shared = APIClient()

    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 120
        session = URLSession(configuration: config)

        decoder = JSONDecoder()
        encoder = JSONEncoder()
    }

    private var baseURL: String {
        SettingsStore.current.serverURL
    }

    // MARK: - Public API

    /// POST /ingest  — queue a URL or file path for processing
    func ingest(url: String? = nil, filePath: String? = nil) async throws -> IngestResponse {
        let request = try buildRequest(
            method: "POST",
            path: "/ingest",
            body: IngestRequest(url: url, filePath: filePath)
        )
        return try await perform(request)
    }

    /// GET /ingest/status/{jobId}  — poll until terminal
    func jobStatus(jobId: String) async throws -> JobStatusResponse {
        let request = try buildRequest(method: "GET", path: "/ingest/status/\(jobId)")
        return try await perform(request)
    }

    /// GET /health
    func health() async throws -> HealthResponse {
        let request = try buildRequest(method: "GET", path: "/health")
        return try await perform(request)
    }

    // MARK: - Helpers

    private func buildRequest<B: Encodable>(
        method: String,
        path: String,
        body: B? = nil as String?
    ) throws -> URLRequest {
        guard let url = URL(string: baseURL + path) else {
            throw APIError.invalidURL
        }
        var req = URLRequest(url: url)
        req.httpMethod = method
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try encoder.encode(body)
        }
        return req
    }

    private func buildRequest(method: String, path: String) throws -> URLRequest {
        guard let url = URL(string: baseURL + path) else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = method
        return req
    }

    private func perform<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.noResponse }
        guard (200...299).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw APIError.httpError(http.statusCode, message)
        }
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }
}
