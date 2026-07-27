# Privacy Statement

Effective date: 2026-07-28

Codex Pet Maker is designed to keep Plugin source separate from user-provided
references and generated pet assets.

## Data processed

Depending on the task, a run may process:

- a reference image supplied by the current user;
- a user-provided or inferred pet name and description;
- prompts created for that run;
- generated animation strips and atlases;
- validation results and visual-review notes; and
- the final Codex pet package.

The repository includes three checksum-pinned `Shape Scout` images from an
isolated synthetic geometry test. It contains no user-provided reference image
or private pet asset.

## Where data goes

| Data | Destination | Purpose |
|---|---|---|
| Reference image | Current run directory | Identity and style reference |
| Reference image attached to an image-generation request | Configured image-generation service | Generate the requested visual job |
| Generated images and QA files | Current run directory | Assembly and validation |
| Final pet package | User-selected package or Codex pet location | Review or installation |
| Plugin source | Plugin or marketplace installation directory | Reusable workflow and deterministic scripts |

The Plugin does not implement analytics, advertising, background telemetry, or
an independent remote server. Processing performed by Codex or an
image-generation provider is governed by the terms and privacy controls of that
service.

## Storage and retention

Run files remain in the local run directory until the user or the hosting
environment removes them. The Plugin does not automatically copy those files
into its source tree, Git repository, or release package.

Retention by a configured image-generation service is outside this Plugin's
control. Users should review that service's data controls before submitting
sensitive material.

## Isolation rules

- Use only inputs supplied for the current user's run.
- Never reuse another run, user asset, generated pet, or prompt as an example.
- Never place user run assets or logs in the Plugin source.
- Use synthetic geometry for automated tests.
- Permit public demo images only by explicit path and SHA-256 allowlist.
- Scan release candidates for other media, unexpected binary files, private
  identifiers, generated directories, and absolute user paths.

## User choices

Users may:

- create a pet from text without attaching a reference image;
- stop before an image-generation request;
- inspect the run directory and generated package before installation;
- remove local run data; and
- decline publication or sharing.

Users are responsible for having the right to use any reference material they
provide.

## Changes to this statement

Material privacy changes will be recorded in [CHANGELOG.md](CHANGELOG.md) and
will update the effective date above.
