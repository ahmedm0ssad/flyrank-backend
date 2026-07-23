Containerize your stack
Type:
Assignment
Code:
BE-04
Track:
Backend AI Engineering
When:
Week 3
Workload:
6h
Phase:
Foundations
Details
Goal
Run Postgres in Docker, connect your A2 service to it (swapping the in-memory store for a real repository), and start app + database together with one command.

Purpose
This is the survival kit applied in one real task: Docker, SQL, .env, and the payoff of A2's layering — proving that "switch storage" really does change only one file. Data that survives a restart is the moment your project stops being a demo. Every later week (jobs, caching, RAG) assumes this local stack.

The task
Start Postgres in Docker with a volume so data persists (the Docker guide has the exact command).
Put the connection string in .env — gitignored, with a committed .env.example .
Create your table with one SQL file (or a tiny init script)
Write a Postgres repository implementing the same interface as your in-memory one, and swap it in. Your service and routes must not change — that's the architecture proving itself.
docker-compose.yml : app + database together; docker compose up runs the whole stack.
Prove persistence: create rows → restart app and container → rows still there.
Requirements
Postgres runs in Docker with a volume ; the whole stack starts with docker compose up .
Connection string from .env (gitignored; .env.example committed).
A Postgres repository replaced the in-memory one — service and routes unchanged (say so in the README, honestly).
Persistence proven across an app + container restart (how you checked goes in the README).
Stretch (optional)
Add Redis to the compose file (you'll want it in W4) and ping it from the app.
Add one index and show EXPLAIN ANALYZE before/after on a seeded table.
Q&A
Feedback
Questions
Public questions are approved by FlyRank first. Use this when the answer can help other interns too.

No public questions yet.

Ask a question
Submission
Add submission
Add a public link or upload a file for Foundation progress.

Deliverable links
Required for completion credit unless you upload a file. One public http(s) URL per line.
https://...
https://...
Notes
Optional context for reviewers. Notes alone do not count toward Foundation progress.
Add context for reviewers.
Files
Required for completion credit unless you add a valid link. Files are stored privately and visible to you and admins.
No file chosen
Save submission
Related resources
1
Resource
Supabase Documentation — Getting Started