# Publishing

Where this skill can go, what each venue actually requires, and the order to do it in.

## The model

Keep one source of truth and treat every registry as a discovery surface:

1. **A public Git repository is the artifact.** Everything else points at it.
2. **Registries index the repository.** Most do not want an upload; they want a public repo with a valid `SKILL.md` at a path they can find.
3. **A release is a tag**, not a copy pushed to each site.

The layout here is already registry-friendly: `skills/<name>/SKILL.md` is the conventional shape that `npx skills add`, skills.sh, and most directories expect to find.

## Venue matrix

| Venue | How publishing works | Effort | Worth it? |
| --- | --- | --- | --- |
| **GitHub** | Push a public repo, tag a release | none beyond the push | **Yes — required.** Every other venue keys off it. |
| **[skills.sh](https://www.skills.sh/)** | No upload. The site indexes public repos and installs through the `skills` CLI (`npx skills add FZ2000/REPO`). Ranking comes from anonymous install telemetry, not submissions. | none — make the repo public and valid | **Yes.** This is the main discovery and install surface for Agent Skills. |
| **[ClawHub](https://clawhub.ai/)** | `clawhub skill publish` with explicit slug, version, and changelog. Supports a dry run. | one command | **Yes.** Cheap, and it reaches OpenClaw users. |
| **[theskills.directory](https://theskills.directory)** | Fork `theskillsdirectory/skills`, add `skills/<name>/`, open a PR — or use the web form. | moderate — needs extra frontmatter | Yes, as a listing. Note the frontmatter cost below. |
| **[Smithery](https://smithery.ai/docs/api-reference/skills/create-or-update-a-skill)** | API call to create or update a skill. The platform is MCP-centric. | low | Optional. Audience skews to MCP servers rather than skills. |
| **npm** | Publish a package exposing the skill text for programmatic consumers. | moderate | Only if something imports skills programmatically. Not needed for agent use. |
| **`anthropics/skills`** | Anthropic's own showcase repository. There is no `CONTRIBUTING.md` on `main`, and PRs adding one have been proposed but not merged. | high, with no defined path | **No.** Do not plan around it. |

## The frontmatter trade-off

Most clients read `name`, `description`, `license`, `compatibility`, `metadata`, and `allowed-tools`, and ignore unknown keys. `theskills.directory` requires a larger set — `version`, `last_updated`, `compatible_agents`, `categories`, `job_roles`, `author`, `github`, `twitter_x`.

Two ways to satisfy both, in order of preference:

1. **Keep `SKILL.md` clean and generate the submission copy.** A small script copies `SKILL.md` and appends the directory-only keys into `skills/<name>/SKILL.md` for the PR. The repository stays portable; the submission carries what is asked for.
2. **Add the keys directly.** Harmless for clients that ignore unknown keys, but it puts registry-specific metadata in the artifact every client downloads.

Option 1 is better here, because the extra keys would otherwise travel into every user's skills directory for the sake of one directory listing.

## Recommended sequence

1. Push the repository publicly and tag `v0.1.0`.
2. Confirm `npx skills add FZ2000/temporary-email-inbox` installs the skill from the repo.
3. Add the skills.sh badge to `README.md`:

   ```markdown
   [![skills.sh](https://skills.sh/b/FZ2000/temporary-email-inbox)](https://skills.sh/FZ2000/temporary-email-inbox)
   ```

4. Publish to ClawHub with a dry run first:

   ```bash
   npm i -g clawhub
   clawhub login
   clawhub skill publish ./skills/temporary-email-inbox \
     --slug temporary-email-inbox \
     --name "Temporary Email Inbox" \
     --version 0.1.0 \
     --changelog "Initial release" \
     --dry-run
   ```

5. Open the `theskills.directory` PR with the generated submission copy.
6. Skip npm and Smithery unless a concrete consumer appears.

## Status

| Step | State |
| --- | --- |
| Public GitHub repository | **Done** — <https://github.com/FZ2000/temporary-email-inbox> |
| Tag `v0.1.0` | **Done** |
| CI on push (`3.9`, `3.13`) | **Done** — green |
| Apache-2.0 detected by GitHub | **Done** |
| `npx skills add` install verified | **Done** — found 1 skill, installed `SKILL.md`, all 4 references and the script intact, frontmatter valid |
| skills.sh listing | Not started — indexed from the public repo, no upload; add the badge once it appears |
| ClawHub | Not started |
| theskills.directory | Not started |
| npm, Smithery | Deliberately skipped |

## Pre-publish checklist

Registries are supply-chain surfaces, and this skill is unusually trust-sensitive: it tells an agent to install third-party inbox servers and to handle mail that hostile parties can write. Before publishing:

- **Declare network access.** The `compatibility` field already states that the skill needs outbound access to a provider and why. Keep it accurate if the script changes.
- **No hidden install scripts.** The repo ships a plain Python file that the agent chooses to run. Nothing executes on install.
- **No credential collection.** The script creates a throwaway account for itself; it never asks for or transmits the user's credentials.
- **No silent side effects.** `create` writes `.temporary-inbox.json` at mode 0600 and says so; the path is a documented flag and is gitignored.
- **Destructive actions are absent.** The script creates and reads. It does not delete accounts.
- **State the verified-versus-documented split.** The README and the catalog both say plainly that inbound delivery was not observed. Keep that honest as claims get re-tested.
- **Re-verify before each release.** Providers die (1secmail is gone; mail.gw returned 502 when tested) and endpoints move. Re-run the probes in the catalog's verification log and update the date.

## Repository host

Settled: **GitHub, public, under `FZ2000`** — <https://github.com/FZ2000/temporary-email-inbox>. The install command, the badge URL, and the directory PR all embed that path, so it is recorded here rather than left to be re-derived.

A self-hosted Gitea is also in play in this environment under the same owner name, which is exactly why the host is written down: the two are not interchangeable, and picking the wrong one yields a repository that looks right but resolves somewhere else.

