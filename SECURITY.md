# Security policy

## Reporting a vulnerability

Please don't open a public issue for a security problem.

Report it privately through GitHub: open the [Security tab](https://github.com/Rishavbhattarai/spring-payment-pci-shield/security) of this repository and select **Report a vulnerability**. Only the maintainer can see the report.

Include what you found, the steps to reproduce it, and the version from `.claude-plugin/plugin.json`. I'll reply within 7 days, and I'll tell you when a fix is released.

## Scope

Problems worth reporting include:

- A way to make the hook or the scanner run code from a file it reads
- A file path or input that makes the hook read or write outside the file being checked
- An MCP tool that sends requests anywhere other than the URL or project it was given
- A way for a crafted file to make the hook print misleading instructions to Claude

A rule that misses a pattern, or flags something it shouldn't, is a normal bug. Open an [issue](https://github.com/Rishavbhattarai/spring-payment-pci-shield/issues) for those.

## Supported versions

Only the latest release gets fixes.
