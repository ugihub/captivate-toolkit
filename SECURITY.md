# Security policy

Captivate Toolkit is a local file-processing tool. Treat input EXE/SWF files as untrusted. Run jobs with a normal user account, keep the Ruffle asset pinned, and do not expose the local render server to a network interface.

Never put `OPENAI_API_KEY` in a command-line argument, log, manifest, issue, or pull request. Analysis sends selected frames, extracted audio, and prompt text to the configured provider. Report suspected secret exposure or code vulnerabilities privately to the repository maintainers rather than opening a public issue.

