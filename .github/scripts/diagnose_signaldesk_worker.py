"""Read-only diagnosis of SignalDesk's Cloudflare Worker HTTP 403.

Never read or print HTML bodies, tokens, cookies, Access AUDs, application
names, or user identities. Does not alter any Cloudflare settings.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

HOST = "signaldesk-news-feed.littlekingchess.workers.dev"
ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def safe_probe(route):
    request = urllib.request.Request("https://" + HOST + route,
        headers={"User-Agent": "SignalDesk-ReadOnly-HealthDiagnostic/1.0",
                 "Accept": "application/json"})
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=12) as response:
            status, headers = response.status, response.headers
    except urllib.error.HTTPError as error:
        status, headers = error.code, error.headers
    except urllib.error.URLError:
        print(route + ": network or DNS error (no response)")
        return
    fields = {
        "status":status,
        "content_type":(headers.get("Content-Type") or "").split(";")[0][:45],
        "cf_mitigated":(headers.get("cf-mitigated") or "absent")[:35],
        "server":(headers.get("Server") or "absent")[:35],
    }
    target = headers.get("Location")
    if target:
        parsed=urllib.parse.urlsplit(urllib.parse.urljoin("https://"+HOST, target))
        fields["redirect_host"]=parsed.hostname
        fields["redirect_to_access"]=parsed.path.startswith("/cdn-cgi/access/")
    # No headers that could contain secrets are printed.
    print(route + ": " + json.dumps(fields))


def check_access_apps():
    if not TOKEN or len(ACCOUNT)!=32:
        print("Access app metadata: Cloudflare token/account not available")
        return
    request=urllib.request.Request(
        "https://api.cloudflare.com/client/v4/accounts/"+ACCOUNT+"/access/apps?page=1&per_page=100",
        headers={"Authorization":"Bearer "+TOKEN,"Accept":"application/json"})
    try:
        with urllib.request.urlopen(request,timeout=12) as response:
            obj=json.load(response)
    except urllib.error.HTTPError as error:
        print("Access app metadata: HTTP "+str(error.code)+
              " (Access Apps and Policies Read permission may be missing)")
        return
    except (urllib.error.URLError,ValueError):
        print("Access app metadata: unavailable")
        return
    if obj.get("success") is not True or not isinstance(obj.get("result"),list):
        print("Access app metadata: unrecognized response")
        return
    apps=obj["result"]
    matches=[]
    for app in apps:
        destinations=app.get("destinations")
        if not isinstance(destinations,list):
            destinations=[]
        for d in destinations:
            if not isinstance(d,dict):
                continue
            typ=d.get("type")
            if typ=="all_workers":
                matches.append("account_all_workers")
            elif typ=="worker" and d.get("worker_id")=="signaldesk-news-feed":
                matches.append("single_worker")
            elif typ=="public":
                uri=str(d.get("uri","")).lower()
                if HOST in uri or "*.workers.dev" in uri:
                    matches.append("matching_hostname")
    print("Access app metadata: "+json.dumps({
        "apps_readable":True,
        "all_workers_rule_present":"account_all_workers" in matches,
        "specific_worker_rule_present":"single_worker" in matches,
        "hostname_rule_present":"matching_hostname" in matches,
        "note":"App names, destinations and policies intentionally omitted."
    }))


def main():
    print("SignalDesk Worker public endpoint diagnosis: READ ONLY")
    for path in ("/health","/feed"):
        safe_probe(path)
    check_access_apps()
    print("No Cloudflare settings were changed.")


if __name__=="__main__":
    main()
