import Foundation

// MARK: - Ingest

struct IngestRequest: Encodable {
    let url: String?
    let filePath: String?

    enum CodingKeys: String, CodingKey {
        case url
        case filePath = "file_path"
    }
}

struct IngestResponse: Decodable {
    let jobId: String
    let status: String
    let message: String?

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case status
        case message
    }
}

// MARK: - Job Status

struct JobStatusResponse: Decodable {
    let jobId: String
    let status: JobStatusValue
    let source: String
    let createdAt: String
    let updatedAt: String
    let result: JobResult?
    let error: String?

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case status
        case source
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case result
        case error
    }
}

enum JobStatusValue: String, Decodable {
    case queued
    case processing
    case complete
    case failed
    case unknown

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = JobStatusValue(rawValue: raw) ?? .unknown
    }

    var isTerminal: Bool { self == .complete || self == .failed }
}

struct JobResult: Decodable {
    let file: String?
    let type: String?
    let mdPath: String?
    let docxPath: String?
    let viabilityScore: Int?
    let driveUrls: [String: String]?

    enum CodingKeys: String, CodingKey {
        case file
        case type
        case mdPath = "md_path"
        case docxPath = "docx_path"
        case viabilityScore = "viability_score"
        case driveUrls = "drive_urls"
    }
}

// MARK: - Health

struct HealthResponse: Decodable {
    let status: String
    let version: String
    let watchDir: String
    let activeJobs: Int
    let totalJobs: Int

    enum CodingKeys: String, CodingKey {
        case status
        case version
        case watchDir = "watch_dir"
        case activeJobs = "active_jobs"
        case totalJobs = "total_jobs"
    }
}

// MARK: - Errors

enum APIError: LocalizedError {
    case invalidURL
    case noResponse
    case httpError(Int, String)
    case decodingError(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL:          return "Invalid server URL"
        case .noResponse:          return "No response from server"
        case .httpError(let c, let m): return "HTTP \(c): \(m)"
        case .decodingError(let e):    return "Decode error: \(e.localizedDescription)"
        }
    }
}
