# Get a repo up on GitHub — your walkthrough

A repeatable, accessible flow for putting a project on GitHub. Written for **podbill**
(public, open-source), but the same steps work for any repo — just flip public/private at Step 3.

You have the `gh` CLI installed, so this is mostly two commands. Web-UI fallback noted where useful.

---

## Step 0 — Pre-flight (30 seconds of safety)
For a **public** repo, confirm there are no secrets before it goes live:
```bash
cd ~/Developer/podbill
git ls-files | xargs grep -nEi 'api[_-]?key|secret|token|password' || echo "clean ✓"
```
podbill is already clean (no keys, no client data). It has a `README.md`, a `LICENSE` (MIT),
and a `.gitignore` — the three things every public repo should have.

## Step 1 — Make sure it's committed locally
```bash
cd ~/Developer/podbill
git add -A
git commit -m "podbill: bill podcast clients by the minute"   # skip if nothing to commit
```

## Step 2 — Sign in to gh (one-time, if needed)
```bash
gh auth status || gh auth login    # pick GitHub.com → HTTPS → login in browser
```

## Step 3 — Create the GitHub repo AND push, in one command
**Public** (the open-source lead magnet — what podbill wants):
```bash
gh repo create podbill --public --source=. --remote=origin --push \
  --description "Bill your podcast clients by the finished minute. One Python file + ffmpeg."
```
**Private** instead (for your other repos like the course or the promo engine):
```bash
gh repo create trueuser-arc/ios-client-app-course --private --source=. --remote=origin --push
```
That single command creates the repo, wires `origin`, and pushes `main`. Done.

*(Web fallback: github.com → New repo → name it, choose Public, DON'T add a README/license
since you already have them → Create → copy the "push an existing repo" block it shows you.)*

## Step 4 — Polish the public page (2 minutes, makes it look legit)
On the repo page:
1. Click the ⚙️ gear by **About** (top-right) → add **Topics/tags**: `podcast`, `cli`,
   `invoicing`, `freelance`, `audio`, `python`. Tags are how people discover it.
2. Confirm the description shows and the README renders.
3. (Optional) Settings → **Social preview** → upload an image so shared links look good.

## Step 5 — (Optional) Cut a release
Gives people a clean version to point at and shows the project is real:
```bash
gh release create v0.1.0 --title "podbill v0.1.0" --notes "First public release — bill by the minute."
```

## Step 6 — Share it (this is the point)
1. Post the link where podcast editors hang out (the podcast-editing subreddits/Discords, X/Bluesky, your podcast).
2. Lead with the pain it kills: *"Stop reading runtimes off a dashboard to invoice clients — point this at your finished-episodes folder and it does the math."*
3. The README already soft-mentions Showsmith, so every star is also top-of-funnel for the paid tool.

---

### Reuse this for your other repos
Same flow gets `ios-client-app-course` (keep **private** until you decide on hosting) and
`social-promo-engine` (private) onto GitHub for backup — just change the name and the
`--public`/`--private` flag at Step 3.
