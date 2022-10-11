# org-ical
Sync org files to a remote calendar.

# Configuration

The behavior is configurable via the config, located at `~/.config/org-ical/config.yaml`. To avoid walking the whole fs, `root_org_dir` is specified in the config and all siblings are crawled.

Currently, there are two sync strategies, i.e. Whitelist and Blacklist.

## Whitelist

When active means that only the org files located in the whitelist array will be synced.

## Blacklist

When active implies that all files are synced except those listed in the blacklist array.

# Instructions

To start using `org-ical`, follow the steps:

1. `pip install org-ical`
2. Create an application in Google Cloud Console 
3. Generate OAuth 2.0 Client IDs Credentials
4. Specify the following as Authorized redirect URIs
- `http://localhost:8080/oauth2callback`
- `http://localhost:8080/`
5. Add yourself as a test user in OAuth consent screen > Test users
6. Execute `python -m org-ical.export`
7. All synced 🚀

Edit your `crontab` to have the syncing running in the background periodically example:

```bash
*/2 * * * * /usr/bin/python -m org_ical.export 
```
