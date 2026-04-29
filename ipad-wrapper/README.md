# iPadOS Wrapper

This folder contains a native SwiftUI iPadOS wrapper for the General Ontology Editor web app.

The wrapper is intentionally thin: it opens the editor in a `WKWebView`, gives the user a reload button, and includes a server settings sheet for changing the editor URL.

## Important Networking Note

`localhost` on a physical iPad means the iPad itself. To connect to the editor running on this PC, start the Docker app and enter this PC's LAN address in the iPad app, for example:

```text
http://192.168.1.25:8010/
```

Use `http://localhost:8010/` only in the iPad simulator when the server is running on the same Mac.

## Build On A Mac

1. Copy this repository to a Mac with Xcode installed.
2. Start the web app somewhere reachable from the iPad:

   ```bash
   docker compose up --build -d
   ```

3. Open:

   ```text
   ipad-wrapper/GeneralOntologyEditor.xcodeproj
   ```

4. Select the `GeneralOntologyEditor` target.
5. In `Signing & Capabilities`, choose your Apple developer team.
6. Build and run on an iPad or iPad simulator.
7. Tap the server button in the app toolbar and enter the reachable editor URL.

## App Store Notes

The included `Info.plist` allows local HTTP networking for development. For production distribution, prefer hosting the editor over HTTPS and tightening App Transport Security settings before submission.
