import SwiftUI
import WebKit

private let bundledEditorURL = URL(string: "goe://editor/index.html")!

struct EditorWebView: UIViewRepresentable {
    let url: URL?
    let reloadToken: UUID

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.allowsInlineMediaPlayback = true
        configuration.setURLSchemeHandler(WebAppSchemeHandler(), forURLScheme: "goe")

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.allowsBackForwardNavigationGestures = true
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        let location = url?.absoluteString ?? "bundled"
        if context.coordinator.currentLocation != location {
            context.coordinator.currentLocation = location
            context.coordinator.reloadToken = reloadToken
            loadEditor(in: webView)
            return
        }

        if context.coordinator.reloadToken != reloadToken {
            context.coordinator.reloadToken = reloadToken
            webView.reload()
        }
    }

    private func loadEditor(in webView: WKWebView) {
        if let url {
            webView.load(URLRequest(url: url))
            return
        }

        guard Bundle.main.url(forResource: "index", withExtension: "html", subdirectory: "WebApp") != nil else {
            webView.loadHTMLString("<h1>General Ontology Editor</h1><p>Bundled web app assets are missing. Build the frontend before running the wrapper.</p>", baseURL: nil)
            return
        }

        webView.load(URLRequest(url: bundledEditorURL))
    }

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        var currentLocation: String?
        var reloadToken: UUID?
    }
}

final class WebAppSchemeHandler: NSObject, WKURLSchemeHandler {
    func webView(_ webView: WKWebView, start urlSchemeTask: WKURLSchemeTask) {
        guard let url = urlSchemeTask.request.url,
              let resourceURL = resourceURL(for: url),
              let data = try? Data(contentsOf: resourceURL) else {
            urlSchemeTask.didFailWithError(NSError(domain: "GeneralOntologyEditor", code: 404))
            return
        }

        let response = URLResponse(
            url: url,
            mimeType: mimeType(for: resourceURL.pathExtension),
            expectedContentLength: data.count,
            textEncodingName: "utf-8"
        )
        urlSchemeTask.didReceive(response)
        urlSchemeTask.didReceive(data)
        urlSchemeTask.didFinish()
    }

    func webView(_ webView: WKWebView, stop urlSchemeTask: WKURLSchemeTask) {}

    private func resourceURL(for url: URL) -> URL? {
        guard let baseURL = Bundle.main.resourceURL?.appendingPathComponent("WebApp", isDirectory: true) else {
            return nil
        }

        var relativePath = url.path
        if relativePath.isEmpty || relativePath == "/" {
            relativePath = "/index.html"
        }

        let fileURL = baseURL.appendingPathComponent(String(relativePath.dropFirst()))
        return fileURL.path.hasPrefix(baseURL.path) ? fileURL : nil
    }

    private func mimeType(for pathExtension: String) -> String {
        switch pathExtension.lowercased() {
        case "html": return "text/html"
        case "js": return "text/javascript"
        case "css": return "text/css"
        case "json": return "application/json"
        case "svg": return "image/svg+xml"
        case "woff2": return "font/woff2"
        case "png": return "image/png"
        default: return "application/octet-stream"
        }
    }
}
