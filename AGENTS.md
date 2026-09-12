# Repository working instructions

## README maintenance

- After every completed task that changes repository code, configuration, notebooks, or documentation, update the bottom `## 변경 이력` section in `README.md` in the same change set.
- Use the actual work date in Korea Standard Time (Asia/Seoul), formatted `YYYY-MM-DD`. Keep date headings newest first; add each new task as a short Korean bullet at the top of that day's entries.
- Summarize what changed and, when useful, the verification actually performed. Do not claim unexecuted hardware, Colab, Drive, or cloud validation succeeded.
- Preserve existing history. Add task-level summaries, not one entry for every temporary edit or intermediate commit. Do not create recursive entries just for adding the history entry itself.
- Keep the README organized as project idea/technology, directory roles, application/device connections, usage/document links, and finally dated change history.
- When directories or integrations change, also update their README descriptions. Distinguish implemented behavior from planned extensions.

## Development references

Follow `CONTRIBUTING.md` for the development workflow and `docs/architecture.md` for module boundaries.
Keep datasets, model weights, runtime output, and credentials out of Git.
