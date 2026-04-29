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

## Build With Android Studio

1. Open `android-wrapper/` in Android Studio.
2. Let Android Studio sync Gradle.
3. Run the `app` configuration on an Android emulator, tablet, or phone.
4. Leave the server setting blank for bundled mode.
5. Optional: start the Docker backend and tap `Server` to enter its reachable URL when you need backend import support.

## Release Notes

The debug wrapper permits cleartext HTTP for local development. For production distribution, host the editor over HTTPS and tighten `network_security_config.xml`.
