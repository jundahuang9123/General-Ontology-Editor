# Android Wrapper

This folder contains a native Android WebView wrapper for the General Ontology Editor.

The wrapper bundles the built React editor into the APK and opens it in a WebView by default. It also keeps a server URL dialog for cases where you want to connect to the FastAPI backend for RDF, OWL, and SHACL import support.

## Bundled Mode

When you build the Android project, Gradle runs the frontend build and copies `frontend/dist` into the APK assets. In bundled mode the editor can open, edit, import LinkML YAML/JSON through the system file picker, save to device storage, and export YAML/RDF/SHACL Turtle to local or cloud storage without a PC server.

RDF, OWL, and SHACL upload parsing still requires the backend server. LinkML YAML/JSON upload works inside the bundled app.

Automatic frontend builds require Node.js/npm on your PATH. If npm is not available, Gradle can still package an existing `frontend/dist` bundle.

## Optional Server Mode

Android emulator networking is different from browser networking. If you choose to use the backend server, this URL points from the emulator to the host machine:

```text
http://10.0.2.2:8010/
```

points from the emulator to the host machine. On a physical Android device, use the LAN address of the machine running Docker, for example:

```text
http://192.168.1.25:8010/
```

Debug builds allow cleartext HTTP for this local testing flow. Release builds are HTTPS-only by default, so use a trusted HTTPS URL if you need server mode in a distributed APK.

## Build With Android Studio

1. Open `android-wrapper/` in Android Studio.
2. Let Android Studio sync Gradle.
3. Run the `app` configuration on an Android emulator, tablet, or phone.
4. Leave the server setting blank for bundled mode.
5. Optional: start the Docker backend and tap `Server` to enter its reachable URL when you need backend import support.

The project is pinned to Android Gradle Plugin 9.1.0, Gradle 9.3.1, compile SDK 36.1, and target SDK 36.

CLI build:

```bash
./gradlew assembleDebug lintDebug
./gradlew assembleRelease lintRelease
```

## APK Distribution

For a small teammate beta, you can share an APK directly. Use the debug APK only for trusted internal testing; for broader testing, create a signed release APK or use Google Play internal testing so installs, updates, and device trust are easier to manage.

Typical outputs:

```text
android-wrapper/app/build/outputs/apk/debug/app-debug.apk
android-wrapper/app/build/outputs/apk/release/app-release-unsigned.apk
```

The debug APK is debug-signed and installable for trusted testers. The release APK shown above is unsigned until you configure release signing in Android Studio, so it is a build artifact rather than an installable production package.

Android users who install a directly shared APK may need to approve installation from that source. Keep the APK link private and replace old builds when you send updates.

## Security Notes

The bundled editor runs from app assets and does not require a backend server. Import and export use Android's system file picker, so the app does not request broad storage access.

Release builds disable WebView debugging, app backup, WebView file URL access, and cleartext HTTP. The JavaScript export bridge is guarded so it only runs while the WebView is on the bundled editor or the configured editor origin.

## Release Notes

For production distribution, use a signed release build and keep server mode on HTTPS.
