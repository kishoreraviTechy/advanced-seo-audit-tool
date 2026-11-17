import ipaddress, socket, time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field
from database import Base, SessionLocal, engine, AuditRecord

app = FastAPI(title="SiteLens SEO Audit API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class AuditRequest(BaseModel):
    url: HttpUrl
    max_pages: int = Field(default=10, ge=1, le=25)

def public_url(url):
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise HTTPException(400, "Enter a valid public HTTP or HTTPS URL.")
    try:
        for item in socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM):
            if not ipaddress.ip_address(item[4][0]).is_global:
                raise HTTPException(400, "Private and local network addresses are not allowed.")
    except socket.gaierror:
        raise HTTPException(400, "Website host could not be resolved.")

def page_score(p):
    checks = [
        (bool(p["title"]), "Missing page title"),
        (0 < len(p["title"]) <= 60, "Title should ideally be 1–60 characters"),
        (bool(p["description"]), "Missing meta description"),
        (0 < len(p["description"]) <= 160, "Meta description should ideally be 1–160 characters"),
        (bool(p["h1"]), "Missing H1 heading"),
        (len(p["h1"]) == 1, "Use one clear primary H1"),
        (p["images_without_alt"] == 0, "Images are missing alt text"),
        (bool(p["canonical"]), "Missing canonical URL"),
        (p["word_count"] >= 300, "Low visible text content (under 300 words)")
    ]
    issues = [message for passed, message in checks if not passed]
    return round(100 * (len(checks)-len(issues))/len(checks)), issues

@app.on_event("startup")
def initialize_database():
    if engine:
        Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"status": "ok", "service": "sitelens-seo-audit"}

@app.get("/api/audits")
def audit_history():
    if not SessionLocal:
        return {"items": [], "storage": "DATABASE_URL is not configured"}
    with SessionLocal() as db:
        items = db.query(AuditRecord).order_by(AuditRecord.created_at.desc()).limit(50).all()
        return {"items": [{"id":x.id,"url":x.url,"pages_crawled":x.pages_crawled,"average_score":x.average_score,"created_at":x.created_at.isoformat()} for x in items]}

@app.post("/api/audit")
def audit(req: AuditRequest):
    started = time.time()
    root = str(req.url).rstrip("/")
    public_url(root)
    host = urlparse(root).hostname
    queue, visited, pages, broken, errors = deque([root]), set(), [], [], []
    session = requests.Session()
    session.headers["User-Agent"] = "SiteLensBot/1.0 (bounded technical SEO audit)"
    while queue and len(visited) < req.max_pages:
        current = urldefrag(queue.popleft())[0]
        if current in visited: continue
        visited.add(current)
        try:
            public_url(current)
            r = session.get(current, timeout=12, allow_redirects=False, stream=True)
            if r.status_code >= 400:
                broken.append({"url": current, "status": r.status_code})
                continue
            if r.status_code in (301,302,303,307,308):
                errors.append({"url": current, "issue": "Redirect not followed"})
                continue
            if "text/html" not in r.headers.get("content-type", ""): continue
            html = r.raw.read(1500000, decode_content=True).decode(r.encoding or "utf-8", errors="replace")
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.get_text(" ", strip=True) if soup.title else ""
            meta = soup.find("meta", attrs={"name": lambda x: x and x.lower()=="description"})
            desc = (meta.get("content") or "").strip() if meta else ""
            h1 = [x.get_text(" ", strip=True) for x in soup.find_all("h1")]
            images = soup.find_all("img")
            canonical_tag = soup.find("link", rel=lambda x: x and "canonical" in x)
            text = soup.get_text(" ", strip=True)
            p = {"url":current,"status":r.status_code,"title":title,"description":desc,"h1":h1,
                 "h2_count":len(soup.find_all("h2")),"images":len(images),
                 "images_without_alt":sum(1 for i in images if not (i.get("alt") or "").strip()),
                 "canonical":canonical_tag.get("href","") if canonical_tag else "",
                 "word_count":len(text.split())}
            p["score"], p["issues"] = page_score(p)
            pages.append(p)
            for a in soup.find_all("a", href=True):
                target = urldefrag(urljoin(current, a["href"]))[0]
                parsed = urlparse(target)
                if parsed.scheme in ("http","https") and parsed.hostname == host and target not in visited and len(visited)+len(queue) < req.max_pages:
                    queue.append(target)
        except HTTPException: raise
        except Exception as exc: errors.append({"url":current,"issue":str(exc)[:160]})
    robots, sitemap = "Not checked", "Not found"
    try:
        public_url(root + "/robots.txt")
        rr = session.get(root + "/robots.txt", timeout=8, allow_redirects=False)
        robots = "Found" if rr.status_code == 200 else "HTTP " + str(rr.status_code)
        if rr.status_code == 200:
            for line in rr.text.splitlines():
                if line.lower().startswith("sitemap:"): sitemap = line.split(":",1)[1].strip()
    except Exception: robots = "Could not check"
    try:
        public_url(root + "/sitemap.xml")
        sr = session.get(root + "/sitemap.xml", timeout=8, allow_redirects=False)
        if sr.status_code == 200: sitemap = root + "/sitemap.xml"
    except Exception: pass
    counts = {}
    for p in pages:
        for issue in p["issues"]: counts[issue] = counts.get(issue,0)+1
    result = {"url":root,"pages_crawled":len(pages),"average_score":round(sum(p["score"] for p in pages)/len(pages)) if pages else 0,
            "pages":pages,"broken_links":broken,"errors":errors,
            "issue_summary":[{"issue":k,"count":v} for k,v in sorted(counts.items(),key=lambda x:-x[1])],
            "robots_txt":robots,"sitemap":sitemap,"duration_seconds":round(time.time()-started,2),
            "notice":"Rule-based audit guidance only; scores do not represent Google rankings."}
    if SessionLocal:
        with SessionLocal() as db:
            record = AuditRecord(url=root, pages_crawled=result["pages_crawled"], average_score=result["average_score"], report=result)
            db.add(record)
            db.commit()
    return result
