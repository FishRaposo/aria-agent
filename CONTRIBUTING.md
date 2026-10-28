# Contributing

Small, reviewed, evidence-backed pull requests are welcome. The short version:
**one behavior change per PR, tests with it, and the offline gates green before
review.** See [AGENTS.md](AGENTS.md) for the architecture rules these checks
protect.

## Offline gates (all credential-free)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"

pytest -q                                  # full offline suite
pytest --noconftest tests/test_skills.py -q  # focused Skills suite
ruff check src/aria tests examples scripts
ruff format --check src/aria tests examples scripts
pyright src/
make evidence                              # deterministic offline evidence bundle
make forbidden                             # dependency scan
```

Frontend changes also need:

```bash
cd frontend
npm ci
npm test -- --run
npm run lint
npm run build
```

## Rules the maintainers actually enforce

- **Public API stability.** `AriaAgent.run()`, route vocabulary, response keys,
  approval states and cost semantics are compatibility surfaces — changes there
  need a compatibility note in the PR description.
- **Offline-first defaults.** The default demo path must stay deterministic,
  credential-free and side-effect free. New integrations are opt-in; never add a
  hidden infrastructure or provider requirement.
- **Golden fixtures first.** Any change to score-sensitive behavior updates the
  golden fixture and the tests that lock it in the same PR.
- **Evidence stays reproducible.** `tests/fixtures/golden/portfolio-evidence.json`
  excludes timestamps, durations, generated IDs, and environment paths — keep it
  that way.
- **Boundary discipline.** `src/aria/internal/` is internal; vendored compatibility
  code is attributed and pinned in `THIRD_PARTY_NOTICES.md` and is not a place for
  new features.

## Commit style

Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`), one logical
change per commit. Please keep `git diff --check` clean (no trailing whitespace)
and the working tree clean after tests.

## License

By contributing you agree your contributions are licensed under the repository's
MIT license.
