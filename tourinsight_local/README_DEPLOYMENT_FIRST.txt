START HERE: DEPLOY TOURINSIGHT 3.5

This is a full-stack project. Use the included DEPLOY_VERCEL_RENDER.md.

Order matters:
1) Upload project contents to a new GitHub repository.
2) Deploy Render Blueprint first.
3) Copy the Render URL into the three placeholder destinations in vercel.json and commit.
4) Import the same GitHub repository into Vercel with Output Directory = web.

Do not deploy to Vercel before replacing the Render URL in vercel.json; the frontend will load but API calls will not work.
