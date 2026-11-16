# pterodactyl.castafero.com

**Pterodactyl Tracker.** Strange, unexplained photos and videos people have caught on camera: pterodactyl sightings, UFOs and UAPs, cryptids, ghosts, lights in the sky, and things that are just strange.

- **Sources:** Reddit media posts from r/HighStrangeness, r/UFOs, r/UFOB, r/UAP, r/Cryptozoology, r/bigfoot, r/Paranormal, r/Ghosts, r/Humanoidencounters and r/UnexplainedPhotos, plus a Reddit search for pterodactyl/pterosaur/thunderbird/ropen sightings (public RSS); headlines from Google News.
- **Categories** come from keywords and the subreddit; a pterodactyl mention always wins.
- **Archive:** `items.json` keeps up to 800 sightings and grows every run, so Reddit blocking GitHub for a day costs nothing.
- To change sources, edit `SUBS`, `REDDIT` and `GNEWS` at the top of `build.py`; categories are in `CATS`.
- NSFW/gore keywords are filtered out.

`build.py` (standard-library Python) runs every 3 hours via GitHub Actions and deploys to Pages. Manual refresh: Actions → Update sightings → Run workflow.

Nothing here is verified. Every card links to the original post.
