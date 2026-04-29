package com.jundahuang.generalontologyeditor;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.ViewGroup;
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
import java.io.IOException;
import java.io.InputStream;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final String PREFS_NAME = "general_ontology_editor";
    private static final String PREF_EDITOR_URL = "editor_url";
    private static final String LOCAL_EDITOR_HOST = "general-ontology-editor.local";
    private static final String LOCAL_EDITOR_URL = "https://" + LOCAL_EDITOR_HOST + "/index.html";
    private static final int FILE_CHOOSER_REQUEST = 1001;

    private WebView webView;
    private SharedPreferences preferences;
    private ValueCallback<Uri[]> filePathCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        preferences = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        WebView.setWebContentsDebuggingEnabled(true);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);

        root.addView(createToolbar());

        webView = new WebView(this);
        configureWebView(webView);
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

    private void configureWebView(WebView view) {
        WebSettings settings = view.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccess(true);
        settings.setAllowFileAccessFromFileURLs(true);
        settings.setAllowUniversalAccessFromFileURLs(true);
        settings.setLoadWithOverviewMode(false);
        settings.setUseWideViewPort(false);

        view.setWebViewClient(new WebViewClient() {
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
        if (!LOCAL_EDITOR_HOST.equals(uri.getHost())) {
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

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != FILE_CHOOSER_REQUEST || filePathCallback == null) {
            return;
        }

        Uri[] result = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
        filePathCallback.onReceiveValue(result);
        filePathCallback = null;
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }

        super.onBackPressed();
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
