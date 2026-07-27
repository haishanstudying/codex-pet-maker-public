# Initial Submission Release Notes

Codex Pet Maker is a skills-only Plugin that turns a user-provided reference
image or text description into a validated, install-ready Codex v2 animated
pet.

## Included in this submission

- Resumable, low-context orchestration that does not repeat completed stages.
- Bounded retries that repair only the failed animation stage.
- Deterministic atlas assembly and transparency cleanup.
- Structural validation for the 1536×2288, 8×11 Codex v2 atlas.
- Visual validation for animation identity and all viewing directions.
- Packaging of the final `pet.json` and `spritesheet.webp` pair.
- Installation only when the user explicitly requests it.
- Privacy controls that isolate user media from Plugin source and other runs.

## Reviewer notes

- Submission type: Skills only.
- No MCP server, authentication, demo credentials, or private network is
  required.
- The public test fixture is the synthetic geometric `Shape Scout` image.
- Repository images are fixed by path and SHA-256 allowlist.
- The submitted Skill contains no user media, private pet, generated run data,
  credentials, telemetry, or absolute user path.
- Local verification covers Plugin structure, Skill structure, 34 automated
  tests, and a release privacy scan.
