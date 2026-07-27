# Security Policy

## Supported versions

This project is currently a release candidate. Security fixes are
applied to the latest `0.1.x` revision only.

| Version | Supported |
|---|---|
| 0.1.0-rc.1 | Yes |
| Other 0.1.x builds | No |
| Earlier versions | No |

## Reporting a vulnerability

Do not include reference images, generated pets, prompts, access tokens, local
paths, or other personal data in a public report.

Use GitHub's private vulnerability-reporting option on the repository's
**Security** tab when it is available. If no private reporting option is
available, open a minimal Issue asking the maintainer to establish a private
contact channel. Include no exploit details or sensitive material in that
Issue.

A useful private report contains:

- the affected version;
- the smallest reproducible description;
- the security impact;
- safe reproduction steps using synthetic data; and
- a suggested mitigation, if known.

The maintainer will acknowledge a valid private report, investigate it, and
coordinate disclosure after a fix is available. No response-time guarantee is
made for this release candidate.

## Security boundaries

- The Plugin must never bundle user media or unapproved run artifacts.
- Approved synthetic demo images must match their fixed SHA-256 allowlist.
- Runtime data must remain outside the Plugin source and installation package.
- Image-generation requests must use only references explicitly attached to the
  current run.
- Publication checks must reject images, unexpected binary files, generated
  directories, private identifiers, and absolute user paths.
- Generated pets must pass structural and direction validation before
  installation.
