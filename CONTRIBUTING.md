# Contributing to PodQApath

Thanks for your interest in contributing. PodQApath is a small open-source project — contributions are welcome but reviewed carefully before merging.

---

## How to Contribute

### 1. Open an Issue First

Before writing code, open an Issue describing what you want to add or fix. This avoids wasted effort if the change doesn't fit the project direction.

### 2. Fork and Branch

```bash
git fork https://github.com/teddyski/podqapath.git
git checkout -b feature/your-feature-name
```

### 3. Make Your Changes

- Keep changes focused — one feature or fix per PR
- Follow the existing code style (Python, Streamlit conventions)
- Do not commit `.env`, secrets, or personal credentials

### 4. Open a Pull Request

Submit your PR against the `main` branch with a clear description of:
- What the change does
- Why it's useful
- Any screenshots if it affects the UI

---

## What Gets Merged

The maintainer reviews all PRs. Changes most likely to be accepted:

- Bug fixes
- New Jira/GitHub integrations
- Improvements to the risk scoring model
- UI clarity improvements

Changes unlikely to be accepted:

- Breaking changes to the core data model
- Dependencies that add significant bloat
- Features that only apply to a single corporate environment

---

## Code of Conduct

Be respectful. This is a side project maintained by one person.

---

## License

By contributing, you agree your changes will be licensed under the [MIT License](LICENSE).
