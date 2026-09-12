# NEXORA v0.3.1 Tester release

The screenshot’s limited response was caused by two deliberate Tester-edition behaviours: the build profile forces keyless Demo mode, and the Demo provider’s generic echo branch ran before identity handling. The provider was not silently failing; this package was intentionally offline. The generic echo branch is now replaced with useful local responses and identity handling runs first.

The tester build remains Demo mode because no secure NEXORA online service is configured. A future deployment can set `NEXORA_SERVICE_URL` to an HTTPS developer-operated service and provision `NEXORA_SERVICE_TOKEN` through Windows Credential Manager. No provider API key or service token is bundled.

## Verified

- Packaged backend health: `status=ok`, version `0.3.1`, profile `tester`, mode `demo`.
- Exact prompt `give me self introduction`: approved NEXORA introduction returned.
- Generic `I received your message` text: absent.
- Provider names in the normal introduction: absent.
- Demo replies cover identity, creator, capabilities, help, greeting, privacy, feedback, navigation, and supported features.
- Unsupported prompts explain that the online NEXORA service is required.
- Secure service adapter: fake-client tests cover healthy response and retry after a connection failure.
- Tester provider/model/key routes and fields remain unavailable.
- Ruff: passed.
- Offline suite: **126 passed, 1 skipped**. The skipped test requires Windows symlink privileges.
- Installer build: passed.
- Packaged secret scan: zero key-shaped strings and zero distributed `.env` files.
- Active removed-provider scan: zero references.

## Installer

`installer/output/NEXORA-Setup-v0.3.1-Tester.exe`

Size: 149,377,380 bytes (142.46 MiB)

SHA-256: `5C8D514A679CDD6F4F52E7EF5F68BD2C6ECD49A1D9C8A87C5D7591BD7444930C`

This installer uses **Demo mode**, not Online mode. It needs no Python, API key, or development tools. Real online replies require a secure NEXORA service to be deployed and configured by the developer.
