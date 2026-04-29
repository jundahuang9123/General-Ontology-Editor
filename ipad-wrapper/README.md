# iOS/iPadOS Wrapper

This folder contains a native SwiftUI iOS/iPadOS wrapper for the General Ontology Editor web app.

The wrapper bundles the built React editor into the app and opens it in a `WKWebView` by default. It gives the user a reload button and keeps a server settings sheet for optional backend import support.

## Bundled Mode

The Xcode project includes a build phase that runs the frontend build and copies `frontend/dist` into the app as `WebApp`. In bundled mode the editor can open, edit, import LinkML YAML/JSON through the Files picker, save to device storage, and export YAML/RDF/SHACL Turtle to local or cloud storage without a PC server.

RDF, OWL, and SHACL upload parsing still requires the backend server. LinkML YAML/JSON upload works inside the bundled app.

The Xcode build phase requires Node.js/npm on the Mac build machine.

## Optional Server Mode

`localhost` on a physical iPhone or iPad means the device itself. To connect to the editor running on this Mac, start the Docker app and enter this Mac's LAN address in the app, for example:

```text
http://192.168.1.25:8010/
```

Use `http://localhost:8010/` only in the iPhone or iPad simulator when the server is running on the same Mac.

## Build On A Mac

1. Copy this repository to a Mac with Xcode installed.
2. Open:

   ```text
   ipad-wrapper/GeneralOntologyEditor.xcodeproj
   ```

3. Select the `GeneralOntologyEditor` target.
4. In `Signing & Capabilities`, choose your Apple developer team.
5. Build and run on an iPhone, iPad, or simulator.
6. Leave the server setting blank for bundled mode.
7. Optional: start the Docker backend and tap the server button to enter its reachable URL when you need backend import support.

## App Store Notes

The included `Info.plist` allows local HTTP networking for development. For production distribution, prefer hosting the editor over HTTPS and tightening App Transport Security settings before submission.
