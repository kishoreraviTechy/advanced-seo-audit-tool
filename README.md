# SiteLens — Technical SEO Audit Platform

A full-stack portfolio application for crawling public websites, finding common on-page and technical SEO issues, and exporting audit reports.

## Features
- Bounded same-domain crawl (1–25 pages)
- Page title and meta description checks
- H1 structure, H2 count, image alt attributes, canonical URL and word count
- Broken page discovery from crawled URLs
- robots.txt and sitemap.xml checks
- Rule-based page score and issue summary
- Responsive React dashboard and CSV export
- FastAPI health endpoint and Docker-ready API

## Technology
- Frontend: React, TypeScript, Vite, Lucide
- Backend: Python, FastAPI, Requests, BeautifulSoup
- Deployment configuration: Render API + Vercel frontend
- PostgreSQL audit history is planned but is not implemented in this MVP.

## Run locally

### Backend
1. Open a terminal in the backend directory.
2. Create and activate a Python virtual environment.
3. Install dependencies: pip install -r requirements.txt
4. Start API: uvicorn main:app --reload --port 8000
5. Optional: set DATABASE_URL to a PostgreSQL connection string to enable persistent audit history.\n6. API docs: http://localhost:8000/docs

### Frontend
1. Open another terminal in frontend.
2. Install dependencies: npm install
3. Start app: npm run dev
4. Open the local Vite URL printed in the terminal.

Set VITE_API_URL to your deployed API URL when hosting the frontend. The default local API is http://localhost:8000.

## Deployment
- Backend: deploy backend/Dockerfile to Render, or use the included render.yaml blueprint.
- Frontend: deploy the frontend directory to Vercel with build command npm run build and output directory dist.
- Configure VITE_API_URL in Vercel to point to the Render API, then redeploy.
- Before production, restrict backend CORS to your frontend origin.

Hosting providers require your own account authorization. Deployment configuration is included, but this app has not yet been published to a hosting provider.

## API
- GET /health — service health\n- GET /api/audits — latest 50 saved reports (requires DATABASE_URL)
- POST /api/audit — JSON body: {"url":"https://example.com","max_pages":10}

## Responsible use and limitations
- Portfolio-grade MVP; not a Google Search Console, Lighthouse or PageSpeed replacement.
- Scores are rule-based indicators and do not represent Google rankings.
- Crawler is limited to public HTTP(S), same-host pages, a maximum page count, timeouts and response-size limits. It does not execute JavaScript.
- This version does not yet validate every external link or integrate Google APIs.
- Only audit websites you own or are authorized to test. Respect website terms and crawl load.

## Roadmap
- [ ] PostgreSQL audit history and user accounts
- [ ] External link validation with rate limits
- [ ] PageSpeed Insights / Core Web Vitals integration
- [ ] Scheduled crawls and PDF reports
- [ ] Automated unit and integration tests

## License
MIT
