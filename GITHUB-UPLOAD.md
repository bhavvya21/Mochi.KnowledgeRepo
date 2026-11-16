# Upload Mochi.KnowledgeRepo to GitHub

This folder contains the current deployed Mochi source, including the BM avatar and simplified header. It includes the React frontend, Worker backend, database migrations, tests and benchmark fixtures. No uploaded user documents, browser session cookies, node_modules, build output or Git credentials are included.

Create an empty repository named Mochi.KnowledgeRepo on GitHub. Do not initialize it with a README, license or .gitignore, because this folder already contains project files.

From this extracted folder, run:

```powershell
git init
git add .
git commit -m "Initial Mochi KnowledgeRepo source"
git branch -M main
git remote add origin https://github.com/bhavvya21/Mochi.KnowledgeRepo.git
git push -u origin main
```

Authenticate through GitHub's normal credential prompt. If using a different GitHub account, replace bhavvya21 in the remote URL.

## Validate locally

Use Node.js 24:

```powershell
npm ci
npm test
npm run build
```

## Hosting

The app remains online at https://mochi-knowledge-garden-261116.me-ed0430495.chatgpt.site . Uploading this source to GitHub does not replace or stop the current deployment.

The .openai/hosting.json manifest retains the existing Sites project ID and D1/R2 binding names. These are configuration identifiers, not credentials. GitHub Pages alone cannot run this backend. Publishing future changes requires the existing Sites deployment workflow; pushing to this new GitHub repository does not automatically deploy them.

Answers currently use retrieved source excerpts with citations. No generative model or API key is connected. Personal uploads and session data live in hosted storage, outside this source repository.