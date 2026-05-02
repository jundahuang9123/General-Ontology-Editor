package com.jundahuang.generalontologyeditor;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Insets;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.WindowInsets;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import android.window.OnBackInvokedDispatcher;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final String PREFS_NAME = "general_ontology_editor";
    private static final String PREF_EDITOR_URL = "editor_url";
    private static final String HTTP_SCHEME = "http";
    private static final String HTTPS_SCHEME = "https";
    private static final String LOCAL_EDITOR_HOST = "general-ontology-editor.local";
    private static final String LOCAL_EDITOR_URL = "https://" + LOCAL_EDITOR_HOST + "/index.html";
    private static final int FILE_CHOOSER_REQUEST = 1001;
    private static final int EXPORT_FILE_REQUEST = 1002;

    private WebView webView;
    private SharedPreferences preferences;
    private ValueCallback<Uri[]> filePathCallback;
    private String pendingExportFileName;
    private String pendingExportMimeType;
    private String pendingExportText;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        preferences = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);
        applySystemBarInsets(root);

        root.addView(createToolbar());

        webView = new WebView(this);
        configureWebView(webView);
        configureBackNavigation();
        root.addView(
            webView,
            new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        );

        setContentView(root);
        loadEditor();
    }

    private void applySystemBarInsets(LinearLayout root) {
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            int topInset;
            int bottomInset;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                Insets systemBars = insets.getInsets(WindowInsets.Type.systemBars());
                topInset = systemBars.top;
                bottomInset = systemBars.bottom;
            } else {
                topInset = insets.getSystemWindowInsetTop();
                bottomInset = insets.getSystemWindowInsetBottom();
            }

            view.setPadding(0, topInset, 0, bottomInset);
            return insets;
        });
    }

    private void configureBackNavigation() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                OnBackInvokedDispatcher.PRIORITY_DEFAULT,
                this::handleBackNavigation
            );
        }
    }

    private LinearLayout createToolbar() {
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setPadding(dp(12), dp(8), dp(12), dp(8));
        toolbar.setBackgroundColor(Color.WHITE);

        TextView title = new TextView(this);
        title.setText(getString(R.string.app_name));
        title.setTextColor(Color.rgb(17, 24, 39));
        title.setTextSize(16);
        title.setSingleLine(true);
        title.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.addView(
            title,
            new LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                1f
            )
        );

        Button reloadButton = new Button(this);
        reloadButton.setText(R.string.reload);
        reloadButton.setOnClickListener(view -> webView.reload());
        toolbar.addView(reloadButton);

        Button serverButton = new Button(this);
        serverButton.setText(R.string.server);
        serverButton.setOnClickListener(view -> showServerDialog());
        toolbar.addView(serverButton);

        return toolbar;
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWebView(WebView view) {
        WebSettings settings = view.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccess(false);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setLoadWithOverviewMode(false);
        settings.setUseWideViewPort(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSafeBrowsingEnabled(true);

        view.addJavascriptInterface(new GeneralOntologyEditorBridge(), "GeneralOntologyEditor");
        view.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView webView, WebResourceRequest request) {
                return handleNavigation(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView webView, String url) {
                return handleNavigation(Uri.parse(url));
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView webView, WebResourceRequest request) {
                return localAssetResponse(request.getUrl());
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView webView, String url) {
                return localAssetResponse(Uri.parse(url));
            }
        });
        view.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(
                WebView webView,
                ValueCallback<Uri[]> callback,
                FileChooserParams fileChooserParams
            ) {
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                }

                filePathCallback = callback;
                Intent intent = fileChooserParams.createIntent();
                try {
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                    return true;
                } catch (ActivityNotFoundException exception) {
                    filePathCallback = null;
                    Toast.makeText(MainActivity.this, R.string.file_picker_unavailable, Toast.LENGTH_LONG).show();
                    return false;
                }
            }
        });
    }

    private WebResourceResponse localAssetResponse(Uri uri) {
        if (!HTTPS_SCHEME.equalsIgnoreCase(uri.getScheme()) || !LOCAL_EDITOR_HOST.equals(uri.getHost())) {
            return null;
        }

        String path = uri.getPath();
        if (path == null || path.equals("/")) {
            path = "/index.html";
        }

        String assetPath = "editor" + path;
        try {
            InputStream stream = getAssets().open(assetPath);
            return new WebResourceResponse(mimeTypeFor(path), "UTF-8", stream);
        } catch (IOException exception) {
            return null;
        }
    }

    private String mimeTypeFor(String path) {
        String lower = path.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".html")) return "text/html";
        if (lower.endsWith(".js")) return "text/javascript";
        if (lower.endsWith(".css")) return "text/css";
        if (lower.endsWith(".json")) return "application/json";
        if (lower.endsWith(".svg")) return "image/svg+xml";
        if (lower.endsWith(".woff2")) return "font/woff2";
        if (lower.endsWith(".png")) return "image/png";
        return "application/octet-stream";
    }

    private void loadEditor() {
        String editorUrl = getConfiguredEditorUrl();
        webView.loadUrl(editorUrl.isEmpty() ? LOCAL_EDITOR_URL : editorUrl);
    }

    private String getConfiguredEditorUrl() {
        return preferences.getString(PREF_EDITOR_URL, "");
    }

    private void showServerDialog() {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        input.setText(getConfiguredEditorUrl());
        input.setHint(R.string.server_url_hint);
        input.setSelectAllOnFocus(true);

        new AlertDialog.Builder(this)
            .setTitle(R.string.server_url)
            .setMessage(R.string.server_url_help)
            .setView(input)
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.apply, (dialog, which) -> {
                String normalized = normalizeUrl(input.getText().toString());
                SharedPreferences.Editor editor = preferences.edit();
                if (normalized.isEmpty()) {
                    editor.remove(PREF_EDITOR_URL);
                } else {
                    editor.putString(PREF_EDITOR_URL, normalized);
                }
                editor.apply();
                loadEditor();
            })
            .show();
    }

    private String normalizeUrl(String value) {
        String trimmed = value.trim();
        if (trimmed.isEmpty()) {
            return "";
        }

        String withScheme = trimmed.contains("://") ? trimmed : "http://" + trimmed;
        return withScheme.endsWith("/") ? withScheme : withScheme + "/";
    }

    private boolean handleNavigation(Uri uri) {
        if (uri == null) {
            return true;
        }

        if (isAllowedEditorUri(uri)) {
            return false;
        }

        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (ActivityNotFoundException exception) {
            Toast.makeText(this, R.string.external_link_unavailable, Toast.LENGTH_LONG).show();
        }
        return true;
    }

    private boolean isAllowedEditorUri(Uri uri) {
        if (uri == null) {
            return false;
        }

        String scheme = uri.getScheme();
        if (!HTTP_SCHEME.equalsIgnoreCase(scheme) && !HTTPS_SCHEME.equalsIgnoreCase(scheme)) {
            return false;
        }

        if (HTTPS_SCHEME.equalsIgnoreCase(scheme) && LOCAL_EDITOR_HOST.equals(uri.getHost())) {
            return true;
        }

        Uri configuredUri = configuredEditorUri();
        return configuredUri != null && sameOrigin(uri, configuredUri);
    }

    private Uri configuredEditorUri() {
        String configuredUrl = getConfiguredEditorUrl();
        return configuredUrl.isEmpty() ? null : Uri.parse(configuredUrl);
    }

    private boolean sameOrigin(Uri first, Uri second) {
        String firstHost = first.getHost();
        String secondHost = second.getHost();
        return firstHost != null
            && secondHost != null
            && firstHost.equalsIgnoreCase(secondHost)
            && normalizedScheme(first).equals(normalizedScheme(second))
            && normalizedPort(first) == normalizedPort(second);
    }

    private String normalizedScheme(Uri uri) {
        String scheme = uri.getScheme();
        return scheme == null ? "" : scheme.toLowerCase(Locale.ROOT);
    }

    private int normalizedPort(Uri uri) {
        int explicitPort = uri.getPort();
        if (explicitPort != -1) {
            return explicitPort;
        }

        String scheme = uri.getScheme();
        if (HTTPS_SCHEME.equalsIgnoreCase(scheme)) {
            return 443;
        }
        if (HTTP_SCHEME.equalsIgnoreCase(scheme)) {
            return 80;
        }
        return -1;
    }

    private boolean isTrustedEditorContext() {
        String currentUrl = webView == null ? null : webView.getUrl();
        return currentUrl != null && isAllowedEditorUri(Uri.parse(currentUrl));
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == EXPORT_FILE_REQUEST) {
            handleExportResult(resultCode, data);
            return;
        }

        if (requestCode != FILE_CHOOSER_REQUEST || filePathCallback == null) {
            return;
        }

        Uri[] result = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
        filePathCallback.onReceiveValue(result);
        filePathCallback = null;
    }

    @SuppressLint("GestureBackNavigation")
    @Override
    public void onBackPressed() {
        handleBackNavigation();
    }

    private void handleBackNavigation() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }

        finish();
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void startExport(String fileName, String mimeType, String text) {
        pendingExportFileName = sanitizeFileName(fileName);
        pendingExportMimeType = sanitizeMimeType(mimeType);
        pendingExportText = text == null ? "" : text;

        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType(pendingExportMimeType);
        intent.putExtra(Intent.EXTRA_TITLE, pendingExportFileName);

        try {
            startActivityForResult(intent, EXPORT_FILE_REQUEST);
        } catch (ActivityNotFoundException exception) {
            clearPendingExport();
            Toast.makeText(this, R.string.export_picker_unavailable, Toast.LENGTH_LONG).show();
        }
    }

    private void handleExportResult(int resultCode, Intent data) {
        Uri uri = data == null ? null : data.getData();
        if (resultCode != RESULT_OK || uri == null || pendingExportText == null) {
            clearPendingExport();
            return;
        }

        try (OutputStream stream = getContentResolver().openOutputStream(uri)) {
            if (stream == null) {
                throw new IOException("No output stream");
            }
            stream.write(pendingExportText.getBytes(StandardCharsets.UTF_8));
            Toast.makeText(this, R.string.export_saved, Toast.LENGTH_SHORT).show();
        } catch (IOException exception) {
            Toast.makeText(this, getString(R.string.export_failed, exception.getLocalizedMessage()), Toast.LENGTH_LONG).show();
        } finally {
            clearPendingExport();
        }
    }

    private void clearPendingExport() {
        pendingExportFileName = null;
        pendingExportMimeType = null;
        pendingExportText = null;
    }

    private String sanitizeFileName(String fileName) {
        if (fileName == null) {
            return "ontology-export.ttl";
        }

        String cleaned = fileName.replaceAll("[\\\\/:]", "-").trim();
        return cleaned.isEmpty() ? "ontology-export.ttl" : cleaned;
    }

    private String sanitizeMimeType(String mimeType) {
        if (mimeType == null || mimeType.trim().isEmpty() || !mimeType.contains("/")) {
            return "text/plain";
        }

        return mimeType.trim();
    }

    private final class GeneralOntologyEditorBridge {
        @JavascriptInterface
        public void exportText(String fileName, String mimeType, String text) {
            runOnUiThread(() -> {
                if (!isTrustedEditorContext()) {
                    Toast.makeText(MainActivity.this, R.string.export_blocked, Toast.LENGTH_LONG).show();
                    return;
                }
                startExport(fileName, mimeType, text);
            });
        }
    }
}
