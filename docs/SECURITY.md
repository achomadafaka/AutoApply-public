# Privacy and safe operation

- This is a personal desktop tool, not an internet service. The launcher binds both servers to loopback; the API also validates Host and blocks browser writes from unapproved origins. There is no authentication or multi-user separation. A local process on the same computer may still reach it.
- Keep populated dotenv files, browser artifacts, SQLite files, CVs and application answers out of Git. They may hold personal data, in plain text. Use OS account permissions and disk encryption for an appropriate level of protection.
- Import and inspection make requests to employer job-board endpoints. Fill & Review opens the chosen Greenhouse page; the app blocks HTTP requests during prefill and until interaction inside the form. It never selects or uploads a file. Once you interact, the employer page may send entered details or manually selected files before final submission. Independent browser verification and the final submit action belong to the applicant.
- The Ollama URL is configurable. If it points to another machine, the prompts and any résumé text used to draft application material go there.
- There is no automatic clicking of Submit, platform-evasion feature, or CAPTCHA-solving path. Do not keep retrying an unconfirmed application until you know what the employer received.

Report issues privately to the maintainer when a private contact channel is available. Do not include real applicant data, tokens, full résumés, or employer verification codes in issues or reproductions.
