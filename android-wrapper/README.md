# Android Wrapper

This folder contains a native Android WebView wrapper for the General Ontology Editor.

The wrapper is intentionally thin: it loads the hosted editor in a WebView, provides a native reload button, includes a server URL dialog, and supports file picking for RDF, OWL, SHACL, and related uploads.

## Important Networking Note

Android emulator networking is different from browser networking:

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
3. Start the editor server somewhere reachable:

   ```bash
   docker compose up --build -d
   ```

4. Run the `app` configuration on an Android emulator, tablet, or phone.
5. Tap `Server` in the app toolbar and set the reachable editor URL.

## Release Notes

The debug wrapper permits cleartext HTTP for local development. For production distribution, host the editor over HTTPS and tighten `network_security_config.xml`.
