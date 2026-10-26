# Tyrion — The Companion (Android)

Native Android frontend for the **same Tyrion PC backend**. The phone does not maintain a second project/task database; it displays the PC-served authenticated workspace.

## Requirements

- Android 8.0+ (API 26), Android SDK 35 for building, Java/JDK 17.
- Tyrion running on the PC (`tyrion-hand.service`) plus the private companion relay (`tyrion-companion.service`), provisioned separately.
- Tailscale connected on **both** devices, with a private, authenticated `tailscale serve` route (development configuration uses HTTPS port 8443). Do not expose the relay through a public Funnel.

## Build and install

```bash
cd android-companion
./gradlew :app:lintDebug :app:assembleDebug
```

The debug APK is generated under `app/build/outputs/apk/debug/`; binaries are not committed to Git. This is a development build, not a signed store release.

1. On the PC, open `http://127.0.0.1:17877/#connections` and find **Tyrion — The Companion**.
2. Confirm that the PC’s private Tailscale Serve URL for the relay is reachable **from the paired tailnet**. Obtain that URL from your own `tailscale serve status`; do not reuse another developer’s hostname.
3. Install the built debug APK and select the PC’s private URL or QR/pairing flow exposed by Tyrion.
4. Generate a single-use eight-digit pairing code in the PC UI; it expires after five minutes. Complete pairing on the phone.
5. If access is lost or the phone is no longer trusted, revoke its paired device in Tyrion’s **Connections** screen.

## Features

- Native branded launcher and pairing screen with Android Keystore-backed credential storage.
- PC-served responsive UI for Overview, Projects, Tasks, Scheduler, Connections, Dispatch, and other available Tyrion pages.
- Shared audit history, approvals, and task status: all mutations still pass through the PC server.
- View dispatch states and manually request recovery of stalled or older open tasks without duplicating work.
- Relaunch the app or use **Refresh live workspace** to load updated PC UI assets without rebuilding the APK.

## Limitations

- The PC and tailnet connection must stay online; **offline editing and FCM background notifications are not implemented**.
- The phone never runs ChatGPT independently or bypasses external approval requirements.
- Physical-phone end-to-end installation/pairing is not established solely by the project’s HTTP tests or desktop mobile-viewport screenshots.
- The private HTTP relay configuration, keys, and runtime databases remain outside Git.

## Service and smoke checks (PC)

```bash
systemctl --user status tyrion-hand.service
systemctl --user status tyrion-companion.service
systemctl --user status tyrion-companion-events.service
tailscale serve status
curl -fsS http://127.0.0.1:17878/api/mobile/health
```

For security, pairing expiry, device revocation, relay routes, and dispatch behavior, see Python tests under `../tests/`. The Android source is under `app/src/main/`.
