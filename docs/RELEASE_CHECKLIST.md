# Public release checklist

- [ ] Choose a license and confirm you have the rights to publish the code. Add a `LICENSE` file if you want to grant reuse rights.
- [ ] Use a clean initial snapshot for the first public repository rather than pushing the old private history. Review Git author metadata, the previous remote and account visibility before publishing.
- [ ] Export with `python3 scripts/release_snapshot.py ../AutoApply-source.zip`. Extract into a new folder, inspect it and initialize a new Git repository there. This script excludes history and checks for some risky files; it is not a full secret scanner.
- [ ] Inspect the candidate snapshot for real profiles, CVs, configuration, keys, logs, database artifacts and unpublished materials. Never use `git add -f` for an ignored local file.
- [ ] Test on the documented runtimes from an empty database, including the browser fixture. Compare the CI commands with the local setup guide.
- [ ] Run dependency audits and review any advisories or restrictions before making the repo public.
- [ ] Verify the GitHub description says review-and-submit is manual. Do not imply support for unattended submissions or untested job platforms.
