import SwiftUI
import UniformTypeIdentifiers
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
        configuration.userContentController.add(context.coordinator, name: "generalOntologyEditor")

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.allowsBackForwardNavigationGestures = true
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        context.coordinator.webView = webView
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

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler, UIDocumentPickerDelegate {
        var currentLocation: String?
        var reloadToken: UUID?
        weak var webView: WKWebView?
        private var openPanelCompletionHandler: (([URL]?) -> Void)?

        @available(iOS 18.4, *)
        func webView(
            _ webView: WKWebView,
            runOpenPanelWith parameters: WKOpenPanelParameters,
            initiatedByFrame frame: WKFrameInfo,
            completionHandler: @escaping ([URL]?) -> Void
        ) {
            openPanelCompletionHandler?(nil)
            openPanelCompletionHandler = completionHandler

            let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.item], asCopy: true)
            picker.allowsMultipleSelection = parameters.allowsMultipleSelection
            picker.delegate = self

            guard present(picker, from: webView) else {
                openPanelCompletionHandler?(nil)
                openPanelCompletionHandler = nil
                return
            }
        }

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            guard message.name == "generalOntologyEditor",
                  let body = message.body as? [String: Any],
                  body["action"] as? String == "exportText",
                  let filename = body["filename"] as? String,
                  let text = body["text"] as? String else {
                return
            }

            exportText(text, filename: filename)
        }

        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            openPanelCompletionHandler?(urls)
            openPanelCompletionHandler = nil
        }

        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            openPanelCompletionHandler?(nil)
            openPanelCompletionHandler = nil
        }

        private func exportText(_ text: String, filename: String) {
            let destination = FileManager.default.temporaryDirectory.appendingPathComponent(sanitizedFilename(filename))

            do {
                try text.write(to: destination, atomically: true, encoding: .utf8)
            } catch {
                showAlert(title: "Export failed", message: error.localizedDescription)
                return
            }

            let picker = UIDocumentPickerViewController(forExporting: [destination], asCopy: true)
            if !present(picker, from: webView) {
                showAlert(title: "Export unavailable", message: "No document picker is available.")
            }
        }

        private func sanitizedFilename(_ filename: String) -> String {
            let pieces = filename.components(separatedBy: CharacterSet(charactersIn: "/\\:"))
            let cleaned = pieces.joined(separator: "-").trimmingCharacters(in: .whitespacesAndNewlines)
            return cleaned.isEmpty ? "ontology-export.ttl" : cleaned
        }

        private func present(_ controller: UIViewController, from view: UIView?) -> Bool {
            guard let presenter = presenter(for: view) else {
                return false
            }

            presenter.present(controller, animated: true)
            return true
        }

        private func presenter(for view: UIView?) -> UIViewController? {
            var controller = view?.window?.rootViewController
            while let presented = controller?.presentedViewController {
                controller = presented
            }
            return controller
        }

        private func showAlert(title: String, message: String) {
            let alert = UIAlertController(title: title, message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default))
            _ = present(alert, from: webView)
        }
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
